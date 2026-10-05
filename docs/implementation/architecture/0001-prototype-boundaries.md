# ADR 0001 — Separate desktop prototype

Status: accepted for the M1 experiment, October 4, 2026. Final stack acceptance remains conditional on three-platform capability evidence.

## Decision

Use `desktop/` for Tauri 2, a Rust workspace, Svelte 5/TypeScript and SQLite. Keep the Python implementation, dependencies, data paths and release workflow available during beta development. Use the beta identifier `com.imranpollob.pomodoro-timer.beta` and a separate data directory. Do not import legacy files or change remote JSONBin records during this experiment. The October 5 MVP decision keeps legacy import and JSONBin sync out of MVP.

The Rust `focus-core` crate contains the timer domain, injected clock contract, one command-processing service and SQLite store. Commands from windows and tray go through that service. Renderer timers never calculate session time. State events carry revisions so delayed command/read responses cannot replace newer UI state.

Session finalization and the next checkpoint commit in one database transaction, with session UUID uniqueness. Only successful transactions advance the live state. Failure freezes elapsed time and requires a retry. Checkpoints serialize a paused state; process-down time is excluded on restart. A 15-second checkpoint interval bounds unrecorded active time while running, except during failed writes. Existing history is untouched.

Main uses native decorations; compact is a separate borderless window with one visible action and a native context menu. Escape or the context menu hides compact without reopening main; the timer continues. Native audio is implemented, while actual delivery, notification behavior, tray visibility and accessibility still require OS acceptance.

## Consequences and unresolved decisions

This establishes useful domain/persistence seams without accepting a stable database contract. The beta schema is versioned but is not a promised long-term user-data format. The Sessions view shows 20 recent records; the daily summary queries the full local-day range. Task attribution is implemented in the MVP. Projects, cloud sync, legacy import, advanced reports, import/export, and recovery UI remain outside MVP.

`Instant` supplies elapsed duration during normal operation. It does not establish a cross-platform suspend/lock policy; OS suspend adapters must be proved before timer acceptance. Global shortcuts, GNOME/KDE Wayland/X11 behavior, window geometry persistence and assistive technology remain open. The user's native Mac/Linux machines supplement hosted CI; remote access is not assumed.

Normal builds omit the Rust smoke module. Feature-enabled test executables observe normal snapshot IPC and probe the same timer service/SQLite store; no test command or embedded driver endpoint is exposed. These executables are not distributed. Signing, update channels, provider selection and final support baselines remain undecided.

References: [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/), [single-instance plugin](https://v2.tauri.app/plugin/single-instance/), [tray API](https://v2.tauri.app/learn/system-tray/), [notification plugin](https://v2.tauri.app/plugin/notification/), and the [platform checklist](../platform-validation.md).
