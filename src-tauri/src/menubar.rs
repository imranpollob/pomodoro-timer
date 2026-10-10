//! macOS menu-bar countdown: the status item shows the running time instead of the app icon.
//!
//! The label is derived from timer snapshots only; the backend timer stays the single authority.
//! Idle shows the app icon so the item stays easy to find and never collapses to nothing.
use focus_core::{Phase, service::Snapshot};
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Display {
    /// `None` shows the app icon; `Some` replaces it with this text.
    pub title: Option<String>,
    pub tooltip: String,
}

fn clock(seconds: u64) -> String {
    let minutes = seconds / 60;
    let remainder = seconds % 60;
    if minutes >= 60 {
        format!("{}:{:02}:{remainder:02}", minutes / 60, minutes % 60)
    } else {
        format!("{minutes:02}:{remainder:02}")
    }
}

pub fn display(snapshot: &Snapshot) -> Display {
    let timer = &snapshot.timer;
    let phase = match timer.phase {
        Phase::Focus => "Focus",
        Phase::ShortBreak => "Short break",
        Phase::LongBreak => "Long break",
        Phase::Stopwatch => "Stopwatch",
    };
    if timer.status == "idle" {
        return Display {
            title: None,
            tooltip: "Pomodoro".into(),
        };
    }
    let time = clock(timer.display_seconds);
    let title = match (timer.status.as_str(), timer.phase) {
        // U+FE0E keeps the pause sign monochrome like the digits.
        ("paused", _) => format!("\u{23F8}\u{FE0E} {time}"),
        (_, Phase::ShortBreak | Phase::LongBreak) => format!("Break {time}"),
        _ => time,
    };
    let task = timer
        .active_task
        .as_ref()
        .map_or(String::new(), |task| format!(" · {}", task.title));
    Display {
        title: Some(title),
        tooltip: format!("{phase} · {}{task}", timer.status),
    }
}

#[derive(Default)]
struct Slot {
    requested: Option<Display>,
    pending: Option<Display>,
    busy: bool,
}

/// Applies label changes off the timer thread. Native tray calls wait for the main thread, which
/// can sit inside a modal menu, so the timer service must never block on them. Updates coalesce
/// to the latest label and are applied in order by a single worker.
#[derive(Default, Clone)]
pub struct MenuBarTime {
    slot: Arc<Mutex<Slot>>,
}

impl MenuBarTime {
    /// Queues `display` unless it is already the latest requested label.
    fn submit(&self, display: Display) -> bool {
        let mut slot = self.slot.lock().unwrap_or_else(|e| e.into_inner());
        if slot.requested.as_ref() == Some(&display) {
            return false;
        }
        slot.requested = Some(display.clone());
        slot.pending = Some(display);
        !std::mem::replace(&mut slot.busy, true)
    }

    fn next(&self) -> Option<Display> {
        let mut slot = self.slot.lock().unwrap_or_else(|e| e.into_inner());
        let next = slot.pending.take();
        if next.is_none() {
            slot.busy = false;
        }
        next
    }
}

#[cfg(target_os = "macos")]
pub fn sync(app: &tauri::AppHandle, snapshot: &Snapshot) {
    use tauri::Manager;
    let Some(menubar) = app.try_state::<MenuBarTime>() else {
        return;
    };
    let menubar = menubar.inner().clone();
    if !menubar.submit(display(snapshot)) {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        while let Some(next) = menubar.next() {
            apply(&app, &next);
        }
    });
}

#[cfg(target_os = "macos")]
fn apply(app: &tauri::AppHandle, display: &Display) {
    let Some(tray) = app.tray_by_id("focus-tray") else {
        return;
    };
    // Cosmetic: a failed native update never affects the timer. Text goes in before the icon
    // leaves, so the item is never empty (an empty item cannot be clicked).
    let _ = tray.set_title(display.title.as_deref());
    let _ = tray.set_icon(match display.title {
        Some(_) => None,
        None => app.default_window_icon().cloned(),
    });
    let _ = tray.set_tooltip(Some(&display.tooltip));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot(phase: Phase, status: &str, seconds: u64) -> Snapshot {
        Snapshot {
            timer: focus_core::TimerView {
                phase,
                status: status.into(),
                display_seconds: seconds,
                active_ms: 0,
                duration_ms: None,
                cycle: 1,
                cycle_interval: 4,
                settings: Default::default(),
                selected_task: None,
                active_task: None,
            },
            revision: 0,
            recovered: false,
            pending_save: false,
            last_error: None,
            records: vec![],
            interruption: None,
        }
    }

    #[test]
    fn idle_keeps_the_icon_and_active_sessions_show_the_time() {
        let title = |phase, status, seconds| display(&snapshot(phase, status, seconds)).title;
        assert_eq!(title(Phase::Focus, "idle", 1500), None);
        assert_eq!(title(Phase::Stopwatch, "idle", 0), None);
        assert_eq!(
            title(Phase::Focus, "running", 1499).as_deref(),
            Some("24:59")
        );
        assert_eq!(
            title(Phase::Stopwatch, "running", 3725).as_deref(),
            Some("1:02:05")
        );
        assert_eq!(
            title(Phase::ShortBreak, "running", 299).as_deref(),
            Some("Break 04:59")
        );
        assert_eq!(
            title(Phase::Focus, "paused", 600).as_deref(),
            Some("\u{23F8}\u{FE0E} 10:00")
        );
        assert_eq!(
            display(&snapshot(Phase::Focus, "running", 60)).tooltip,
            "Focus · running"
        );
    }

    #[test]
    fn clock_matches_the_app_format() {
        assert_eq!(clock(0), "00:00");
        assert_eq!(clock(1499), "24:59");
        assert_eq!(clock(3600), "1:00:00");
        assert_eq!(clock(360_001), "100:00:01");
    }

    #[test]
    fn identical_labels_are_not_reapplied_and_updates_coalesce() {
        let menubar = MenuBarTime::default();
        let label = |title: &str| Display {
            title: Some(title.into()),
            tooltip: String::new(),
        };
        assert!(
            menubar.submit(label("24:59")),
            "first update starts a worker"
        );
        assert!(!menubar.submit(label("24:58")), "busy worker picks it up");
        assert!(!menubar.submit(label("24:58")), "duplicate is dropped");
        assert_eq!(menubar.next(), Some(label("24:58")));
        assert_eq!(menubar.next(), None, "worker stops when drained");
        assert!(
            menubar.submit(label("24:57")),
            "next update restarts a worker"
        );
    }
}
