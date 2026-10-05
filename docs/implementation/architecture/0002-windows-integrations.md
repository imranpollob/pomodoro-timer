# ADR 0002 — Windows desktop integration

Accepted for the M1 prototype, October 5, 2026. Windows is the current validation target; macOS/Linux remain mandatory and require their own adapters and acceptance evidence.

## Decisions

- Native Rodio/CPAL playback runs on a dedicated worker, replacing webview audio. Preview replacement/cancellation and volume/mute share this worker. Device-open failures are visible. Streams are dropped after playback. API/device acceptance does not confirm audible delivery.
- Notifications and editable global shortcuts are opt-in. Windows notification settings and Focus Assist still control delivery; the plugin's desktop permission result does not establish those settings. New shortcut registrations are attempted before persistence/removal of previous bindings. Registration conflicts and save failures preserve previous preferences.
- SQLite schema 2 adds preferences through a transaction without rewriting existing sessions/checkpoints. The timer's serialized worker owns preference writes as well as session transactions. Window geometry uses a separate key and a debounced writer; normal exit flushes pending placement before quitting.
- Placement is validated and clamped to connected monitor bounds, using Windows work areas. Compact sizing is automatic. Native shadows are disabled for the compact window: testing at 125% DPI showed undecorated shadow offsets inflating a requested 44-pixel height. The normal packaged build now measures 200 × 44 logical pixels.
- Clicking/double-clicking the time, Enter and native accessibility Invoke open main. Click support makes the Windows UI Automation action functional without adding another visible control.
- A hidden top-level Windows window receives suspend broadcasts and registered session lock messages. Interruption records the observation timestamp before queuing a pause, so delayed handling cannot count sleep time. The listener waits at most one second for checkpoint completion, then returns and reports failure asynchronously. Wake/unlock never resumes automatically. Forced suspension/crash or failed writes can still lose time since the last durable checkpoint.
- A nondistributed smoke feature drives rendered controls via real IPC and simulates Windows messages. Normal packages are independently tested through Windows UI Automation, with isolated profiles and current-user install/uninstall. No test driver is included in distribution.

## Remaining gates

Physical sleep/lock, Narrator, multiple monitors/scales, tray visibility and manual notification/audio delivery require Windows QA. macOS/Linux suspend events, Wayland portal shortcuts, their native packages and assistive technology remain open. Linux audio development now requires ALSA headers. Signing, updater, stable migration and full product parity are later milestones.

References: [Windows suspend notification timing](https://learn.microsoft.com/en-us/windows/win32/power/pbt-apmsuspend), [session notifications](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change), [Tauri global shortcuts](https://v2.tauri.app/plugin/global-shortcut/), [notifications](https://v2.tauri.app/plugin/notification/), [Rodio 0.21.1](https://docs.rs/rodio/0.21.1/rodio/), and [platform evidence](../platform-validation.md).
