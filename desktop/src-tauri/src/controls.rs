//! Validated desktop integrations.
use focus_core::service::TimerService;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{Emitter, Manager};

fn default_close_to_tray() -> bool {
    true
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Preferences {
    pub volume: u8,
    pub theme: String,
    pub opacity_percent: u8,
    pub pinned: bool,
    pub notifications: bool,
    #[serde(default = "default_close_to_tray")]
    pub close_to_tray: bool,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            volume: 60,
            theme: "dark".into(),
            opacity_percent: 100,
            pinned: true,
            notifications: true,
            close_to_tray: true,
        }
    }
}
impl Preferences {
    pub fn validate(&self) -> Result<(), String> {
        if self.volume > 100
            || !(60..=100).contains(&self.opacity_percent)
            || !["dark", "light"].contains(&self.theme.as_str())
        {
            return Err(
                "Choose a supported appearance, 60–100% compact opacity and volume 0–100.".into(),
            );
        }
        Ok(())
    }
}

#[derive(Clone, Serialize)]
pub struct DesktopState {
    pub revision: u64,
    pub preferences: Preferences,
    pub notification_status: String,
    pub audio_status: String,
    pub power_status: String,
}
pub struct Controls {
    state: Mutex<DesktopState>,
    save_lock: Mutex<()>,
}
impl Controls {
    pub fn load(service: &TimerService) -> Result<Self, String> {
        let preferences: Preferences = service
            .preference("desktop")?
            .map(|raw| serde_json::from_str(&raw))
            .transpose()
            .map_err(|e| format!("Invalid desktop preferences: {e}"))?
            .unwrap_or_default();
        preferences.validate()?;
        Ok(Self {
            state: Mutex::new(DesktopState {
                revision: 0,
                preferences,
                notification_status:
                    "Delivery is controlled by OS notification settings; test the installed app."
                        .into(),
                audio_status: "Native playback; test your output device.".into(),
                power_status: "Native suspend/lock adapter not available on this platform yet."
                    .into(),
            }),
            save_lock: Mutex::new(()),
        })
    }
    pub fn snapshot(&self) -> DesktopState {
        self.state.lock().unwrap().clone()
    }
    pub fn power_status(&self, value: String) {
        let mut state = self.state.lock().unwrap();
        state.power_status = value;
        state.revision += 1;
    }
    pub fn audio_status(&self, app: &tauri::AppHandle, result: &Result<(), String>) {
        {
            let mut state = self.state.lock().unwrap();
            state.audio_status = match result {
                Ok(()) => "Playback accepted by the output device.".into(),
                Err(e) => e.clone(),
            };
            state.revision += 1;
        }
        self.publish(app);
    }
    fn publish(&self, app: &tauri::AppHandle) {
        let _ = app.emit("desktop-state", self.snapshot());
    }
    pub fn initialize(&self, app: &tauri::AppHandle) {
        let preferences = self.snapshot().preferences;
        if let Some(window) = app.get_webview_window("compact")
            && let Err(error) = window.set_always_on_top(preferences.pinned)
        {
            crate::report_error(app, &error.to_string());
        }
    }
    pub fn save(
        &self,
        app: &tauri::AppHandle,
        preferences: Preferences,
    ) -> Result<DesktopState, String> {
        let _save = self.save_lock.lock().unwrap();
        preferences.validate()?;
        let previous = self.snapshot().preferences;
        let compact = app
            .get_webview_window("compact")
            .ok_or("Compact window unavailable")?;
        compact
            .set_always_on_top(preferences.pinned)
            .map_err(|e| e.to_string())?;
        if let Err(error) = app.state::<TimerService>().save_preference(
            "desktop",
            &serde_json::to_string(&preferences).map_err(|e| e.to_string())?,
        ) {
            let _ = compact.set_always_on_top(previous.pinned);
            return Err(error);
        }
        {
            let mut state = self.state.lock().unwrap();
            state.preferences = preferences;
            state.revision += 1;
        }
        self.publish(app);
        Ok(self.snapshot())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn invalid_settings_are_rejected() {
        let mut p = Preferences::default();
        assert!(p.validate().is_ok());
        p.volume = 101;
        assert!(p.validate().is_err());
        p = Preferences::default();
        p.theme = "sepia".into();
        assert!(p.validate().is_err());
        p = Preferences::default();
        p.opacity_percent = 59;
        assert!(p.validate().is_err());
        p.opacity_percent = 100;
        assert!(p.validate().is_ok());
    }
    #[test]
    fn close_to_tray_defaults_on_for_old_profiles() {
        let stored: Preferences =
            serde_json::from_str(r#"{"volume":60,"theme":"dark","opacity_percent":100,"pinned":true,"notifications":false}"#)
                .unwrap();
        assert!(stored.close_to_tray);
        assert!(Preferences::default().close_to_tray);
        assert!(Preferences::default().notifications);
    }
}
