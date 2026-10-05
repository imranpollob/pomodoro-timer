use focus_core::{
    Command,
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

#[derive(Clone, serde::Serialize)]
struct DesktopInfo {
    os: String,
    arch: String,
    tray: String,
    data_directory: String,
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
    tauri::async_runtime::spawn_blocking(move || service.snapshot())
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn timer_command(
    command: Command,
    service: State<'_, TimerService>,
) -> Result<Snapshot, String> {
    let service = service.inner().clone();
    tauri::async_runtime::spawn_blocking(move || service.command(command))
        .await
        .map_err(|e| e.to_string())?
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
fn desktop_info(info: State<'_, DesktopInfo>) -> DesktopInfo {
    info.inner().clone()
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
    geometry::ensure_visible(&compact, None)?;
    compact.set_focus().map_err(|e| e.to_string())?;
    // Main stays available: a missing Linux tray never strands the app.
    Ok(())
}

#[tauri::command]
fn resize_compact(app: tauri::AppHandle, width: f64, height: f64) -> Result<(), String> {
    if !(200.0..=1200.0).contains(&width) || !(44.0..=300.0).contains(&height) {
        return Err("Invalid compact size".into());
    }
    let window = app
        .get_webview_window("compact")
        .ok_or("Compact window unavailable")?;
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
async fn test_sound(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let volume = app.state::<Controls>().snapshot().preferences.volume;
        let result = app.state::<audio::AudioService>().play(volume);
        app.state::<Controls>().audio_status(&app, &result);
        result
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn stop_sound(audio: State<'_, audio::AudioService>) {
    audio.stop();
}

#[tauri::command]
async fn compact_menu(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
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
    let finish = MenuItem::with_id(
        &app,
        "finish",
        "Finish session / Skip break",
        snapshot.timer.status != "idle" && !snapshot.pending_save,
        None::<&str>,
    )
    .map_err(|e| e.to_string())?;
    let exit =
        MenuItem::with_id(&app, "exit", "Exit", true, None::<&str>).map_err(|e| e.to_string())?;
    let menu = Menu::with_items(&app, &[&open, &pin, &sound, &finish, &exit])
        .map_err(|e| e.to_string())?;
    window.popup_menu(&menu).map_err(|e| e.to_string())
}

#[tauri::command]
fn test_notification(app: tauri::AppHandle) -> Result<(), String> {
    app.notification()
        .builder()
        .title("Pomodoro Beta")
        .body("Your desktop notification test.")
        .show()
        .map_err(|e| e.to_string())
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
        _ => {}
    }
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            let _ = show_main(app);
        }))
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    if let Some(controls) = app.try_state::<Controls>() {
                        controls.handle(app, shortcut, event.state());
                    }
                })
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            get_snapshot,
            timer_command,
            desktop_info,
            open_main,
            open_compact,
            resize_compact,
            set_pin,
            compact_menu,
            test_notification,
            get_desktop_state,
            save_desktop_preferences,
            test_sound,
            stop_sound,
            report_desktop_error
        ])
        .setup(|app| {
            let path = std::env::var_os("POMODORO_BETA_DATA_DIR")
                .map(std::path::PathBuf::from)
                .unwrap_or(app.path().app_data_dir()?);
            std::fs::create_dir_all(&path)?;
            let publish = app.handle().clone();
            let notification = app.handle().clone();
            let service = TimerService::spawn(
                Store::open(&path.join("prototype.sqlite3"))?,
                Arc::new(SystemClock::default()),
                move |snapshot| {
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
            let exit = MenuItem::with_id(app, "exit", "Exit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &compact, &toggle, &exit])?;
            let tray = TrayIconBuilder::with_id("focus-tray")
                .menu(&menu)
                .tooltip("Pomodoro Beta")
                .icon(app.default_window_icon().ok_or("Missing app icon")?.clone())
                .build(app);
            app.manage(DesktopInfo {
                os: std::env::consts::OS.into(),
                arch: std::env::consts::ARCH.into(),
                tray: match tray {
                    Ok(_) => "Created; visibility must be checked on this desktop".into(),
                    Err(e) => format!("Unavailable: {e}"),
                },
                data_directory: path.to_string_lossy().into_owned(),
            });
            #[cfg(feature = "smoke-test")]
            smoke::start(app.handle().clone());
            Ok(())
        })
        .on_menu_event(|app, event| menu_action(app, event.id.as_ref()))
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
                if window.label() == "compact" {
                    let _ = window.hide();
                    let _ = show_main(window.app_handle());
                } else {
                    request_exit(window.app_handle());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Unable to start Pomodoro Beta; existing data was left intact");
    app.run(|app, event| {
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
