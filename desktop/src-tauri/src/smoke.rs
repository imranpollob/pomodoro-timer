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
                serde_json::json!({"passed": true, "checks": ["main/compact rendered controls and real IPC", "finish dialog", "SQLite completion/checkpoint", "native pinning", "placement persistence/clamping", "desktop preference persistence", "Windows suspend/lock (Windows only)"]})
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
    ui_step(
        app,
        "main",
        "await until(() => document.querySelector('.timer-actions .primary')); document.querySelector('.timer-actions .primary').click(); await until(() => document.querySelector('.timer-actions .primary')?.textContent.includes('Pause'));",
    )?;
    ui_step(
        app,
        "compact",
        "await until(() => document.querySelector('.compact-action')?.getAttribute('aria-label') === 'Pause'); if (document.querySelectorAll('button').length !== 1) throw Error('Compact has extra controls'); document.querySelector('.compact-action').click(); await until(() => document.querySelector('.compact-action')?.getAttribute('aria-label') === 'Resume');",
    )?;
    let paused = service.snapshot()?;
    if paused.timer.status != "paused" || paused.timer.active_ms < 30 {
        return Err("Shared timer did not pause".into());
    }
    ui_step(
        app,
        "main",
        "await until(() => Array.from(document.querySelectorAll('.timer-actions button')).find(b => b.textContent.trim() === 'Finish')); Array.from(document.querySelectorAll('.timer-actions button')).find(b => b.textContent.trim() === 'Finish').click(); await until(() => document.querySelector('dialog')?.open); Array.from(document.querySelectorAll('dialog button')).find(b => b.textContent.trim() === 'Finish and save').click(); await until(() => !document.querySelector('dialog')?.open && document.querySelector('.timer-actions .primary')?.textContent.includes('Start'));",
    )?;
    let saved = service.snapshot()?;
    if saved.pending_save || saved.records.len() != 1 {
        return Err("Session did not persist exactly once".into());
    }
    service.command(Command::Toggle)?;
    #[cfg(windows)]
    {
        app.state::<power::PowerListener>().simulate_lock();
        let interrupted = service.snapshot()?;
        if interrupted.timer.status != "paused"
            || interrupted.interruption.as_deref() != Some("lock")
        {
            return Err("Windows lock broadcast did not pause the shared session".into());
        }
        service.command(Command::Toggle)?;
        app.state::<power::PowerListener>().simulate_suspend();
        if service.snapshot()?.interruption.as_deref() != Some("sleep") {
            return Err("Windows suspend broadcast did not pause the session".into());
        }
    }
    let checkpoint = service.command(Command::Pause)?;
    let profile = std::env::var_os("POMODORO_BETA_DATA_DIR")
        .map(std::path::PathBuf::from)
        .unwrap_or(app.path().app_data_dir().map_err(|e| e.to_string())?);
    let store = Store::open(&profile.join("prototype.sqlite3"))?;
    if store.records()?.len() != 1
        || store.load()?.view(u64::MAX).active_ms != checkpoint.timer.active_ms
    {
        return Err("SQLite checkpoint/record read-back disagreed".into());
    }
    let controls = app.state::<Controls>();
    let previous = controls.snapshot().preferences;
    let mut candidate = previous.clone();
    candidate.pinned = false;
    controls.save(app, candidate.clone())?;
    let compact = app.get_webview_window("compact").ok_or("Missing compact")?;
    if compact.is_always_on_top().map_err(|e| e.to_string())? {
        return Err("Pinning did not update the native window".into());
    }
    ui_step(
        app,
        "compact",
        "await until(() => getComputedStyle(document.querySelector('.compact-time')).fontSize === '25px');",
    )?;
    geometry::ensure_visible(&compact, Some((1_000_000, 1_000_000)))?;
    app.state::<geometry::GeometryService>()
        .observe(&compact.as_ref().window());
    app.state::<geometry::GeometryService>().flush()?;
    if store.preference("windows")?.is_none() || store.preference("desktop")?.is_none() {
        return Err("Desktop preferences or placement were not saved".into());
    }
    controls.save(app, previous)?;
    ui_step(
        app,
        "main",
        "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Settings').click(); await until(() => Array.from(document.querySelectorAll('label')).find(l => l.textContent.includes('Play a completion tone'))?.querySelector('input'));",
    )?;
    dispatch_menu(app, "sound");
    ui_step(
        app,
        "main",
        "await until(() => Array.from(document.querySelectorAll('label')).find(l => l.textContent.includes('Play a completion tone'))?.querySelector('input')?.checked === false);",
    )?;
    dispatch_menu(app, "sound");
    app.state::<audio::AudioService>().play(0)?;
    Ok(())
}

fn ui_step(app: &tauri::AppHandle, label: &str, script: &str) -> Result<(), String> {
    use tauri::Listener;
    static STEP: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let name = format!(
        "native-smoke-ui-{}",
        STEP.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    );
    let (send, receive) = std::sync::mpsc::channel();
    let listener = app.listen(name.clone(), move |event| {
        let _ = send.send(event.payload().to_owned());
    });
    let window = app
        .get_webview_window(label)
        .ok_or("Missing native webview")?;
    let javascript = format!(
        r#"(async () => {{
        const until = async predicate => {{ const end = Date.now() + 8000; while (!predicate()) {{ if (Date.now() > end) throw Error('Rendered UI timed out'); await new Promise(r => setTimeout(r, 50)); }} }};
        let result = 'ok'; try {{ {script} }} catch (e) {{ result = String(e); }}
        await window.__TAURI_INTERNALS__.invoke('plugin:event|emit', {{ event: '{name}', payload: result }});
    }})();"#
    );
    window.eval(javascript).map_err(|e| e.to_string())?;
    let result = receive
        .recv_timeout(Duration::from_secs(12))
        .map_err(|e| format!("{label} native UI: {e}"));
    app.unlisten(listener);
    let payload = result?;
    if serde_json::from_str::<String>(&payload).map_err(|e| e.to_string())? != "ok" {
        return Err(payload);
    }
    Ok(())
}
