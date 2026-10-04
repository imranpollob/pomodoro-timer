//! Native IPC/persistence probe. This module is absent from normal builds.
use super::*;
use std::{
    collections::HashSet,
    sync::{Mutex, OnceLock},
    thread,
    time::{Duration, Instant},
};

static READY: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();
pub fn ready(label: &str) {
    if let Ok(mut ready) = READY.get_or_init(Mutex::default).lock() {
        ready.insert(label.to_owned());
    }
}

pub fn start(app: tauri::AppHandle) {
    let Some(report) = std::env::var_os("POMODORO_NATIVE_SMOKE_REPORT") else {
        return;
    };
    thread::spawn(move || {
        let result = probe(&app);
        let payload = match &result {
            Ok(()) => {
                serde_json::json!({"passed": true, "checks": ["main and compact IPC", "shared timer commands", "pause", "SQLite completion", "paused checkpoint"]})
            }
            Err(error) => serde_json::json!({"passed": false, "error": error}),
        };
        let written = std::fs::write(report, payload.to_string()).is_ok();
        app.exit(if result.is_ok() && written { 0 } else { 1 });
    });
}

fn probe(app: &tauri::AppHandle) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(30);
    loop {
        let ready = READY
            .get_or_init(Mutex::default)
            .lock()
            .map_err(|e| e.to_string())?;
        if ready.contains("main") && ready.contains("compact") {
            break;
        }
        if Instant::now() >= deadline {
            return Err(format!("Webview IPC readiness timed out: {ready:?}"));
        }
        drop(ready);
        thread::sleep(Duration::from_millis(50));
    }
    let service = app.state::<TimerService>();
    service.command(Command::Toggle)?;
    thread::sleep(Duration::from_millis(60));
    let paused = service.command(Command::Pause)?;
    if paused.timer.status != "paused" || paused.timer.active_ms < 30 {
        return Err("Shared timer did not pause".into());
    }
    let saved = service.command(Command::Finish)?;
    if saved.pending_save || saved.records.len() != 1 {
        return Err("Session did not persist exactly once".into());
    }
    service.command(Command::Toggle)?;
    let checkpoint = service.command(Command::Pause)?;
    let info = app.state::<DesktopInfo>();
    let store = Store::open(&std::path::Path::new(&info.data_directory).join("prototype.sqlite3"))?;
    if store.records()?.len() != 1
        || store.load()?.view(u64::MAX).active_ms != checkpoint.timer.active_ms
    {
        return Err("SQLite checkpoint/record read-back disagreed".into());
    }
    Ok(())
}
