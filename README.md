# SigmaOS Desktop

SigmaOS Desktop contains the desktop component of SigmaOS. The Rust crate
exposes desktop functionality through `sigmaos_desktop`; the repository also
includes a Python core validation suite under `tests/`.

## Build and run checks

The Rust crate depends on the sibling `SigmaOS-kernel` repository at
`../SigmaOS-kernel`. In a local checkout, place both repositories side by side
and run:

```sh
cargo build --release
cargo test --release
python3 -m unittest discover -s tests
```

GitHub Actions also checks out the private kernel repository. Configure the
repository secret `SIGMAOS_REPO_TOKEN` with read access to `SigmaOS-kernel` so
the workflow can resolve that path dependency.
