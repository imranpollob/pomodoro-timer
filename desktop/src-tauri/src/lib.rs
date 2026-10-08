use focus_core::{
    Command, Settings, Task,
    service::{Snapshot, SystemClock, TimerService},
    store::Store,
};
use std::sync::Arc;
use tauri::{
    Emitter, Manager, State,
    menu::{CheckMenuItem, Menu, MenuItem},
    tray::TrayIconBuilder,
};
use tauri_plugin_notification::NotificationExt;
mod audio;
mod controls;
mod geometry;
#[cfg(windows)]
mod power;
use controls::{Controls, DesktopState, Preferences};

fn report_error(app: &tauri::AppHandle, message: &str) {
    let _ = app.emit("desktop-error", message);
    let _ = show_main(app);
}
#[tauri::command]
fn report_desktop_error(app: tauri::AppHandle, message: String) {
    report_error(&app, &message.chars().take(2000).collect::<String>());
}

#[tauri::command]
async fn get_snapshot(
    service: State<'_, TimerService>,
    window: tauri::WebviewWindow,
) -> Result<Snapshot, String> {
    #[cfg(feature = "smoke-test")]
    smoke::ready(window.label());
    #[cfg(not(feature = "smoke-test"))]
    let _ = window;
    let service = service.inner().clone();
    eprintln!("DIAG2 get_snapshot entry");
    tauri::async_runtime::spawn_blocking(move || service.snapshot())
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn timer_command(
    command: Command,
    service: State<'_, TimerService>,
) -> Result<Snapshot, String> {
    eprintln!("DIAG2 timer_command entry tid={:?}", std::thread::current().id());
    let service = service.inner().clone();
    let out = tauri::async_runtime::spawn_blocking(move || {
        eprintln!("DIAG2 timer_command blocking-start");
        let r = service.command(command);
        eprintln!("DIAG2 timer_command blocking-done ok={}", r.is_ok());
        r
    })
    .await
    .map_err(|e| e.to_string())?;
    eprintln!("DIAG2 timer_command exit ok={}", out.is_ok());
    out
}

#[tauri::command]
async fn list_tasks(service: State<'_, TimerService>) -> Result<Vec<Task>, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.tasks())
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn create_task(title: String, service: State<'_, TimerService>) -> Result<Task, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.create_task(title))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn rename_task(
    id: String,
    title: String,
    service: State<'_, TimerService>,
) -> Result<Task, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.rename_task(id, title))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn complete_task(
    id: String,
    completed: bool,
    service: State<'_, TimerService>,
) -> Result<(), String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.complete_task(id, completed))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn delete_task(id: String, service: State<'_, TimerService>) -> Result<(), String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.delete_task(id))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn daily_totals(
    start_unix_ms: u64,
    end_unix_ms: u64,
    service: State<'_, TimerService>,
) -> Result<focus_core::store::DailyTotals, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.daily_totals(start_unix_ms, end_unix_ms))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn reset_reports(service: State<'_, TimerService>) -> Result<Snapshot, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.reset_reports())
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn report_records(
    start_unix_ms: u64,
    end_unix_ms: u64,
    service: State<'_, TimerService>,
) -> Result<Vec<focus_core::Record>, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.report_records(start_unix_ms, end_unix_ms))
        .await
        .map_err(|e| e.to_string())?
}

/// Size the Linux strip: GTK freezes a non-resizable window to its mapped size,
/// so the Linux window stays resizable (see tauri.linux.conf.json) and is
/// pinned to each target through min/max hints instead, keeping manual edge
/// resizing disabled while programmatic grows and shrinks keep working.
#[cfg(target_os = "linux")]
fn size_compact(window: &tauri::WebviewWindow, width: f64, height: f64) -> Result<(), String> {
    window
        .set_min_size(Some(tauri::LogicalSize::new(200.0, 44.0)))
        .map_err(|e| e.to_string())?;
    window
        .set_max_size(Some(tauri::LogicalSize::new(1200.0, 300.0)))
        .map_err(|e| e.to_string())?;
    window
        .set_size(tauri::LogicalSize::new(width, height))
        .map_err(|e| e.to_string())?;
    window
        .set_min_size(Some(tauri::LogicalSize::new(width, height)))
        .map_err(|e| e.to_string())?;
    window
        .set_max_size(Some(tauri::LogicalSize::new(width, height)))
        .map_err(|e| e.to_string())
}

