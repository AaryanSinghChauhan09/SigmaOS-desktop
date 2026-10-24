"""Wayland compositor shell configuration for SigmaOS-desktop.

Principles: validate before apply (fail-fast), pure plan layer (no Wayland
connection is opened by these functions), least astonishment (canonical,
deterministic keybind map), KISS.
"""
import argparse, json, os, re, sys

ENGINE = {
    "name": "sigma-desktop",
    "summary": "Configure outputs, inputs, keybinds and the session",
    "language": "python",
    "verbs": ["outputs", "inputs", "keybinds", "session"],
    "principles": ["Fail-Fast", "Least Astonishment", "Pure Plan / Thin Execute",
                   "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-desktop outputs outputs.json
$ sigma-desktop inputs inputs.json
$ sigma-desktop keybinds keybinds.json
$ sigma-desktop session session.json
"""


class DesktopError(Exception):
    pass


_MODE_RE = re.compile(r"^(\d+)x(\d+)(@(\d+(\.\d+)?))?$")
_LAYOUT_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
_ENVKEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
MOD_ORDER = ("SUPER", "CTRL", "ALT", "SHIFT")
_KEY_RE = re.compile(r"^[A-Z0-9]{1,12}$")


def outputs(specs):
    """Pure: validate monitor configs; deterministic order by output name."""
    out, names = [], set()
    for spec in specs:
        name = spec.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,32}", name):
            raise DesktopError(f"bad output name: {name!r}")
        if name in names:
            raise DesktopError(f"duplicate output: {name}")
        names.add(name)
        m = _MODE_RE.match(str(spec.get("mode", "")))
        if not m:
            raise DesktopError(f"{name}: bad mode {spec.get('mode')!r}")
        scale = spec.get("scale", 1.0)
        if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not (0.25 <= scale <= 4.0):
            raise DesktopError(f"{name}: bad scale {scale!r}")
        pos = spec.get("pos", [0, 0])
        if (not isinstance(pos, list) or len(pos) != 2
                or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                           for v in pos)):
            raise DesktopError(f"{name}: bad position {pos!r}")
        out.append({"name": name, "width": int(m.group(1)), "height": int(m.group(2)),
                    "refresh": float(m.group(4) or 60), "scale": float(scale),
                    "pos": list(pos), "enabled": bool(spec.get("enabled", True))})
    if out and not any(o["enabled"] for o in out):
        raise DesktopError("at least one output must be enabled")
    return sorted(out, key=lambda o: o["name"])


def inputs(specs):
    """Pure: validate input device configs."""
    out, names = [], set()
    for spec in specs:
        name = spec.get("name")
        itype = spec.get("type")
        if not isinstance(name, str) or not name.strip():
            raise DesktopError(f"bad input name: {name!r}")
        if name in names:
            raise DesktopError(f"duplicate input: {name}")
        names.add(name)
        if itype not in ("keyboard", "touchpad", "pointer", "tablet"):
            raise DesktopError(f"{name}: bad input type {itype!r}")
        rec = {"name": name, "type": itype}
        if itype == "keyboard":
            layout = spec.get("layout", "us")
            if not isinstance(layout, str) or not _LAYOUT_RE.match(layout):
                raise DesktopError(f"{name}: bad layout {layout!r}")
            rec["layout"] = layout
        if itype in ("touchpad", "pointer"):
            speed = spec.get("speed", 0)
            if not isinstance(speed, int) or isinstance(speed, bool) or not (-100 <= speed <= 100):
                raise DesktopError(f"{name}: bad speed {speed!r}")
            rec["speed"] = speed
        if itype == "touchpad":
            rec["tap"] = bool(spec.get("tap", True))
        out.append(rec)
    return sorted(out, key=lambda r: r["name"])


def canonical_chord(chord):
    """Pure: normalize a chord like 'alt+super+t' -> 'SUPER+ALT+T'."""
    parts = [p.strip().upper() for p in str(chord).split("+")]
    if len(parts) < 2:
        raise DesktopError(f"bad keybind chord: {chord!r}")
    *mods, key = parts
    if any(m not in MOD_ORDER for m in mods):
        raise DesktopError(f"{chord!r}: unknown modifier (one of {MOD_ORDER})")
    if len(set(mods)) != len(mods):
        raise DesktopError(f"{chord!r}: repeated modifier")
    if not _KEY_RE.match(key):
        raise DesktopError(f"{chord!r}: bad key {key!r}")
    ordered = [m for m in MOD_ORDER if m in mods]
    return "+".join(ordered + [key])


def keybinds(mapping):
    """Pure: canonical keybind map; fail-fast on conflicting chords."""
    out, seen = {}, {}
    for chord, action in mapping.items():
        canon = canonical_chord(chord)
        if not isinstance(action, str) or not action.strip():
            raise DesktopError(f"{canon}: empty action")
        if canon in seen and seen[canon] != action:
            raise DesktopError(f"conflicting keybind {canon}: "
                               f"{seen[canon]!r} vs {action!r}")
        seen[canon] = action
        out[canon] = action
    return dict(sorted(out.items()))


def session_plan(settings):
    """Pure: validate session settings; render deterministic env lines."""
    stype = settings.get("type", "wayland")
    if stype not in ("wayland", "tty"):
        raise DesktopError(f"bad session type: {stype!r}")
    idle = settings.get("idle_delay", 600)
    if not isinstance(idle, int) or isinstance(idle, bool) or not (0 <= idle <= 86400):
        raise DesktopError(f"bad idle delay: {idle!r}")
    env = settings.get("env", {})
    if not isinstance(env, dict):
        raise DesktopError("env must be an object")
    for key, value in env.items():
        if not _ENVKEY_RE.match(key):
            raise DesktopError(f"bad env key: {key!r}")
        if not isinstance(value, str):
            raise DesktopError(f"env {key}: value must be a string")
    lines = [f"XDG_SESSION_TYPE={stype}", f"SIGMA_IDLE_DELAY={idle}",
             f"SIGMA_LOCK_ON_IDLE={'1' if settings.get('lock_on_idle', True) else '0'}"]
    lines += [f"{k}={env[k]}" for k in sorted(env)]
    return {"type": stype, "idle_delay": idle, "lines": lines}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    for verb, help_ in (("outputs", "validate monitor configs"),
                        ("inputs", "validate input configs"),
                        ("keybinds", "validate keybind map"),
                        ("session", "validate session settings")):
        sp = sub.add_parser(verb, help=help_)
        sp.add_argument("spec", help="JSON spec file")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with open(args.spec, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
        if args.cmd == "outputs":
            for o in outputs(spec):
                print(f"{o['name']}: {o['width']}x{o['height']}@{o['refresh']:g} "
                      f"scale={o['scale']} pos={o['pos'][0]},{o['pos'][1]} "
                      f"{'on' if o['enabled'] else 'off'}")
        elif args.cmd == "inputs":
            for i in inputs(spec):
                extra = " ".join(f"{k}={v}" for k, v in sorted(i.items())
                                 if k not in ("name", "type"))
                print(f"{i['name']} ({i['type']}) {extra}".rstrip())
        elif args.cmd == "keybinds":
            for chord, action in keybinds(spec).items():
                print(f"{chord} = {action}")
        elif args.cmd == "session":
            for line in session_plan(spec)["lines"]:
                print(line)
        return 0
    except (DesktopError, OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    # outputs
    outs = outputs([
        {"name": "eDP-1", "mode": "2256x1504@60", "scale": 1.25, "pos": [0, 0]},
        {"name": "HDMI-A-1", "mode": "1920x1080@75", "pos": [2256, 0]},
    ])
    assert [o["name"] for o in outs] == ["HDMI-A-1", "eDP-1"]  # sorted by name
    by_name = {o["name"]: o for o in outs}
    assert by_name["eDP-1"]["width"] == 2256 and by_name["eDP-1"]["scale"] == 1.25
    assert by_name["HDMI-A-1"]["refresh"] == 75.0
    for bad_call in (
        lambda: outputs([{"name": "eDP-1", "mode": "1920"}]),
        lambda: outputs([{"name": "eDP-1", "mode": "1920x1080", "scale": 0.1}]),
        lambda: outputs([{"name": "eDP 1", "mode": "1920x1080"}]),
        lambda: outputs([{"name": "a", "mode": "1x1", "pos": [-1, 0]}]),
        lambda: outputs([{"name": "a", "mode": "1x1"},
                         {"name": "a", "mode": "1x1"}]),
        lambda: outputs([{"name": "a", "mode": "1x1", "enabled": False}]),
    ):
        try:
            bad_call()
        except DesktopError:
            pass
        else:
            raise AssertionError("expected DesktopError (outputs)")
    # inputs
    ins = inputs([
        {"name": "atkbd", "type": "keyboard", "layout": "de"},
        {"name": "synaptics", "type": "touchpad", "speed": 40, "tap": True},
    ])
    assert [i["name"] for i in ins] == ["atkbd", "synaptics"]
    assert ins[0]["layout"] == "de" and ins[1]["speed"] == 40
    for bad_call in (
        lambda: inputs([{"name": "x", "type": "keyboard", "layout": "US!"}]),
        lambda: inputs([{"name": "x", "type": "touchpad", "speed": 500}]),
        lambda: inputs([{"name": "x", "type": "modem"}]),
        lambda: inputs([{"name": "x", "type": "pointer"},
                        {"name": "x", "type": "pointer"}]),
    ):
        try:
            bad_call()
        except DesktopError:
            pass
        else:
            raise AssertionError("expected DesktopError (inputs)")
    # keybinds: canonicalization + conflict detection
    kb = keybinds({"super+t": "terminal", "alt+super+t": "task-manager",
                   "Ctrl+Alt+L": "lock"})
    assert kb["SUPER+T"] == "terminal"
    assert kb["SUPER+ALT+T"] == "task-manager"     # canonical mod order
    assert kb["CTRL+ALT+L"] == "lock"
    assert list(kb) == sorted(kb)                  # deterministic
    assert keybinds({"super+t": "terminal", "SUPER+T": "terminal"})["SUPER+T"] == "terminal"
    for bad_call in (
        lambda: keybinds({"super+t": "a", "alt+super+t": "b", "SUPER+ALT+t": "c"}),
        lambda: keybinds({"t": "terminal"}),
        lambda: keybinds({"meta+t": "x"}),            # unknown modifier
        lambda: keybinds({"super+super+t": "x"}),
        lambda: keybinds({"super+": "x"}),
        lambda: keybinds({"super+t": "  "}),
    ):
        try:
            bad_call()
        except DesktopError:
            pass
        else:
            raise AssertionError("expected DesktopError (keybinds)")
    # session
    sess = session_plan({"type": "wayland", "idle_delay": 300,
                         "env": {"MOZ_ENABLE_WAYLAND": "1", "THEME": "dark"}})
    assert sess["lines"][0] == "XDG_SESSION_TYPE=wayland"
    assert "SIGMA_IDLE_DELAY=300" in sess["lines"]
    assert sess["lines"][-1] == "THEME=dark"
    for bad_call in (
        lambda: session_plan({"type": "x11"}),
        lambda: session_plan({"idle_delay": -5}),
        lambda: session_plan({"idle_delay": 999999}),
        lambda: session_plan({"env": {"lowercase": "x"}}),
        lambda: session_plan({"env": {"OK": 5}}),
    ):
        try:
            bad_call()
        except DesktopError:
            pass
        else:
            raise AssertionError("expected DesktopError (session)")
    # CLI smoke through main()
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        raw_outs = [
            {"name": "eDP-1", "mode": "2256x1504@60", "scale": 1.25,
             "pos": [0, 0]},
            {"name": "HDMI-A-1", "mode": "1920x1080@75", "pos": [2256, 0]},
        ]
        for name, data in (("out.json", raw_outs), ("in.json", ins),
                           ("kb.json", kb), ("sess.json", {"type": "wayland"})):
            path = os.path.join(d, name)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        assert main(["outputs", os.path.join(d, "out.json")]) == 0
        assert main(["inputs", os.path.join(d, "in.json")]) == 0
        assert main(["keybinds", os.path.join(d, "kb.json")]) == 0
        assert main(["session", os.path.join(d, "sess.json")]) == 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
