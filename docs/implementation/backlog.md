# Version 1.0.0 backlog

Updated October 10, 2026. Version 1.0.0 is the first released Tauri app. This page summarizes the released scope and tracks installed-app checks that still need direct platform verification. The legacy Python app was removed; its data is not imported automatically.

## Included in v1.0.0

- Pomodoro and stopwatch timers with editable durations, pause/resume, finish/skip, checkpoints, and paused recovery after restart.
- Main and 200 × 44 compact windows. Hiding compact keeps the timer and app running.
- Tasks assigned before a session starts; each session keeps the task title it started with.
- Today totals and date-range reports with daily summaries and session history.
- Optional automatic focus/break transitions, light/dark theme, compact opacity, sound, notifications, and desktop preferences.
- Windows lock/suspend pause handling. The menu bar, tray, and app-reopen behavior follow each platform's controls.
- Local SQLite storage for settings, tasks, sessions, and checkpoints.

## Demo data

[`scripts/seed_demo_profile.py`](../../scripts/seed_demo_profile.py) adds stable synthetic tasks and sessions to the selected profile without replacing existing data. See [the development guide](../development.md#seed-demo-data-for-ui-review) for instructions.

The recorded frontend and Rust checks passed, as did the Linux automated checks. Platform-specific build, installation, and native-behavior evidence is in [platform-validation.md](platform-validation.md). CI and browser fixtures do not establish physical desktop acceptance.

## Post-release validation

1. **macOS:** install the release build and verify the main timer, tasks, reports, menu bar/Dock behavior, VoiceOver, audio and notification delivery, placement, and sleep/wake behavior.
2. **Windows:** verify the feature journey and physical sleep/lock, Narrator, tray, audio and notification delivery, display scaling, and monitor changes.
3. **Linux:** install the package and verify the feature journey, tray, audio and notification delivery, suspend behavior, Orca, display scaling, and monitor changes.
4. Record the OS, version, architecture, desktop session, package, and results in [platform-validation.md](platform-validation.md). Keep unverified behavior marked as unverified.

## Not included in v1.0.0

Projects, automatic import of legacy data, cloud sync, data export, per-session detail views, reset-today, custom themes, goals, reminders, break overlays, and in-app updates are not included. See [MIGRATION.md](../../MIGRATION.md) for migration from the Python app.
