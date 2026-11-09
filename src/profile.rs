//! Desktop profile manifest: loads `desktop-profile.toml` and validates it.

use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct DesktopProfile {
    pub profile: ProfileMeta,
    pub session: Session,
    pub components: Components,
    #[serde(default)]
    pub optional: Optional,
    #[serde(default)]
    pub defaults: Defaults,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ProfileMeta {
    pub name: String,
    pub version: String,
    #[serde(default)]
    pub description: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Session {
    pub compositor: String,
    #[serde(default)]
    pub shell: Vec<String>,
    pub portal: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Components {
    #[serde(default)]
    pub core: Vec<String>,
    #[serde(default)]
    pub apps: Vec<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Optional {
    #[serde(default)]
    pub media: Vec<String>,
    #[serde(default)]
    pub development: Vec<String>,
    #[serde(default)]
    pub accessibility: Vec<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Defaults {
    #[serde(default)]
    pub keymap: String,
    #[serde(default)]
    pub autostart_shell: bool,
    #[serde(default)]
    pub night_light_default: bool,
    #[serde(default)]
    pub animations: bool,
}

impl DesktopProfile {
    /// Load and parse the profile from a TOML file.
    pub fn from_file(path: impl AsRef<Path>) -> Result<Self, String> {
        let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        toml::from_str(&text).map_err(|e| e.to_string())
    }

    /// Load the profile shipped inside this crate (`desktop-profile.toml`).
    pub fn bundled() -> Result<Self, String> {
        Self::from_file(concat!(env!("CARGO_MANIFEST_DIR"), "/desktop-profile.toml"))
    }

    /// Every package the default install must pull, deduplicated, in order:
    /// compositor deps → core components → apps.
    pub fn required_packages(&self) -> Vec<String> {
        let mut pkgs: Vec<String> = Vec::new();
        pkgs.push(self.session.compositor.clone());
        pkgs.extend(self.session.shell.iter().cloned());
        pkgs.push(self.session.portal.clone());
        pkgs.extend(self.components.core.iter().cloned());
        pkgs.extend(self.components.apps.iter().cloned());
        pkgs.sort();
        pkgs.dedup();
        pkgs
    }

    /// Validate structural invariants (fail-fast).
    pub fn validate(&self) -> Result<(), String> {
        if self.profile.name.is_empty() {
            return Err("profile name empty".into());
        }
        if self.session.compositor.is_empty() || self.session.portal.is_empty() {
            return Err("session compositor/portal missing".into());
        }
        if self.components.core.is_empty() {
            return Err("no core components".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // AAA: bundled profile loads, validates, yields non-empty package list.
    #[test]
    fn bundled_profile_loads() {
        let p = DesktopProfile::bundled().unwrap();
        p.validate().unwrap();
        let pkgs = p.required_packages();
        assert!(pkgs.contains(&"hyprland".to_string()));
        assert!(pkgs.contains(&"sigmaos-desktop".to_string()));
        assert!(pkgs.len() > 5);
    }

    // AAA: required_packages is deduplicated and sorted.
    #[test]
    fn packages_dedup_sorted() {
        let p = DesktopProfile::bundled().unwrap();
        let pkgs = p.required_packages();
        let mut sorted = pkgs.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(pkgs, sorted);
    }

    // AAA: malformed toml fails with error not panic.
    #[test]
    fn bad_toml_errors() {
        let tmp = std::env::temp_dir().join("bad-profile.toml");
        std::fs::write(&tmp, "not = [valid").unwrap();
        assert!(DesktopProfile::from_file(&tmp).is_err());
        std::fs::remove_file(&tmp).ok();
    }
}