fn show_main(app: &tauri::AppHandle) -> Result<(), String> {
    let main = app
        .get_webview_window("main")
        .ok_or("Main window unavailable")?;
    main.show().map_err(|e| e.to_string())?;
    main.unminimize().map_err(|e| e.to_string())?;
    main.set_focus().map_err(|e| e.to_string())
}

fn request_exit(app: &tauri::AppHandle) {
    let app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let service = app.state::<TimerService>();
        match service.command(Command::Pause) {
            Ok(snapshot) if !snapshot.pending_save => {
                if let Err(error) = app.state::<geometry::GeometryService>().flush() {
                    report_error(&app, &format!("Could not save window placement: {error}"));
                } else {
                    app.exit(0);
                }
            }
            _ => {
                let _ = show_main(&app);
            }
        }
    });
}

#[tauri::command]
fn open_main(app: tauri::AppHandle) -> Result<(), String> {
    show_main(&app)
}

#[tauri::command]
fn open_compact(app: tauri::AppHandle) -> Result<(), String> {
    let compact = app
        .get_webview_window("compact")
        .ok_or("Compact window unavailable")?;
    compact.show().map_err(|e| e.to_string())?;
    #[cfg(target_os = "linux")]
    {
        // Re-apply the persisted size now that the strip is mapped.
        let (width, height) = app
            .state::<TimerService>()
            .preference("windows")
            .map(|raw| geometry::compact_size_from_pref(raw.as_deref()))
            .unwrap_or((200.0, 44.0));
        size_compact(&compact, width, height)?;
    }
    let _ = app.emit("compact-shown", ());
    geometry::ensure_visible(&compact, None)?;
    compact.set_focus().map_err(|e| e.to_string())?;
    // Main stays available: a missing Linux tray never strands the app.
    Ok(())
}

