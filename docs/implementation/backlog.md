# Version 1.0.0 backlog and follow-on work

Updated October 20, 2026. Version 1.0.0 is the first released Tauri app. This page summarizes the released scope, follow-on implementation in the current tree, and installed-app checks that still need direct platform verification. The legacy Python app was removed; its data is not imported automatically.

## Included in v1.0.0

- Pomodoro and stopwatch timers with editable durations, pause/resume, finish/skip, checkpoints, and paused recovery after restart.
- Main and 200 × 44 compact windows. Hiding compact keeps the timer and app running.
- Tasks assigned before a session starts; each session keeps the task title it started with.
- Today totals and date-range reports with daily summaries and session history.
- Optional automatic focus/break transitions, light/dark theme, compact opacity, sound, notifications, and desktop preferences.
- Windows lock/suspend pause handling. The menu bar, tray, and app-reopen behavior follow each platform's controls.
- Local SQLite storage for settings, tasks, sessions, and checkpoints.

## Follow-on implementation in the current tree

- Three-column task board with To do, In progress, and Done statuses, drag-and-drop, and keyboard status controls.
- Task completion events power a rolling three-local-month contribution graph and a current streak. Reopening a task does not erase completion history; each later move into Done records another event.
- Accepted Balanced UI revision: flatter light/dark surfaces, minimum-window timer controls in view, responsive task groups with accessible Actions, a larger independently labeled heatmap, and grouped settings with destructive reset last. Compact mode dimensions and shared backend authority are preserved.
- Review fixes: Windows HTML drag-and-drop enabled, rejected status saves retain the persisted value and keyboard focus, and completion reports refresh across local-date rollover/resume while preserving custom session ranges.
- The schema upgrade to version 4 clears the existing task list once, as requested, while preserving saved sessions and their task-title snapshots.

## Demo data

[`scripts/seed_demo_profile.py`](../../scripts/seed_demo_profile.py) adds stable synthetic tasks, completion events, and sessions to the selected profile. A pre-v4 profile receives the documented one-time task-list reset during schema upgrade. See [the development guide](../development.md#seed-demo-data-for-ui-review) for instructions.

The recorded frontend and Rust checks passed, as did the Linux automated checks. Platform-specific build, installation, and native-behavior evidence is in [platform-validation.md](platform-validation.md). CI and browser fixtures do not establish physical desktop acceptance.

## Post-release validation

1. **macOS:** install the release build and verify the main timer, tasks, reports, menu bar/Dock behavior, VoiceOver, audio and notification delivery, placement, and sleep/wake behavior.
2. **Windows:** verify the feature journey and physical sleep/lock, Narrator, tray, audio and notification delivery, display scaling, and monitor changes.
3. **Linux:** install the package and verify the feature journey, tray, audio and notification delivery, suspend behavior, Orca, display scaling, and monitor changes.
4. Record the OS, version, architecture, desktop session, package, and results in [platform-validation.md](platform-validation.md). Keep unverified behavior marked as unverified.

## Not included in v1.0.0

Projects, automatic import of legacy data, cloud sync, data export, per-session detail views, reset-today, custom themes, goals, reminders, break overlays, and in-app updates are not included. See [MIGRATION.md](../../MIGRATION.md) for migration from the Python app.
