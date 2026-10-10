# Pomodoro Timer

[![CI](https://github.com/imranpollob/pomodoro-timer/actions/workflows/ci.yml/badge.svg)](https://github.com/imranpollob/pomodoro-timer/actions/workflows/ci.yml)

A focus timer for Windows, macOS and Linux, built with Tauri 2, Rust, Svelte/TypeScript and SQLite. Your data stays on your machine in a local SQLite profile.

![Main timer](docs/implementation/prototype-screenshots/main-timer.png)

## Features

- Pomodoro, short/long breaks and stopwatch, with precise pause/resume and explicit finish confirmation.
- A 200 × 44 compact countdown strip with one play/pause button and an accessible context menu.
- Tasks that you assign before a session starts; the title is saved with the session.
- Reports for today, the last 7/30 days and custom date ranges.
- System tray (Windows/Linux) or menu bar (macOS), native notifications and audio, light/dark theme.
- Sleep/lock handling, transactional persistence and crash-safe checkpoints from a single Rust timer authority.

## Install

Pre-built packages are **unsigned** CI artifacts (`.deb`, NSIS installer, `.dmg`) and no release has been published yet. Download them from the latest [CI run](https://github.com/imranpollob/pomodoro-timer/actions/workflows/ci.yml), or build from source below. Coming from the legacy Python app or a beta build? See [MIGRATION.md](MIGRATION.md).

## Build from source

Install the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/), Rust via rustup (the toolchain is pinned in `rust-toolchain.toml`) and Node 24 (see `.node-version`).

```sh
npm ci
npm run tauri -- dev      # run the app
npm run tauri -- build    # produce a package
```

Platform-specific setup, packaging, test commands and demo data are in the [development guide](docs/development.md).

## Data and privacy

Profiles live in the app-data directory for `com.imranpollob.pomodoro-timer`. Set `POMODORO_DATA_DIR` before launching to use another location. Back up the whole directory with the app closed.

## Project layout

| Path | Purpose |
| --- | --- |
| `crates/focus-core/` | Timer domain, service and SQLite persistence (no Tauri dependency) |
| `src-tauri/` | Windows, tray, notifications, audio and process lifecycle |
| `src/` | Svelte views and typed IPC client |
| `tests/` | Playwright UI tests |
| `scripts/` | Smoke tests, demo seeder and packaging helpers |
| `docs/` | Development guide, specifications and validation records |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
