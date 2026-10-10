# ADR 0001 — Separate desktop prototype

Status: Historical design record, accepted for the M1 experiment on October 4, 2026. The Tauri stack was released as version 1.0.0; current platform evidence is in [platform-validation.md](../platform-validation.md).

Note, October 2026: the legacy Python app was removed and the Tauri app promoted to the repository root with identity `com.imranpollob.pomodoro-timer`. The separate-`desktop/` and interim-identity parts of this decision are superseded. This record explains the initial prototype; it is not the current v1 specification.

## Decision

Use `desktop/` for Tauri 2, a Rust workspace, Svelte 5/TypeScript and SQLite. Keep the Python implementation, dependencies, data paths and release workflow available during the Tauri experiment. Use the initial identifier `com.imranpollob.pomodoro-timer.beta` and a separate data directory. Do not import legacy files or change remote JSONBin records during this experiment. The October 5 MVP decision keeps legacy import and JSONBin sync out of MVP.

The Rust `focus-core` crate contains the timer domain, injected clock contract, one command-processing service and SQLite store. Commands from windows and tray go through that service. Renderer timers never calculate session time. State events carry revisions so delayed command/read responses cannot replace newer UI state.

Session finalization and the next checkpoint commit in one database transaction, with session UUID uniqueness. Only successful transactions advance the live state. Failure freezes elapsed time and requires a retry. Checkpoints serialize a paused state; process-down time is excluded on restart. A 15-second checkpoint interval bounds unrecorded active time while running, except during failed writes. Existing history is untouched.

Main uses native decorations; compact is a separate borderless window with one visible action and a native context menu. Escape or the context menu hides compact without reopening main; the timer continues. Native audio is implemented, while actual delivery, notification behavior, tray visibility and accessibility still require OS acceptance.

## Consequences and unresolved decisions

This established useful domain/persistence seams without accepting a stable database contract. The prototype schema was versioned but was not a promised long-term user-data format. The prototype Sessions view showed 20 recent records; its daily summary queried the full local-day range. Task attribution was implemented later. Projects, cloud sync, automatic legacy import, advanced reports, import/export, and recovery UI were outside the original scope.

`Instant` supplies elapsed duration during normal operation. It does not establish a cross-platform suspend/lock policy. Global shortcuts are not part of v1.0.0; native suspend behavior and assistive technology still need platform-specific verification. GNOME/KDE Wayland/X11 behavior also requires direct testing.

Normal builds omit the Rust smoke module. Feature-enabled test executables observe normal snapshot IPC and probe the same timer service/SQLite store; no test command or embedded driver endpoint is exposed. These executables are not distributed. Version 1.0.0 packages are unsigned; an updater is not included.

References: [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/), [single-instance plugin](https://v2.tauri.app/plugin/single-instance/), [tray API](https://v2.tauri.app/learn/system-tray/), [notification plugin](https://v2.tauri.app/plugin/notification/), and the [platform checklist](../platform-validation.md).
