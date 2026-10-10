# MVP UI specification

Updated October 5, 2026. This document defines the current MVP interface. The full [mockup gallery](mockups/v2/README.md) also contains future concepts; those concepts do not add features to MVP. Windows is the current implementation target; Windows, macOS, and Linux remain mandatory.

## Main window

The main window has four destinations: **Timer, Tasks, Reports, Settings**. Use native main-window decorations and keep the primary timer controls keyboard accessible.

### Timer

- Show Pomodoro or stopwatch mode, phase, time, cycle where relevant, and Start/Pause/Resume.
- Provide validated focus, short-break, long-break, and cycle settings. Changes apply to the next session.
- Select a task for the next session. During an active session, changing this selection affects only a later session; the active task snapshot stays fixed.
- Show the active task during a session and offer Finish or Skip break with explicit confirmation where required.
- Show today's saved focus time for the local calendar date, split into Pomodoro and stopwatch minutes and session counts. Break time is excluded.

### Tasks

- Add, rename, complete/uncomplete, and remove a task. Titles are trimmed, required, and limited to 120 characters.
- Let the user select an incomplete task from the Timer view.
- Save task ID and title with each session. Renaming or removing a task must not rewrite history. Removal confirmation explains that saved sessions retain the title.
- Projects, archive workflows, estimates, and task search are deferred.

### Reports

Reports is the only session-history page. Reports opens on Today; the preset matching the selected range is highlighted. Last 7 days and Last 30 days include today and the preceding 6 or 29 local dates. Custom dates are inclusive. Query all matching sessions; show focus time, Pomodoro/stopwatch counts, daily focus bars, and a five-column table: start time, session, task, active time, outcome. Do not show CSV export or per-row Details actions. A confirmed Reset reports action in Settings deletes every recorded session. Active time excludes pauses; break time is excluded from focus totals.

### Settings

Keep MVP settings in the main window: timer durations/cycle, completion sound, sound volume, pinning, notifications on by default, and close-to-tray. Settings save automatically shortly after each edit; invalid timer values are skipped. Explain that notification delivery also depends on OS settings. Include light/dark, compact-mode opacity, and optional automatic focus/break transitions.

## Typography and layout

Use 16 px body text, labels, controls, and table rows; 20 px section titles; 14 px secondary hints; and 32 px summary metrics. Timer digits and phase labels retain their functional emphasis. Use the same hierarchy in both themes. Remove promotional page headings and sidebar slogans; open Compact mode from the timer page. Avoid repeating explanatory copy already conveyed by labels or headings.

## Compact timer

Target **200 × 44 logical pixels** and show only the time and one small play/pause button. Grow for long stopwatch hours; do not clip digits or add permanent controls.

- Space starts/pauses/resumes. Clicking, double-clicking, Enter, or assistive-technology Invoke on the time opens main.
- Right-click, Shift+F10, or the context-menu key opens the native menu.
- Escape, **Close compact timer**, or a native close request hides compact only. It must not stop the timer, quit the app, or automatically focus main. The tray can reopen it.
- Close compact, open main, pin, and sound belong in the accessible context menu, in that order.
- Keep task/phase context in the tooltip and accessible name without expanding the strip for long task titles.

## Shared behavior and data safety

Main, compact, and tray send commands to the same Rust timer service. The renderer never owns elapsed-time state. Failed writes remain visible; the app must not label unsaved work as saved. Closing/restarting during a session restores it paused and excludes process-down time. No task/session operation may silently delete or rewrite another saved record.

Use labels and keyboard focus that work without color alone. Do not announce each timer tick to screen readers; announce deliberate actions and phase changes. On desktops without a tray, keep a normal reopen path. Native sleep, notification, audio, geometry, and accessibility behavior must be verified per OS.

## Deferred design concepts

Projects, sync/conflicts, legacy import, backup/import/export windows, reset-today, custom themes, goals/reminders, overlays, updates, and diagnostic export remain future concepts in the gallery. They are not MVP acceptance criteria.
