# Complete UI mockup gallery — revision 2

Prepared October 4, 2026. **18 boards** replace the previous two overview images as the current design direction. Begin with [compact mode](#03-compact-mode) to see the size and control reduction.

Read the [UI design specification](../../ui-design-spec.md) for the surface inventory, compact interaction contract, window/state behavior, and accessibility requirements. The [implementation plan](../../implementation-plan.md) retains Windows, macOS, and Linux as mandatory targets.

These are generated design concepts, not implemented application screenshots. Some repeated previews and small labels may vary between boards. Follow the written specification when an image differs. Logical dimensions are targets at default text scale, not the physical size of the raster image.


> **Scope note (October 5, 2026):** This gallery records broad visual exploration, not the active MVP contract. Use [the concise implementation plan](../../implementation-plan.md) and [MVP UI specification](../../ui-design-spec.md) for current scope. Project management, sync, migration, data import/export, custom themes, and other extended screens are deferred. The implemented Reports page uses rolling 7-day/30-day ranges and custom dates; CSV and Details actions from these concepts are intentionally omitted. Promotional headers and sidebar slogans are also omitted.

## Board index

| Board | Windows and states |
| --- | --- |
| [01](#01-timer-states) | Timer: ready, running, paused |
| [02](#02-break-and-stopwatch) | Short break, long break, stopwatch |
| [03](#03-compact-mode) | Compact: one control, six states |
| [04](#04-tasks-and-projects) | Tasks, task editor, project editor, archive |
| [05](#05-reports-and-export) | Reports, date range, session detail, export |
| [06](#06-settings-timer-appearance) | Settings: timer and appearance |
| [07](#07-settings-alerts-shortcuts) | Settings: sound, notification permissions, shortcuts |
| [08](#08-settings-desktop-sync-about) | Settings: desktop, optional sync, about |
| [09](#09-data-and-recovery) | Data management, import preview, restore backup |
| [10](#10-first-launch-migration-and-resume) | First launch, migration, permissions, session recovery |
| [11](#11-sync-dialogs-and-conflicts) | Sync connection, offline, conflict, disconnect |
| [12](#12-confirmations-empty-and-errors) | Confirmations and exceptional UI states |
| [13](#13-tray-notifications-and-updates) | Tray menu, notification, update and exit |
| [14](#14-platforms-and-accessibility) | Windows, macOS, Linux, keyboard and larger text |
| [15](#15-follow-up-windows) | Later releases: breaks, goals, theme import |
| [16](#16-support-and-system-dialogs) | Release notes, licenses, diagnostics, system dialogs |
| [17](#17-daily-report-and-reset) | Daily report and existing reset-statistics flow |
| [18](#18-completion-and-draft-dialogs) | Session completion, unsaved drafts, disconnect and reconnect |

<a id="01-timer-states"></a>

## 01 — Timer: ready, running, paused

Ready, running, and paused Pomodoro sessions. Final components should keep the same task/cycle structure across states.

![Timer: ready, running, paused](01-timer-states.png)

<a id="02-break-and-stopwatch"></a>

## 02 — Short break, long break, stopwatch

Short and long breaks plus an hours-based stopwatch. Any extra overview panels in the board are incidental previews.

![Short break, long break, stopwatch](02-break-and-stopwatch.png)

<a id="03-compact-mode"></a>

## 03 — Compact: one control, six states

Six compact states, task tooltip, context menu, and enlarged sizing study. The strip has exactly one visible control; measurements follow the written specification.

![Compact: one control, six states](03-compact-mode.png)

<a id="04-tasks-and-projects"></a>

## 04 — Tasks, task editor, project editor, archive

Task workspace, validated task editor, project form, and archived tasks. Project editing reuses the same form.

![Tasks, task editor, project editor, archive](04-tasks-and-projects.png)

<a id="05-reports-and-export"></a>

## 05 — Reports, date range, session detail, export

Weekly overview, custom range, session details, and CSV/JSON export. Today/month reuse the same report components.

![Reports, date range, session detail, export](05-reports-and-export.png)

<a id="06-settings-timer-appearance"></a>

## 06 — Settings: timer and appearance

Duration/cycle and automatic-transition settings, followed by appearance, text size, reduced motion, and supported opacity.

![Settings: timer and appearance](06-settings-timer-appearance.png)

<a id="07-settings-alerts-shortcuts"></a>

## 07 — Settings: sound, notification permissions, shortcuts

Sound preview, blocked notifications, editable shortcuts, capture dialog, and unavailable/conflicting global shortcut states.

![Settings: sound, notification permissions, shortcuts](07-settings-alerts-shortcuts.png)

<a id="08-settings-desktop-sync-about"></a>

## 08 — Settings: desktop, optional sync, about

Desktop behavior, sync off/connected, and About. Native capability messages must reflect the actual supported desktop.

![Settings: desktop, optional sync, about](08-settings-desktop-sync-about.png)

<a id="09-data-and-recovery"></a>

## 09 — Data management, import preview, restore backup

Backup/export/import entry points, import validation, backup restore confirmation, and corrupted-data recovery.

![Data management, import preview, restore backup](09-data-and-recovery.png)

<a id="10-first-launch-migration-and-resume"></a>

## 10 — First launch, migration, permissions, session recovery

Local-first welcome, existing-data import, completion summary, optional permission setup, and session resumption.

![First launch, migration, permissions, session recovery](10-first-launch-migration-and-resume.png)

<a id="11-sync-dialogs-and-conflicts"></a>

## 11 — Sync connection, offline, conflict, disconnect

Optional connection, offline edits, conflicting task revisions, and safe disconnection. Provider details remain an architecture decision.

![Sync connection, offline, conflict, disconnect](11-sync-dialogs-and-conflicts.png)

<a id="12-confirmations-empty-and-errors"></a>

## 12 — Confirmations and exceptional UI states

Finish/archive/unsaved-draft confirmations and the empty, loading, invalid-input, failed-save, and undo patterns.

![Confirmations and exceptional UI states](12-confirmations-empty-and-errors.png)

<a id="13-tray-notifications-and-updates"></a>

## 13 — Tray menu, notification, update and exit

Tray/menu-bar actions, completion notification, update progress/failure/install deferral, and exit during active focus. “Keep running” means continue in a supported background state.

![Tray menu, notification, update and exit](13-tray-notifications-and-updates.png)

<a id="14-platforms-and-accessibility"></a>

## 14 — Windows, macOS, Linux, keyboard and larger text

Shared Windows/macOS/Linux functionality, platform chrome, visible keyboard focus, larger text, and minimalist compact variants.

![Windows, macOS, Linux, keyboard and larger text](14-platforms-and-accessibility.png)

<a id="15-follow-up-windows"></a>

## 15 — Later releases: breaks, goals, theme import

Later-release concepts only: fullscreen break overlay, scheduled breaks, goals/reminders, and custom theme import. These do not expand first-stable-release scope.

![Later releases: breaks, goals, theme import](15-follow-up-windows.png)

<a id="16-support-and-system-dialogs"></a>

## 16 — Release notes, licenses, diagnostics, system dialogs

Release notes, licenses, redacted diagnostic export, rejected-record review, and OS-owned file/permission chooser concepts.

![Release notes, licenses, diagnostics, system dialogs](16-support-and-system-dialogs.png)

<a id="17-daily-report-and-reset"></a>

## 17 — Daily report and existing reset-statistics flow

Preserves the current app's daily Pomodoro/stopwatch breakdown and reset-today action. Reset requires confirmation, a protective backup, no active session, atomic date-scoped deletion, and reconciled task totals. Backup failure leaves data untouched.

![Daily report and reset statistics](17-daily-report-and-reset.png)

<a id="18-completion-and-draft-dialogs"></a>

## 18 — Session completion, unsaved drafts, disconnect and reconnect

Explicit designs for the completed-session next action, save/discard/keep-editing choice, local-data-preserving disconnect, and expired-credential reconnect. These complete dialog coverage where earlier boards prioritized the larger screens.

![Session completion, unsaved drafts, disconnect and reconnect](18-completion-and-draft-dialogs.png)

## Asset record

All boards were generated using the **built-in image_gen tool**, inspected, and copied into this project. [Exact generation prompts and refinement instructions](prompts.json) accompany the images. [Inspection notes](inspection-notes.md) record design differences that remain illustrative.

The two revision-1 images in the parent directory are retained for historical comparison. They no longer define compact geometry or controls.
