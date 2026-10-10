# Version 1.0.0 scope and acceptance plan

Updated October 10, 2026. Version 1.0.0 is released as the Tauri app at the repository root. This document records the released scope and the platform checks that still need direct verification. The legacy Python app was removed; its data is not imported automatically. See [MIGRATION.md](../../MIGRATION.md) for the manual steps.

## Included in v1.0.0

| Area | Released behavior |
| --- | --- |
| Timer | Pomodoro and stopwatch modes, editable durations and cycle, pause/resume, finish or skip, and optional automatic focus/break transitions after natural completion. |
| Tasks | Create, edit, complete, and remove tasks. A session keeps the task title selected when it starts. |
| Today and Reports | Local-day focus totals plus rolling 7-day/30-day and custom-date reports with summaries and session history. |
| Appearance | Light/dark theme and adjustable compact-window opacity. |
| Desktop controls | Main and 200 × 44 compact windows, tray or menu-bar access, pinning, audio, notifications, and saved window placement. Windows also pauses on native suspend and lock events. |
| Local storage | SQLite stores settings, tasks, sessions, and checkpoints. A running session is restored paused after restart; time while the app was closed is excluded. |
| Platforms | CI builds packages for Windows, macOS, and Linux. Package and native behavior evidence is tracked in [platform-validation.md](platform-validation.md). |

The UI behavior is defined in the [UI specification](ui-design-spec.md). The [backlog](backlog.md) summarizes released features and open verification work.

## Post-release acceptance

These checks describe installed-app behavior. Passing CI or browser tests does not count as physical desktop acceptance.

1. **macOS:** install the v1.0.0 package; check timer/task/report journeys, menu-bar and Dock behavior, VoiceOver, delivered audio and notifications, window placement, and sleep/wake.
2. **Windows:** check the full feature journey, real sleep/lock and wake/unlock, Narrator, tray visibility, audio and notification delivery, display scales, and monitor removal.
3. **Linux:** install the package; check the feature journey, tray, delivered audio and notifications, suspend behavior, Orca, display scales, and monitor removal.
4. Record the OS version, architecture, desktop session, package, and results in [platform-validation.md](platform-validation.md). Mark any unsupported or unverified behavior clearly.

## Acceptance checklist

- A focus or stopwatch session starts, pauses, resumes, and saves once; active time excludes pauses.
- A session keeps its task title after the task is edited or removed.
- Today's total matches saved Pomodoro and stopwatch sessions for the local date; breaks are excluded.
- Reports include every matching session for the selected range and show correct daily and range totals.
- Automatic start occurs only after natural completion when enabled. Manual finish, skip, and stopwatch remain manual.
- Settings persist after restart. A failed save is visible and is never shown as saved.
- Closing compact hides only that window. The timer continues, main is not raised automatically, and compact can be reopened through the platform's supported app controls.
- Closing or restarting during a session restores it paused and excludes time while the process was absent.
- Each platform's installed journey and native checks are recorded in the platform checklist.

## Not included in v1.0.0

Projects, cloud sync, automatic import of legacy data, data export, per-session detail views, reset-today, custom themes, goals, reminders, break overlays, and in-app updates are not included.

## Implementation boundary

Tauri 2 hosts the desktop app. Rust owns timer state, commands, and SQLite; Svelte/TypeScript renders the views. Main, compact, and tray controls use the same Rust timer service. Frontend code does not own the authoritative timer.
