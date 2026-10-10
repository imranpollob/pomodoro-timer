# MVP backlog

Updated October 10, 2026. The [implementation plan](implementation-plan.md) defines scope; this page tracks code completion and acceptance. The legacy Python app was removed and the Tauri app promoted to the repository root as v1. Do not commit or push on the user's behalf.

## Implemented

- Pomodoro and stopwatch timer, editable durations/break cycle, precise pause/resume, checkpointing, and paused recovery.
- Main and 200 × 44 compact timer; compact can be hidden with Escape, its context menu, or a native close request without stopping the app or showing main.
- Native desktop settings, audio, notifications, tray, pinning, and Windows lock/suspend pause behavior.
- Task add/edit/complete/remove, next-session task selection, and task-title snapshots on session records.
- Today totals split by Pomodoro/stopwatch; session history is available only in Reports.
- Reports open on Today and provide rolling Last 7 days / Last 30 days presets (active preset highlighted), custom local-date ranges, all matching sessions, and daily/range totals. There are no CSV or Details actions. Settings offers a confirmed Reset reports action that deletes every recorded session.
- Optional automatic transitions, light/dark themes, and compact-mode opacity are persisted in desktop preferences.
- Timer, Tasks, Reports, and Settings use shared 16 px body/control text, 20 px section titles, and 14 px hints. Promotional headers and sidebar slogans are removed; Compact mode opens from the timer page.

## Demo data

`scripts/seed_demo_profile.py` adds stable synthetic tasks and two months of varied sessions to the selected profile without replacing existing data. See [README](../../README.md#seed-demo-data-for-ui-review).

The app passes the frontend build, 23 Playwright UI checks, 6 Vitest checks, 22 Rust core tests, 8 native Rust tests, rustfmt, and Clippy, plus the native webview/IPC smoke with compact geometry checks on Linux. Installed-app appearance and runtime acceptance remain open.

## Remaining acceptance work

1. **Windows feature journey:** verify task/session attribution, today and date-range totals, date filtering, auto-start behavior, appearance changes, save errors, and restart recovery with the seeded demo records; use a disposable profile for destructive scenarios.
2. **Windows desktop checks:** confirm compact close/reopen; test real sleep/lock, Narrator, tray, sound/notification delivery, themes/scales/opacity, DPI changes, and monitor removal. Record evidence in [platform-validation.md](platform-validation.md).
3. **macOS and remaining Linux acceptance:** Linux automated checks (gates, native smoke, package build) pass; run the installed-app journey plus tray, audio, notifications, suspend behavior, geometry, and accessibility there. On macOS, build/install and verify the same flows. Fix capability gaps.
4. **MVP gate:** only declare complete when all three platforms pass installed-app acceptance and essential controls remain reachable.

## Deferred

Projects, old-data migration, cloud sync, data import/export, session-detail views, reset-today, custom theme creation, goals/reminders, break overlays, and in-app updates are outside the MVP. Reliable storage and recovery for created data remain required.
