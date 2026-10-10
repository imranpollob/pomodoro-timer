//! Validated desktop integrations.
use focus_core::service::TimerService;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{Emitter, Manager};

fn default_close_to_tray() -> bool {
    true
}

fn default_menu_bar_visible() -> bool {
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
    #[serde(default = "default_menu_bar_visible")]
    pub menu_bar_visible: bool,
    pub dock_hidden: bool,
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
            menu_bar_visible: true,
            dock_hidden: false,
        }
    }
}
impl Preferences {
    /// macOS keeps the app reachable: a hidden Dock icon requires the menu bar icon.
    /// Dropping the menu bar icon restores the Dock icon instead of stranding the app.
    fn normalized(mut self) -> Self {
        if !self.menu_bar_visible {
            self.dock_hidden = false;
        }
        self
    }
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
    pub platform: &'static str,
    pub notification_status: String,
    pub audio_status: String,
    pub power_status: String,
}

/// Applies Dock and menu-bar presence on macOS. Other platforms ignore these preferences.
/// Presence is cosmetic: a failed application never fails the saved preferences.
#[cfg(target_os = "macos")]
pub fn apply_macos_presence(app: &tauri::AppHandle, preferences: &Preferences) {
    if let Some(tray) = app.tray_by_id("focus-tray") {
        let _ = tray.set_visible(preferences.menu_bar_visible);
    }
    let _ = app.set_activation_policy(if preferences.dock_hidden {
        tauri::ActivationPolicy::Accessory
    } else {
        tauri::ActivationPolicy::Regular
    });
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
        let preferences = preferences.normalized();
        preferences.validate()?;
        Ok(Self {
            state: Mutex::new(DesktopState {
                revision: 0,
                preferences,
                platform: std::env::consts::OS,
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
    // Only the Windows power listener reports status today; macOS/Linux adapters will call this.
    #[cfg_attr(not(target_os = "windows"), allow(dead_code))]
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
        let preferences = preferences.normalized();
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
        #[cfg(target_os = "macos")]
        apply_macos_presence(app, &self.state.lock().unwrap().preferences);
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
    fn macos_presence_defaults_keep_old_profiles_reachable() {
        let stored: Preferences =
            serde_json::from_str(r#"{"volume":60,"theme":"dark","opacity_percent":100,"pinned":true,"notifications":false,"close_to_tray":true}"#)
                .unwrap();
        assert!(stored.menu_bar_visible);
        assert!(!stored.dock_hidden);
        assert!(Preferences::default().menu_bar_visible);
        assert!(!Preferences::default().dock_hidden);
    }
    #[test]
    fn dropping_menu_bar_restores_dock() {
        let hidden = Preferences {
            menu_bar_visible: false,
            dock_hidden: true,
            ..Preferences::default()
        };
        assert!(!hidden.normalized().dock_hidden);
        let visible = Preferences {
            menu_bar_visible: true,
            dock_hidden: true,
            ..Preferences::default()
        };
        assert!(visible.normalized().dock_hidden);
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
