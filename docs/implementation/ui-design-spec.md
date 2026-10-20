# Pomodoro Timer UI specification

Updated October 20, 2026. This document describes the current interface. The [mockup gallery](mockups/v2/README.md) includes concepts outside the released scope; this specification defines current behavior. The app builds for Windows, macOS, and Linux. Native platform verification is tracked in [platform-validation.md](platform-validation.md).

## Main window

The main window has four destinations: **Timer, Tasks, Reports, Settings**. Use native main-window decorations and keep the primary timer controls keyboard accessible. Use the Balanced layout: a 150 px sidebar on wider windows and a horizontal navigation row at 780 px and below. Start/Pause/Resume and Finish must stay in view without scrolling at the minimum 660 × 520 client size during ordinary idle, running, and paused states.

### Timer

- Show Pomodoro or stopwatch mode, phase, time, cycle where relevant, and Start/Pause/Resume. Place task selection above the ring, the primary action below it, and next-session context below the action. Keep Today and Last session in a quieter supporting column; Compact mode stays in the Timer heading.
- Provide validated focus, short-break, long-break, and cycle settings. Changes apply to the next session.
- Select a task before starting the next session. Hide the picker while a session is active; the active task snapshot stays fixed.
- Show the active task during a session and offer Finish or Skip break with explicit confirmation where required.
- Show today's saved focus time for the local calendar date, split into Pomodoro and stopwatch minutes and session counts. Break time is excluded.

### Tasks

- Use a three-column To do, In progress, and Done board on wide windows. At 900 px and below, stack the status groups so none are hidden behind horizontal scrolling. Tasks can be dragged between columns; a labeled status selector provides a keyboard-accessible alternative. Disable Tauri’s native drag-drop handler for the main window so HTML drag-and-drop works on Windows.
- Add, rename, and remove tasks. New tasks start in To do. Titles are trimmed, required, and limited to 120 characters. Keep the title and status visible; expose Edit/Remove through a keyboard-operable Actions disclosure. Preserve focus when status changes move a card. Until a status save succeeds, show the persisted value; a rejected save must remain retryable.
- Let the user select To do or In progress tasks from the Timer view; Done tasks are not selectable. Moving the selected task to Done clears it for later sessions but does not change an active session's task snapshot.
- Every transition into Done records a task completion event. Moving a task out of Done leaves the event in history; moving it into Done again records another event.
- Save task ID and title with each session. Renaming or removing a task must not rewrite history. Removal confirmation explains that saved sessions retain the title.
- Projects, estimates, and task search are deferred.

### Reports

Reports is the only session-history page. Reports opens on Today; the preset matching the selected range is highlighted. Last 7 days and Last 30 days include today and the preceding 6 or 29 local dates. Custom dates are inclusive. Keep presets together and put both custom-date fields and Apply dates in one form. Query all matching sessions; show focus time, Pomodoro/stopwatch counts, daily focus bars, and a five-column table: start time, session, task, active time, outcome. Also show a task-completion contribution graph for the rolling three local calendar months ending today and the current streak. The larger graph explicitly states that it is independent of the selected session range, labels each day with its exact count, and groups completions by local calendar date. Refresh the graph and streak when the local date changes, including focus/visibility after resume. Today/Last 7 days/Last 30 days advance with the date; custom dates stay unchanged. Refresh the task history when applying session dates as well. A day counts toward the streak when at least one task enters Done; the streak stays active when its latest completion was today or yesterday. Do not show CSV export or per-row Details actions. A confirmed Reset reports action in Settings deletes every recorded session and task-completion event while leaving task statuses unchanged. Active time excludes pauses; break time is excluded from focus totals.

### Settings

Keep v1 settings in the main window: timer durations/cycle, completion sound, sound volume, pinning, notifications on by default, and close-to-tray. Settings save automatically shortly after each edit; invalid timer values are skipped. Explain that notification delivery also depends on OS settings. Include light/dark, compact-mode opacity, and optional automatic focus/break transitions. Group controls into Timer, Sound & notifications, and Appearance & compact. Keep separate timer/desktop persistence and restore-default actions. Put Data & reset last; distinguish destructive controls and their confirmation actions with the danger color.

## Typography and layout

Use 16 px body text, primary labels/controls, and table rows; 14 px task status/actions, supporting copy, and secondary hints; 20 px section titles; and 32 px summary metrics. Timer digits and phase labels retain their functional emphasis. Use flat, theme-aware surfaces, subtle borders, a purple primary accent, clear To do/In progress/Done cues, vivid completion levels, and brief completion feedback. Give timer digits and task titles stronger emphasis than supporting summaries; avoid decorative gradients, glow, and layered card shadows. Keep labels and contrast clear in both themes and respect reduced-motion settings. Remove promotional page headings and sidebar slogans; open Compact mode from the timer page. Avoid repeating explanatory copy already conveyed by labels or headings.

## Compact timer

Target **200 × 44 logical pixels** and show the time, one small play/pause button and one small options button that opens the native menu. Grow for long stopwatch hours; do not clip digits or add other permanent controls.

- Space starts/pauses/resumes. Clicking, double-clicking, Enter, or assistive-technology Invoke on the time opens main.
- The options button, Shift+F10, or the context-menu key opens the native menu anchored below the button; right-click does nothing. Clicking the button again dismisses it.
- Escape, **Close compact timer**, or a native close request hides compact only. It must not stop the timer, quit the app, or automatically focus main. The tray can reopen it.
- Close compact, open main, pin, and sound belong in the accessible context menu, in that order.
- Keep task/phase context in the tooltip and accessible name without expanding the strip for long task titles.

## Shared behavior and data safety

Main, compact, and tray send commands to the same Rust timer service. The renderer never owns elapsed-time state. Failed writes remain visible; the app must not label unsaved work as saved. Closing/restarting during a session restores it paused and excludes process-down time. The schema upgrade to version 4 clears the existing task list once while preserving saved sessions and their task-title snapshots. Reset reports clears sessions and task-completion events, but leaves the current board intact. No task/session operation may silently delete or rewrite another saved record.

Use labels and keyboard focus that work without color alone. Do not announce each timer tick to screen readers; announce deliberate actions and phase changes. On desktops without a tray, keep a normal reopen path. Native sleep, notification, audio, geometry, and accessibility behavior must be verified per OS.

## Outside v1.0.0

Projects, sync/conflicts, automatic legacy import, backup/export windows, reset-today, custom themes, goals/reminders, overlays, updates, and diagnostic export remain future concepts in the gallery. They are not part of v1.0.0.
