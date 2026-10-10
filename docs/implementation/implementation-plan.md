# Pomodoro Timer MVP implementation plan

Updated October 10, 2026. This plan defines the first releases of the Tauri app at the repository root (see [README](../../README.md)). The legacy Python app was removed in October 2026; its data will not be migrated.

## Selected feature additions

The user-selected additions now in the app are:

- **Reports:** rolling last-7-day, last-30-day, and custom local-date ranges; focus totals, daily summaries, and session rows. Reports are the only session-history page, with no CSV export or per-row Details actions.
- **Timer flow:** a saved preference to automatically start the next focus/break only after a timer completes naturally. Manually finishing or skipping a session never starts another session automatically. Stopwatch remains manual.
- **Appearance and accessibility:** dark/light theme and adjustable compact-mode opacity. Keep compact dimensions intact. Each native platform must honor these preferences or report an explicit capability limitation before release.
- **Subpage layout:** Timer, Tasks, Reports, and Settings use concise content titles and shared typography. No promotional header or sidebar slogans; Compact mode opens from the timer page.

## MVP features

| Feature | Required behavior | Current status |
| --- | --- | --- |
| Pomodoro and stopwatch | Configurable focus, short break, long break, and cycle; precise pause/resume; finish or skip; sleep/close recovery pauses instead of counting downtime. | Implemented; Windows acceptance remains. |
| Tasks | Add, rename, complete/uncomplete, remove; select a task for the next session; save the task ID and title with each session. Editing/removing a task must not rewrite saved history. | Implemented; runtime acceptance remains. |
| Today | Show today’s saved focus time split into Pomodoro and stopwatch minutes/session counts. Use the local calendar day. | Implemented; runtime acceptance remains. |
| Reports | Rolling last-7-day/last-30-day and custom local date ranges, aggregate and per-day focus summaries, and all matching session rows. | Implemented; Windows runtime acceptance pending. |
| Automatic transitions | Optional auto-start after a naturally completed focus/break; manual finish/skip and stopwatch stay manual. | Implemented; Windows runtime acceptance pending. |
| Appearance/accessibility | Light/dark and adjustable compact-mode opacity, persisted across restarts. | Implemented; native platform acceptance pending. |
| Compact timer | Target 200 × 44 logical pixels at default scale; show time, phase, and one play/pause control. Time activation opens main. Escape, native close, or **Close compact timer** hides only compact; timer and app keep running. | Implemented; verify in the running Windows app. |
| Desktop controls | Tray/reopen path, pinning, native audio, notifications, remembered placement, and Windows lock/suspend pause. | Implemented; several physical Windows checks remain. |
| Local data | SQLite stores settings, tasks, sessions, and checkpoints. Show save errors; retry failed session writes; restore active work paused after restart and exclude process downtime. | Implemented; new task/session flows need runtime acceptance. |
| Platform support | Build and accept on Windows first, then native macOS and Linux. No platform can be dropped from MVP. | Windows partial; Linux automated checks pass, installed/physical checks pending; macOS pending. |

The interface and compact behavior are detailed in the [UI specification](ui-design-spec.md); visual concepts are in the [mockup gallery](mockups/v2/README.md). The [backlog](backlog.md) tracks implementation status and the [platform checklist](platform-validation.md) tracks OS evidence.

## Delivery order

1. **Windows feature acceptance:** exercise tasks, full-range reports, auto-transition preference, theme/opacity settings, compact close/reopen, restart recovery, save failure feedback, tray, sound, and notifications in the native app.
2. **Windows desktop acceptance:** check real suspend/wake and lock/unlock, Narrator, display scaling and monitor removal, tray visibility, and actual sound/notification delivery. Record results in `platform-validation.md`.
3. **macOS and Linux acceptance:** when those machines are available, build and install the normal app, then verify timer/task/report journeys and native audio, notifications, sleep/wake, geometry, accessibility, and packaging. Add adapters where needed; retain all three OS requirements.
4. **MVP completion:** close every required feature and platform check above. The app must build as a normal package and run without a development server. Installers are unsigned; release distribution decisions follow MVP feature acceptance.

## MVP acceptance checklist

- A focus or stopwatch session can be started, paused, resumed, and finished once; saved active duration excludes pauses.
- A session started with a task retains that task’s title in history after the task is renamed, completed, or removed.
- Today’s total agrees with saved Pomodoro and stopwatch sessions for the local date; break sessions do not count as focus.
- Reports open on Today; the Today, Last 7 days, or Last 30 days preset matching the selected range is highlighted. Last 7 days and Last 30 days include today and the preceding 6 or 29 local dates; custom ranges include both selected dates. Reports include all matching records with correct totals. Settings offers a confirmed Reset reports action that deletes every recorded session.
- Automatic start begins the next focus/break only after natural timer completion when enabled; manual finish, skip, and stopwatch do not start another session.
- Theme and compact-mode opacity persist across restart and remain readable/usable at their supported values.
- Compact closes without exiting the app, reopening main, or stopping the timer; it can be opened again from the tray.
- Closing or restarting during a session restores it paused and excludes time while the process was absent.
- A failed save is visible and cannot be mistaken for a saved session.
- Each platform passes the installed-app journey and its native capability checks before MVP is declared complete.

## Out of scope

Projects, cloud sync, old-data migration, data import/export, session-detail views, reset-today, custom theme creation, goals/reminders, break overlays, and in-app updates are deferred. Created data still needs reliable local storage and recovery.

## Implementation boundary

Tauri 2 hosts the desktop app; Rust owns timer state, commands, and SQLite; Svelte/TypeScript renders views. Main, compact, and tray use the same Rust timer service. Frontend code must not run its own authoritative timer. The legacy Python app was removed; no legacy import exists.
