use anyhow::Result;
use sigmaos_component::{Component, ComponentStatus, Config, Desktop, Service, DesktopConfig};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_desktop_lifecycle_aaa() -> Result<()> {
        let config = Config::default();
        let mut d = Desktop::new(config);
        
        assert_eq!(d.status(), ComponentStatus::Stopped);
        d.initialize()?;
        d.start()?;
        assert_eq!(d.status(), ComponentStatus::Running);
        d.stop()?;
        assert_eq!(d.status(), ComponentStatus::Stopped);
        Ok(())
    }

    #[test]
    fn test_service_lifecycle_aaa() -> Result<()> {
        let config = DesktopConfig::default();
        let mut service = Service::new(config);
        assert!(!service.is_running());
        service.start()?;
        assert!(service.is_running());
        assert!(service.start().is_err());
        service.stop()?;
        assert!(!service.is_running());
        assert!(service.stop().is_err());
        Ok(())
    }
}
