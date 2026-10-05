# MVP backlog

Updated October 5, 2026. The [implementation plan](implementation-plan.md) defines scope; this page tracks code completion and acceptance. The existing Python app remains separate. Do not commit or push on the user's behalf.

## Implemented in the beta

- Pomodoro and stopwatch timer, editable durations/break cycle, precise pause/resume, checkpointing, and paused recovery.
- Main and 200 × 44 compact timer; compact can be hidden with Escape, its context menu, or a native close request without stopping the app or showing main.
- Native desktop settings, audio, notifications, tray, pinning, and Windows lock/suspend pause behavior.
- Task add/edit/complete/remove, next-session task selection, and task-title snapshots on session records.
- Today totals split by Pomodoro/stopwatch; session history is available only in Reports.
- Reports open on Today and provide rolling Last 7 days / Last 30 days presets (active preset highlighted), custom local-date ranges, all matching sessions, and daily/range totals. There are no CSV or Details actions. Settings offers a confirmed Reset reports action that deletes every recorded session.
- Optional automatic transitions, light/dark themes, and compact-mode opacity are persisted in desktop preferences.
- Timer, Tasks, Reports, and Settings use shared 16 px body/control text, 20 px section titles, and 14 px hints. Promotional headers and sidebar slogans are removed; Compact mode opens from the timer page.

## Demo data

`desktop/scripts/seed_demo_profile.py` adds stable synthetic tasks and two months of varied sessions to the selected beta profile without replacing existing data. See [desktop README](../../desktop/README.md#seed-demo-data-for-ui-review).

The selected reports/automatic-flow/appearance batch passes the frontend build, 9 Playwright UI checks, 6 Vitest checks, 20 Rust core tests, 4 native Rust tests, rustfmt, and Clippy. Native installed-app appearance and Windows runtime acceptance remain open.

## Remaining acceptance work

1. **Windows feature journey:** verify task/session attribution, today and date-range totals, date filtering, auto-start behavior, appearance changes, save errors, and restart recovery with the seeded demo records; use a disposable profile for destructive scenarios.
2. **Windows desktop checks:** confirm compact close/reopen; test real sleep/lock, Narrator, tray, sound/notification delivery, themes/scales/opacity, DPI changes, and monitor removal. Record evidence in [platform-validation.md](platform-validation.md).
3. **macOS and Linux:** when available, build/install and verify the same flows plus tray, audio, notifications, suspend behavior, geometry, and accessibility. Fix capability gaps.
4. **MVP gate:** only declare complete when all three platforms pass installed-app acceptance and essential controls remain reachable.

## Deferred

Projects, old-data migration, JSONBin/cloud sync, data import/export, session-detail views, reset-today, custom theme creation, goals/reminders, break overlays, and in-app updates are outside the MVP. Reliable storage and recovery for newly created beta data remain required.
