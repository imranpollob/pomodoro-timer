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
            Ok(snapshot) if !snapshot.pending_save => app.exit(0),
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
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn set_pin(app: tauri::AppHandle, pinned: bool) -> Result<(), String> {
    app.get_webview_window("compact")
        .ok_or("Compact window unavailable")?
        .set_always_on_top(pinned)
        .map_err(|e| e.to_string())
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
            let _ = app.state::<TimerService>().command(Command::Toggle);
        }
        "finish" => {
            let _ = show_main(app);
            let _ = app.emit("finish-requested", ());
        }
        "pin" => {
            if let Some(w) = app.get_webview_window("compact") {
                let _ = w.set_always_on_top(!w.is_always_on_top().unwrap_or(false));
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
        .invoke_handler(tauri::generate_handler![
            get_snapshot,
            timer_command,
            desktop_info,
            open_main,
            open_compact,
            resize_compact,
            set_pin,
            compact_menu,
            test_notification
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
                    let _ = notification.emit("session-completed", &record);
                    let _ = notification
                        .notification()
                        .builder()
                        .title("Session complete")
                        .body("Your next session is ready when you are.")
                        .show();
                },
            )?;
            app.manage(service);
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
