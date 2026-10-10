# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0]

### Added
- First Tauri desktop release for Windows, macOS and Linux, with a local SQLite profile.
- Pomodoro and stopwatch timers, task-linked sessions, date-range reports, compact mode, and desktop preferences.

### Changed
- On macOS the menu bar item shows the running pomodoro or stopwatch time (with a pause sign or Break label) instead of the app icon, and returns to the icon when idle.
- Replaced the legacy Python app with a Tauri 2 / Rust / Svelte desktop app. See [MIGRATION.md](MIGRATION.md) for data migration steps.

### Fixed
- Compile the Linux compact-size helper only on Linux and in tests, keeping Windows and macOS lint checks clean.
