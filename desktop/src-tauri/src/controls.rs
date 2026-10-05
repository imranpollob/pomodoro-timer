//! Validated, opt-in desktop integrations. Failed registration keeps previous bindings.
use focus_core::service::TimerService;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Preferences {
    pub volume: u8,
    pub text_scale: u16,
    pub pinned: bool,
    pub notifications: bool,
    pub shortcuts_enabled: bool,
    pub timer_shortcut: String,
    pub open_shortcut: String,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            volume: 60,
            text_scale: 100,
            pinned: true,
            notifications: false,
            shortcuts_enabled: false,
            timer_shortcut: "CommandOrControl+Alt+Space".into(),
            open_shortcut: "CommandOrControl+Alt+F".into(),
        }
    }
}
impl Preferences {
    pub fn validate(&self) -> Result<Vec<Shortcut>, String> {
        if self.volume > 100 || ![100, 125, 150, 200].contains(&self.text_scale) {
            return Err("Choose volume 0–100 and text scale 100, 125, 150 or 200%.".into());
        }
        let mut shortcuts = Vec::new();
        for value in [&self.timer_shortcut, &self.open_shortcut] {
            if value.len() > 100 {
                return Err("Shortcut is too long.".into());
            }
            let shortcut: Shortcut = value
                .parse()
                .map_err(|e| format!("Invalid shortcut: {e}"))?;
            if !shortcut
                .mods
                .intersects(Modifiers::CONTROL | Modifiers::ALT | Modifiers::SUPER)
            {
                return Err("Global shortcuts need Control, Alt or Command/Super.".into());
            }
            shortcuts.push(shortcut);
        }
        if shortcuts[0] == shortcuts[1] {
            return Err("Timer and open-window shortcuts must differ.".into());
        }
        Ok(if self.shortcuts_enabled {
            shortcuts
        } else {
            Vec::new()
        })
    }
}

#[derive(Clone, Serialize)]
pub struct DesktopState {
    pub revision: u64,
    pub preferences: Preferences,
    pub shortcuts: String,
    pub notification_status: String,
    pub audio_status: String,
    pub power_status: String,
}
pub struct Controls {
    state: Mutex<DesktopState>,
    registered: Mutex<Vec<Shortcut>>,
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
                shortcuts: "Disabled".into(),
                notification_status:
                    "Delivery is controlled by OS notification settings; test the installed app."
                        .into(),
                audio_status: "Native playback; test your output device.".into(),
                power_status: "Native suspend/lock adapter not available on this platform yet."
                    .into(),
            }),
            registered: Mutex::new(Vec::new()),
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
        let shortcuts = preferences.validate().unwrap_or_default();
        match register_new(app, &[], &shortcuts) {
            Ok(()) => {
                *self.registered.lock().unwrap() = shortcuts;
                self.state.lock().unwrap().shortcuts = if preferences.shortcuts_enabled {
                    "Registered"
                } else {
                    "Disabled"
                }
                .into();
            }
            Err(error) => {
                self.state.lock().unwrap().shortcuts =
                    format!("Unavailable: {error}. In-app Space remains available.");
            }
        }
    }
    pub fn save(
        &self,
        app: &tauri::AppHandle,
        preferences: Preferences,
    ) -> Result<DesktopState, String> {
        let _save = self.save_lock.lock().unwrap();
        let desired = preferences.validate()?;
        let previous = self.snapshot().preferences;
        let old = self.registered.lock().unwrap().clone();
        let compact = app
            .get_webview_window("compact")
            .ok_or("Compact window unavailable")?;
        register_new(app, &old, &desired)?;
        let changed: Vec<_> = desired
            .iter()
            .filter(|s| !old.contains(s))
            .copied()
            .collect();
        let save = || {
            compact
                .set_always_on_top(preferences.pinned)
                .map_err(|e| e.to_string())?;
            app.state::<TimerService>().save_preference(
                "desktop",
                &serde_json::to_string(&preferences).map_err(|e| e.to_string())?,
            )
        };
        if let Err(error) = save() {
            for shortcut in changed {
                let _ = app.global_shortcut().unregister(shortcut);
            }
            let _ = compact.set_always_on_top(previous.pinned);
            return Err(error);
        }
        // Persistence has committed before removing the old working bindings.
        let mut errors = Vec::new();
        let mut registered = desired.clone();
        for shortcut in old.iter().filter(|s| !desired.contains(s)) {
            if let Err(error) = app.global_shortcut().unregister(*shortcut) {
                errors.push(error.to_string());
                registered.push(*shortcut);
            }
        }
        *self.registered.lock().unwrap() = registered;
        {
            let mut state = self.state.lock().unwrap();
            state.preferences = preferences;
            state.revision += 1;
            state.shortcuts = if !errors.is_empty() {
                format!(
                    "Some old bindings could not be removed: {}",
                    errors.join("; ")
                )
            } else if desired.is_empty() {
                "Disabled".into()
            } else {
                "Registered".into()
            };
        }
        self.publish(app);
        Ok(self.snapshot())
    }
    pub fn handle(&self, app: &tauri::AppHandle, shortcut: &Shortcut, event: ShortcutState) {
        if event != ShortcutState::Pressed {
            return;
        }
        let preferences = self.snapshot().preferences;
        if !preferences.shortcuts_enabled {
            return;
        }
        if preferences.timer_shortcut.parse::<Shortcut>().ok().as_ref() == Some(shortcut) {
            crate::menu_action(app, "toggle");
        } else if preferences.open_shortcut.parse::<Shortcut>().ok().as_ref() == Some(shortcut) {
            crate::menu_action(app, "open");
        }
    }
}
fn register_new(
    app: &tauri::AppHandle,
    old: &[Shortcut],
    desired: &[Shortcut],
) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    if !desired.is_empty() && std::env::var("XDG_SESSION_TYPE").is_ok_and(|v| v == "wayland") {
        return Err("Global shortcuts need a Wayland portal adapter on this desktop. Use in-app Space for now.".into());
    }
    let mut added = Vec::new();
    for shortcut in desired.iter().filter(|s| !old.contains(s)) {
        if app.global_shortcut().is_registered(*shortcut) {
            for registered in added {
                let _ = app.global_shortcut().unregister(registered);
            }
            return Err("Shortcut is already registered. Previous settings were kept.".into());
        }
        if let Err(error) = app.global_shortcut().register(*shortcut) {
            for registered in added {
                let _ = app.global_shortcut().unregister(registered);
            }
            return Err(format!(
                "Shortcut unavailable or already in use: {error}. Previous settings were kept."
            ));
        }
        added.push(*shortcut);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn disabled_shortcuts_do_not_register_and_invalid_settings_are_rejected() {
        let mut p = Preferences::default();
        assert!(p.validate().unwrap().is_empty());
        p.shortcuts_enabled = true;
        assert_eq!(p.validate().unwrap().len(), 2);
        p.open_shortcut = p.timer_shortcut.clone();
        assert!(p.validate().is_err());
        p.open_shortcut = "Space".into();
        assert!(p.validate().is_err());
        p = Preferences::default();
        p.text_scale = 99;
        assert!(p.validate().is_err());
        p.text_scale = 200;
        p.volume = 101;
        assert!(p.validate().is_err());
    }
}