#[tauri::command]
fn close_compact(app: tauri::AppHandle) -> Result<(), String> {
    app.get_webview_window("compact")
        .ok_or("Compact window unavailable")?
        .hide()
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn resize_compact(app: tauri::AppHandle, width: f64, height: f64) -> Result<(), String> {
    eprintln!("DIAG2 resize_compact {width}x{height}");
    if !(200.0..=1200.0).contains(&width) || !(44.0..=300.0).contains(&height) {
        return Err("Invalid compact size".into());
    }
    let window = app
        .get_webview_window("compact")
        .ok_or("Compact window unavailable")?;
    #[cfg(target_os = "linux")]
    size_compact(&window, width, height)?;
    #[cfg(not(target_os = "linux"))]
    window
        .set_size(tauri::LogicalSize::new(width, height))
        .map_err(|e| e.to_string())?;
    geometry::ensure_visible(&window, None)
}

#[tauri::command]
async fn set_pin(app: tauri::AppHandle, pinned: bool) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let controls = app.state::<Controls>();
        let mut preferences = controls.snapshot().preferences;
        preferences.pinned = pinned;
        controls.save(&app, preferences).map(|_| ())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn timer_defaults() -> Settings {
    Settings::default()
}

#[tauri::command]
fn desktop_defaults() -> Preferences {
    Preferences::default()
}

#[tauri::command]
fn get_desktop_state(controls: State<'_, Controls>) -> DesktopState {
    controls.snapshot()
}

#[tauri::command]
async fn save_desktop_preferences(
    app: tauri::AppHandle,
    preferences: Preferences,
) -> Result<DesktopState, String> {
    tauri::async_runtime::spawn_blocking(move || app.state::<Controls>().save(&app, preferences))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn compact_menu(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
    eprintln!("DIAG2 compact_menu entry");
    let service = app.state::<TimerService>().inner().clone();
    let snapshot = tauri::async_runtime::spawn_blocking(move || service.snapshot())
        .await
        .map_err(|e| e.to_string())??;
    let open = MenuItem::with_id(&app, "open", "Open main window", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let pin = CheckMenuItem::with_id(
        &app,
        "pin",
        "Always on top",
        true,
        window.is_always_on_top().map_err(|e| e.to_string())?,
        None::<&str>,
    )
    .map_err(|e| e.to_string())?;
    let sound = CheckMenuItem::with_id(
        &app,
        "sound",
        "Sound",
        !snapshot.pending_save,
        snapshot.timer.settings.sound_enabled,
        None::<&str>,
    )
    .map_err(|e| e.to_string())?;
    let close = MenuItem::with_id(
        &app,
        "close-compact",
        "Close compact timer",
        true,
        None::<&str>,
    )
    .map_err(|e| e.to_string())?;
    let menu = Menu::with_items(&app, &[&close, &open, &pin, &sound]).map_err(|e| e.to_string())?;
    eprintln!("DIAG2 compact_menu popup start");
    let out = window.popup_menu(&menu).map_err(|e| e.to_string());
    eprintln!("DIAG2 compact_menu popup done ok={}", out.is_ok());
    out
}

fn menu_action(app: &tauri::AppHandle, id: &str) {
    let app = app.clone();
    let id = id.to_owned();
    tauri::async_runtime::spawn_blocking(move || dispatch_menu(&app, &id));
}

fn dispatch_menu(app: &tauri::AppHandle, id: &str) {
    match id {
        "open" => {
            let _ = show_main(app);
        }
        "compact" => {
            let _ = open_compact(app.clone());
        }
        "toggle" => {
            if let Err(error) = app.state::<TimerService>().command(Command::Toggle) {
                report_error(app, &error);
            }
        }
        "finish" => {
            let _ = show_main(app);
            let _ = app.emit("finish-requested", ());
        }
        "pin" => {
            let controls = app.state::<Controls>();
            let mut preferences = controls.snapshot().preferences;
            preferences.pinned = !preferences.pinned;
            if let Err(error) = controls.save(app, preferences) {
                report_error(app, &error);
            }
        }
        "sound" => {
            let service = app.state::<TimerService>();
            if let Ok(snapshot) = service.snapshot() {
                let mut settings = snapshot.timer.settings;
                settings.sound_enabled = !settings.sound_enabled;
                let _ = service.command(Command::Configure { settings });
            }
        }
        "exit" => request_exit(app),
        "close-compact" => {
            if let Some(compact) = app.get_webview_window("compact") {
                let _ = compact.hide();
            }
        }
        _ => {}
    }
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            let _ = show_main(app);
        }))
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            get_snapshot,
            timer_command,
            list_tasks,
            create_task,
            rename_task,
            complete_task,
            delete_task,
            daily_totals,
            report_records,
            reset_reports,
            open_main,
            open_compact,
            close_compact,
            resize_compact,
            set_pin,
            compact_menu,
            get_desktop_state,
            save_desktop_preferences,
            timer_defaults,
            desktop_defaults,
            report_desktop_error
        ])
        .setup(|app| {
            let path = std::env::var_os("POMODORO_BETA_DATA_DIR")
                .map(std::path::PathBuf::from)
                .unwrap_or(app.path().app_data_dir()?);
            std::fs::create_dir_all(&path)?;
            let publish = app.handle().clone();
            let publish_log = std::sync::Arc::new(std::sync::atomic::AtomicU64::new(0));
            let publish_count = publish_log.clone();
            let notification = app.handle().clone();
            let service = TimerService::spawn(
                Store::open(&path.join("prototype.sqlite3"))?,
                Arc::new(SystemClock::default()),
                move |snapshot| {
                    let n = publish_count.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    eprintln!(
                        "DIAG_PUBLISH n={n} rev={} status={} active_ms={}",
                        snapshot.revision, snapshot.timer.status, snapshot.timer.active_ms
                    );
                    let _ = publish.emit("timer-state", &snapshot);
                    if snapshot.pending_save {
                        let _ = show_main(&publish);
                    }
                },
                move |record| {
                    let app = notification.clone();
                    tauri::async_runtime::spawn_blocking(move || {
                        let _ = app.emit("session-completed", &record);
                        let controls = app.state::<Controls>();
                        let preferences = controls.snapshot().preferences;
                        if app
                            .state::<TimerService>()
                            .snapshot()
                            .is_ok_and(|s| s.timer.settings.sound_enabled)
                        {
                            let result =
                                app.state::<audio::AudioService>().play(preferences.volume);
                            controls.audio_status(&app, &result);
                            if let Err(error) = result {
                                report_error(&app, &error);
                            }
                        }
                        if preferences.notifications
                            && let Err(error) = app
                                .notification()
                                .builder()
                                .title("Session complete")
                                .body("Your next session is ready when you are.")
                                .show()
                        {
                            report_error(&app, &error.to_string());
                        }
                    });
                },
            )?;
            let controls = Controls::load(&service)?;
            let (geometry, placements) = geometry::GeometryService::start(service.clone())?;
            app.manage(controls);
            app.manage(audio::AudioService::start()?);
            app.manage(geometry);
            app.manage(service);
            for (label, placement) in placements {
                if let Some(window) = app.get_webview_window(&label) {
                    geometry::restore(&window, &placement)?;
                }
            }
            app.state::<Controls>().initialize(app.handle());
            #[cfg(windows)]
            match power::PowerListener::start(
                app.handle().clone(),
                app.state::<TimerService>().inner().clone(),
            ) {
                Ok(listener) => {
                    app.manage(listener);
                    app.state::<Controls>().power_status(
                        "Windows suspend/lock listener active; interrupted sessions stay paused."
                            .into(),
                    );
                }
                Err(error) => app.state::<Controls>().power_status(error),
            }
            let open = MenuItem::with_id(app, "open", "Open Pomodoro", true, None::<&str>)?;
            let compact = MenuItem::with_id(app, "compact", "Compact timer", true, None::<&str>)?;
            let toggle =
                MenuItem::with_id(app, "toggle", "Start / Pause / Resume", true, None::<&str>)?;
            let quit_label = if cfg!(target_os = "macos") {
                "Quit"
            } else {
                "Exit"
            };
            let exit = MenuItem::with_id(app, "exit", quit_label, true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &compact, &toggle, &exit])?;
            // Tray visibility varies by desktop; the main window stays available when it is missing.
            let _ = TrayIconBuilder::with_id("focus-tray")
                .menu(&menu)
                .tooltip("Pomodoro")
                .icon(app.default_window_icon().ok_or("Missing app icon")?.clone())
                .build(app);
            #[cfg(target_os = "macos")]
            controls::apply_macos_presence(
                app.handle(),
                &app.state::<Controls>().snapshot().preferences,
            );
            #[cfg(feature = "smoke-test")]
            smoke::start(app.handle().clone());
            Ok(())
        })
        .on_menu_event(|app, event| menu_action(app, event.id.as_ref()))
        .on_tray_icon_event(|tray, event| {
            if matches!(
                event,
                tauri::tray::TrayIconEvent::Click {
                    button: tauri::tray::MouseButton::Left,
                    ..
                }
            ) {
                let _ = show_main(tray.app_handle());
            }
        })
        .on_window_event(|window, event| {
            if matches!(
                event,
                tauri::WindowEvent::Moved(_) | tauri::WindowEvent::Resized(_)
            ) && let Some(geometry) =
                window.app_handle().try_state::<geometry::GeometryService>()
            {
                geometry.observe(window);
            }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                // macOS closes windows without quitting; quitting stays on Cmd+Q and Quit.
                #[cfg(target_os = "macos")]
                let hide = true;
                #[cfg(not(target_os = "macos"))]
                let hide = window.label() == "compact"
                    || window
                        .app_handle()
                        .try_state::<Controls>()
                        .is_some_and(|controls| controls.snapshot().preferences.close_to_tray);
                if hide {
                    let _ = window.hide();
                } else {
                    request_exit(window.app_handle());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Unable to start Pomodoro; existing data was left intact");
    app.run(|app, event| {
        // Dock-icon clicks reopen the main window when it is hidden.
        #[cfg(target_os = "macos")]
        if matches!(&event, tauri::RunEvent::Reopen { .. }) {
            let _ = show_main(app);
        }
        if let tauri::RunEvent::ExitRequested {
            code: None, api, ..
        } = event
        {
            api.prevent_exit();
            request_exit(app);
        }
    });
}

#[cfg(feature = "smoke-test")]
mod smoke;
