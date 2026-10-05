# Implementation log

## October 4, 2026 — First stabilization batch

B01–B03 and the implementation portion of B04 are complete in the existing Python application. This is the reliable baseline for the planned rebuild; no Tauri workspace or revision-2 UI has been implemented yet. Windows, macOS, and Linux remain mandatory. M0 is open until all three CI jobs and the performance baseline pass.

### Resulting behavior

- Countdown and stopwatch use the same injected monotonic clock. Delayed refreshes compute elapsed duration, pauses exclude paused time, fractional segments accumulate, and one generation-guarded callback renders the timer. Stop, mode change, completion, and close finalize a session once during the process lifetime.
- Work/break duration and cycle interval are captured when a session starts. Changes apply to future sessions. Invalid saved or entered settings produce visible errors instead of a divide-by-zero crash or partial settings save.
- Settings, tasks, and history are validated. Writes use a same-directory temporary file, flush/fsync, and replacement; valid previous contents are saved as `.json.bak`. Malformed originals remain untouched and are copied to `.json.corrupt-<id>` when possible. A failed protective backup prevents replacement.
- Failed session saves freeze the recorded active duration and expose **Retry save**. Starting/resuming/replacing that unfinished session is blocked until saved; close cannot silently discard it. This protection is in memory, so forcibly terminating the process still loses an unsaved session. Durable restart recovery belongs to M2.
- The **Recovery** menu opens a native backup picker for settings, tasks, or history. Selected contents are validated before restoration. Reset-today retains other dates, creates a backup, and refuses an active or paused unfinished session.
- Task changes are saved before committing the candidate list. Failed additions retain the input; unsaved edit text survives row rendering. New tasks use UUIDs and timezone-aware revision timestamps.
- Sync validates task schemas/timestamps, preserves edits made during a request, and rebases those edits beyond received timestamps. Deletion wins equal-timestamp ties. Tombstones no longer expire solely because seven days elapsed.
- Workers send results through a synchronized queue; only the main thread operates Tk. Close cancels polling and checks cancellation before a pending upload. An HTTP upload already sent cannot be canceled by this bridge.
- An OS-held lock prevents two normal app instances from sharing a data directory. Lock files remain on disk; process exit releases the lock. Storage operations are serialized within a manager.
- Geometry parsing supports monitors with negative coordinates. Linux completion audio uses an optional discovered `paplay` executable without shell interpolation, with the existing bell fallback.

### Validation evidence

| Check | Local result | Scope |
| --- | --- | --- |
| Full pytest suite | **101 passed** | Existing coverage plus seven research defect regressions and persistence, lifecycle, sync, and process-lock failure cases |
| Native Tk smoke | Passed on Windows | Countdown/stopwatch pause-resume, task editing, Unicode, draft retention, settings/report windows, geometry, close |
| PyInstaller build | Passed on Windows | Current source packaged into `dist/pomodoro.exe` |
| Packaged startup smoke | Passed on Windows | Isolated data directory; executable remained running for eight seconds; launched process tree cleaned up |
| Compile checks and `git diff --check` | Passed | Python syntax and whitespace |
| Windows/macOS/Linux PR CI | Workflow authored; results pending | Locked dependencies, pytest, native Tk smoke, package build, packaged launch; Linux installs the `.deb` |
| Post-change startup/history/process-tree metrics | Pending | Must be recorded before M0 exit; no new performance improvement claim yet |

The packaged launch test checks startup/lifetime only. It does not establish installer, accessibility, sleep/wake, signing, or full packaged GUI acceptance. The native Tk smoke drives real widgets with a deterministic clock. Regression tests and smoke scripts use temporary profiles and fake sync responses; they do not transmit real tasks or JSONBin credentials. Research probes and their historical results are unchanged.

Run from the repository root after installing the locked dependencies:

```text
uv sync --locked
uv run --locked python -m pytest -q
uv run --locked python scripts/smoke_app.py
uv run --locked pyinstaller --noconfirm pomodoro.spec
uv run --locked python scripts/smoke_packaged.py dist/pomodoro.exe
```

On Linux, run GUI checks under `xvfb-run --auto-servernum` when no display is available. The packaged path there is `/usr/bin/pomodoro` after installing the `.deb`; on macOS use `dist/Pomodoro.app/Contents/MacOS/pomodoro`. Local Windows checks used the existing `.venv/Scripts/python.exe` Python 3.12 environment; the dependency lockfile was not changed.

### Boundaries and next work

The JSONBin bridge still reads and replaces an entire bin. Concurrent devices can overwrite each other; the new local reconciliation is not the M6 revision-aware protocol. Legacy naive timestamps have no recoverable original timezone and use UTC only as a deterministic ordering convention. Deletion records remain indefinitely until an acknowledged deletion protocol exists. Existing credential storage/provider behavior is unchanged.

The legacy policy ignores sessions shorter than ten seconds. History is still JSON and rewritten with backups; large-history scaling awaits SQLite in M2. File fsync and atomic replacement do not establish full directory durability under every power-loss scenario. A monotonic clock avoids wall-clock corrections, but sleep/wake policy still needs explicit platform adapters; it is not proven by these tests.

Next: run the three-OS CI and record baseline measurements, then B05/B06 should create a separate Tauri prototype and prove all mandatory desktop capabilities. The revision-2 compact strip remains specified at **200 × 44 logical pixels**, one visible play/pause control, with other actions in its accessible context menu. The current Tk layout remains in place during this batch.

### Files and references

Core additions: `src/timer.py`, `src/settings.py`, `src/instance.py`. Integration: `src/pomodoro.py`, `src/storage.py`, `src/sync.py`. Verification: `tests/test_stabilization.py`, updated existing tests, `scripts/smoke_app.py`, `scripts/smoke_packaged.py`, `.github/workflows/ci.yml`.

Implementation contracts follow Python's official documentation for [monotonic clocks](https://docs.python.org/3/library/time.html#time.monotonic), [replacement semantics](https://docs.python.org/3/library/os.html#os.replace), and [thread-safe queues](https://docs.python.org/3/library/queue.html). CI configuration follows the [official uv integration guide](https://docs.astral.sh/uv/guides/integration/github/) and [setup-python documentation](https://github.com/actions/setup-python).

## October 4, 2026 — Linux CI close failure

The reported CI screenshot shows Windows/macOS validation passing and Linux failing at the native Tk smoke's close assertion. Reproducing the committed application under Linux/Xvfb exposed the underlying error: `window_width must be an integer from 80 to 8192`, with geometry `1x1+0+0`. The withdrawn window had never been mapped. Compact/restore captured that temporary geometry, mutated settings, and caused subsequent saves and close to fail validation.

Geometry capture now flushes pending layout and retains the last validated dimensions for unmapped windows or dimensions outside the existing bounds. Close and compact/restore use the same helper. Compact/restore save candidates before changing in-memory settings. Settings bounds and genuine storage-error handling remain intact. The smoke assertion now reports the error and geometry when close fails.

Five regression cases cover unmapped main/compact close, hidden compact/restore, and out-of-range sizes. Shared source-path setup in `tests/conftest.py` also permits selecting the stabilization tests independently of collection order.

**Verified locally:** 106 tests and native Tk smoke pass on Windows (Python 3.12.15) and WSL Ubuntu 26.04.1 (Python 3.14.4, Tk 8.6, Xvfb), using locked dependencies and temporary data. The same Linux smoke against the committed pre-fix application failed with the diagnostic above. WSL checks used a separate Linux environment and did not replace the Windows `.venv`.

The exact `ubuntu-24.04` GitHub runner and all three jobs must rerun on the pushed fix before merge. This follow-up did not rebuild packages or change the CI matrix. M0's three-platform gate and post-change performance measurements remain open.

## October 4, 2026 — M0 closed; Tauri migration started

The user confirms that the Windows/macOS/Linux legacy CI now passes and requests M0 closure. M0.8 and M0 are closed on that confirmation. This supersedes the preceding pending-CI status; no remote run URL was supplied. Unrecorded legacy performance measurements carry forward to the M1 comparison and M5.3 rather than being presented as measured.

### Delivered prototype

M1.1 is implemented in the separate [`desktop/`](../../desktop/README.md) workspace. Node 24.19.0/npm 11.17.0 and Rust 1.99.0 are pinned; both dependency lockfiles are included. The legacy application, tests and release workflows remain available.

- The Rust `focus-core` crate owns injected-clock timing, frozen session configuration, Pomodoro cycles, stopwatch, finish/skip outcomes and paused recovery. One serialized service handles commands from all windows/tray, revisions, one-second presentation updates and 15-second checkpoints.
- SQLite transactions persist a session and checkpoint together; duplicate record IDs are idempotent. Failed transactions freeze active duration and block replacement until retry succeeds. Malformed checkpoints are rejected instead of silently overwritten. Forced termination can lose active time since the latest checkpoint.
- Svelte views provide the main timer, a 200 × 44 compact countdown with one visible action, recent sessions, timer preferences, finish confirmation, and connection/save/recovery feedback. Compact supports Space, time-region Enter/double-click, drag and a keyboard-accessible native context menu with checked pin/sound items. Main remains reachable when the tray is unavailable.
- Native integration includes single-instance activation, tray actions, notification testing and close/OS-quit checkpointing. Beta identity and `POMODORO_BETA_DATA_DIR` keep the prototype isolated from legacy profiles. There is no legacy import or remote sync in this batch.
- `.github/workflows/desktop.yml` checks frontend/Rust code and builds unsigned normal `.deb`, NSIS and `.dmg` prototypes. A separate, nondistributed `smoke-test` executable checks both native webviews' regular IPC and SQLite read-back; the test driver is absent from normal builds.

### Verification

| Check | Result | Environment and scope |
| --- | --- | --- |
| Frontend build | Passed; zero Svelte errors/warnings | Windows, Node 24.19.0; production assets generated |
| Vitest | 4 passed | Event ordering, listener cleanup, display/retry contracts |
| Playwright | 4 passed | Rendered Svelte with test-only IPC fixtures: pause/resume, modal focus, compact fit/one action, settings validation, empty/connection states |
| Rust core/service/store | 12 passed | WSL Ubuntu 26.04.1 x86_64; injected clocks, transactional rollback/idempotency, malformed checkpoints and failed-save guards |
| rustfmt / Clippy | Passed | Normal workspace and `smoke-test` feature; warnings rejected |
| Native Tauri build and smoke | Passed | WSL/Xvfb/DBus, Rust 1.99.0; both webviews call Rust, shared commands, one saved session and paused SQLite checkpoint |
| Legacy pytest | 106 passed | Windows Python 3.12; coexistence regression check |

The headless native run logged GTK/EGL/portal warnings. Its success establishes IPC/storage behavior, not tray visibility, physical audio/notifications or accessibility. Windows native compilation is pending C++/Rust prerequisites on this host; macOS and physical Linux tests await the user's machines. The new three-platform workflow is authored and has not run remotely in this session. No replacement performance or installed-package readiness claim is made.

### Next gate

Complete B05/M1.2 package checks on all three platforms, then B06 native capability evidence using the [platform checklist](platform-validation.md). Explicit sleep/lock adapters, global shortcuts, notification permission handling, reliable hidden-main audio, geometry restoration, text scaling and assistive-technology journeys remain open. Tauri stays provisional until these mandatory gates pass.

Tasks/projects, full reports, migration/recovery workflows, synchronization and the remaining UI inventory follow later batches. The foundational Rust/SQLite work supports this prototype; it does not close M2. [ADR 0001](architecture/0001-prototype-boundaries.md) documents these boundaries.

## October 4, 2026 — Windows launch prerequisites

The user could not run the prototype on the current Windows machine. `npm run tauri -- dev` reproduced `cargo metadata ... program not found`: native Windows Rust/Cargo and Microsoft C++ Build Tools were absent; the earlier Rust checks used WSL's separate toolchain.

Installed Rustup through the official winget package and selected Rust 1.99.0 with rustfmt/Clippy. Native `cargo --version` and `rustc --version` now succeed. `cargo test --locked -p focus-core` reaches compilation but fails with **`link.exe not found`**, confirming the remaining C++ prerequisite. The C++ workload installer returned **1602 (cancellation)** while requesting administrator access; the workload was not installed. No native Windows build or launch success is claimed.

The [desktop README](../../desktop/README.md#windows-first-time-setup) now supplies explicit Windows installation commands, administrator/PATH restart instructions, and explanations for missing Cargo/linker errors. Complete the C++ workload installation, restart the IDE/terminal, then rerun the native build and launch checks. The prototype and legacy data were not modified by these checks.

## October 5, 2026 — Windows integration and installed-build validation

The user confirms that Windows development launch works and requests the next steps, scoped to Windows. macOS/Linux-specific work will be completed when the user is on those machines. Their support remains mandatory; this batch does not close M1's three-platform gate.

### Resulting behavior

- Native Rodio/CPAL audio replaces Web Audio. Main, compact and tray sessions use the same backend completion path; output-device errors are visible. Volume/mute and cancellable preview are available in Settings. Notification opt-in and OS-controlled delivery are explained without treating the desktop plugin's permission result as actual delivery proof.
- Optional editable timer/open-window global shortcuts register through the native plugin and share normal commands. Conflicts keep previous settings/bindings. Windows UI Automation verifies real key presses while a separate test window owns foreground focus.
- SQLite schema 2 adds validated desktop preferences and window placement. A transactional schema-1 upgrade preserves sessions/checkpoints. Placement writes are debounced; normal exit flushes pending placement. Compact pinning is persisted and synchronized with Settings; work-area clamping handles removed/negative-coordinate monitors.
- Compact text supports 100/125/150/200% and automatically grows instead of clipping long stopwatch digits. Manual edge resizing is disabled. Native Windows tests exposed shadow-related height inflation at 125% DPI; disabling compact shadows fixes its client area to **200 × 44 logical pixels**. Native accessibility Invoke, ordinary click, double-click and Enter now reopen main.
- A hidden top-level Windows listener pauses/checkpoints on suspend and lock. It captures notification time before queueing, so delayed processing excludes suspension. Its response wait is limited to one second; write failures/timeouts are reported asynchronously. Wake/unlock remains paused until explicit resume. Persistence still has the documented crash/failed-write boundaries.
- Vite ignores Rust source/build and generated test files, preventing Windows watcher lock errors during concurrent frontend/native development. The native library uses an `rlib` with a distinct name, eliminating unnecessary desktop DLL output/PDB collisions.
- Settings drafts merge backend changes into unedited fields. Compact sound/pin changes therefore reach the main form without discarding an unsaved duration or volume edit; timer ticks do not replace an unchanged draft.

### Verification

Environment: Windows 11 Home 10.0.26300 x64; 120 DPI (125%); Rust 1.99.0, Node 24.19.0/npm 11.17.0, Python 3.12.15, Microsoft C++ Build Tools and WebView2. Base revision `1c362b9` plus working-tree changes.

| Check | Result |
| --- | --- |
| Production frontend | Passed; zero Svelte errors/warnings |
| Rust core/store/service | 16 passed, including delayed suspend processing, frozen interruption duration and schema-1 upgrade |
| Native preferences/geometry unit tests | 4 passed |
| Vitest / Playwright | 6 / 6 passed |
| rustfmt / Clippy | Passed, normal and smoke-feature targets; warnings rejected |
| Native rendered-control/IPC smoke | Passed: main/compact UI, finish dialog, SQLite, pin/text propagation, clamping, Windows suspend/lock messages and shortcut conflict/registration |
| Normal release executable / Windows UI Automation | Passed: real controls, 200 × 44 compact at 125% DPI, accessible minimized-main reopen, real background shortcuts, second-instance activation, driver absence and paused restart recovery |
| Unsigned NSIS package | Built; current-user install, registry location, installed normal-build UI journey and uninstall verified with isolated profiles |
| Audio / notification API | Output device accepted native playback; installed notification request returned without an error |

The user missed the audio/notification test; hearing and receipt remain unconfirmed. Real suspend/wake and lock/unlock, Narrator, tray visibility, monitor removal and other display scales require manual Windows checks. The separate native smoke simulates OS messages; it does not suspend or lock the user's machine. Its successful exit logged a WebView2 class-unregistration warning (1412), with no failing assertion or record discrepancy.

`desktop/scripts/windows_ui_smoke.py` drives normal artifacts through UI Automation and uses disposable SQLite data. `windows_install_smoke.ps1` refuses to replace an existing beta installation, verifies a workspace-contained target and retains app data during silent uninstall. CI now exercises the installed normal Windows artifact separately from the nondistributed smoke-feature executable. Remote results for this updated workflow are pending.

See [ADR 0002](architecture/0002-windows-integrations.md), the [Windows platform record](platform-validation.md), [machine-readable evidence](windows-validation-2026-10-05.json), and updated [desktop instructions](../../desktop/README.md). The unsigned installer is under `desktop/target/release/bundle/nsis/`; generated binaries, test environments and reports remain ignored. No release, signing, remote sync conversion or legacy-data migration was performed.

## October 5, 2026 — MVP task flow, daily summary, and compact close

The user narrowed the target to high-impact MVP behavior and explicitly removed old Python/JSONBin data migration from scope. Windows remains the first development/acceptance platform; Windows, macOS, and Linux remain mandatory before MVP completion. Projects, cloud sync, import/export, and reset-today remain deferred; Reports and appearance options were selected for MVP in the later feature batch below.

### Implemented

- Compact Escape and the native context menu now hide only the compact window. The application keeps running, the timer continues, and closing no longer unexpectedly focuses the main window. The compact strip retains one visible timer action.
- SQLite schema 3 adds task records and session task snapshots. The task view supports add, rename, complete/uncomplete and remove. Selecting a task applies to the next session; active sessions retain their original task title in history even if that task is later edited or removed.
- The timer page now shows today’s local-calendar-day focus total split into Pomodoro and stopwatch time/session counts. The summary queries all stored records while the Sessions view remains a concise latest-20 list.
- MVP/backlog, UI compact behavior, contributor guidance and desktop README now reflect that old-data migration and sync are deferred.

### Validation

`npm run build` passed with 0 Svelte errors and 0 warnings; `cargo check --locked --workspace --all-targets` passed on Windows. No test suite or installed-package/manual Windows acceptance was run for this change. UI behavior, task history attribution, local-day/DST boundaries and the new SQLite migration still need runtime acceptance. Existing Windows physical power/accessibility/monitor/audio/notification checks remain open; macOS/Linux work is deferred until the user is on those platforms.

### UI readability refinement

Removed the timer page's “A MOMENT TO BEGIN” message card and increased the main application typography, including headings, controls, labels, summaries, and muted text. Compact mode sizing and its minimal controls are unchanged. `npm run build` passed with 0 Svelte errors and 0 warnings; no runtime screenshot review was performed for this refinement.

## October 5, 2026 — Reports, automatic transitions, appearance, and demo profile

Removed the promotional page header from Tasks, Sessions, Reports, and Settings. Timer keeps its header and Compact mode entry point.

- Reports query all saved sessions in a selected local-date range (separate from the 20-row recent-session preview), provide week/month presets, custom dates, aggregate and per-day focus summaries, session details, and CSV download.
- The optional auto-start preference starts the next focus/break phase only after automatic natural completion. Manual finish/skip and stopwatch do not auto-start. The finished record and next active checkpoint are saved atomically.
- Desktop preferences now include dark/light, main-window scale, reduced motion, and opacity settings. Compact text scaling remains independent. Native transparency and color appearance still require installed Windows, macOS, and Linux checks.
- Added `desktop/scripts/seed_demo_profile.py`; it idempotently adds 4 tasks and 57 synthetic sessions across the last 28 local calendar days to the selected beta profile, preserving existing settings and records. The current Windows beta profile increased from 2 to 6 tasks and from 8 to 65 sessions. Samples cover focus, short/long breaks, stopwatch, completed, skipped, and interrupted outcomes.

### Verification

`npm run build` passed with 0 Svelte errors/warnings. Playwright passed 8/8 UI checks, including subpage header removal, report detail/CSV download, and persisted appearance preferences. Vitest passed 6/6; Rust core passed 20/20, including date-range queries beyond the latest-20 limit, old-settings compatibility, and manual-versus-automatic completion; native Rust tests passed 4/4; rustfmt and workspace Clippy passed. The demo seeder added 61 rows (4 tasks and 57 sessions) to the existing Windows beta profile, then added 0 rows on a second run. Browser fixture tests do not establish native CSV delivery or native transparency/color output; restart the app to review its seeded Windows profile. macOS/Linux acceptance remains pending until those platforms are available.

## October 5, 2026 — Simplified pages and consistent typography

- Removed the Sessions page; Reports is the only session-history view. Removed CSV export, Details actions, and their unused frontend code/styles.
- Replaced calendar-week/month presets with **Last 7 days** and **Last 30 days**, including today and the preceding 6/29 local dates. Custom date ranges remain inclusive.
- Removed the timer's promotional heading and sidebar badge/slogans. Compact mode is available once in the sidebar on every page; navigation resets page scroll and the sidebar stays accessible during long-page scrolling.
- Standardized main-window text: 16 px body/labels/controls/table text, 20 px section titles, 14 px hints, and 32 px summary metrics. Shortened repeated explanatory text, checked both themes, and improved light-theme borders/completed-task contrast. Compact keeps its independent typography and geometry.
- Extended the seeder to two calendar months: August 6–October 5 for this run. Added 66 sample sessions to the existing Windows beta profile, bringing the generated demo set to 123 sessions. A repeated seed added zero rows.

Validation: production frontend build passed with zero Svelte errors/warnings; all 9 Playwright checks passed. Following final layout/contrast adjustments, the build and the page/theme review check passed again. Reviewed rendered Timer, Tasks, Reports, and Settings in dark/light themes; verified no page-wide overflow at 660 × 520 and retained compact sizing checks. Updated current documentation and browser-fixture screenshots. Native platform appearance remains a separate acceptance check.

## October 5, 2026 - Settings reduction: System section, global shortcuts, reduce motion

- Removed the Settings System section (sound/notification test buttons, platform/tray/data-folder and audio/notification/power status) and its `desktop_info`, `test_notification`, `test_sound`, and `stop_sound` commands. Completion tone and notifications still work; only the manual test UI is gone.
- Removed global shortcut functionality end to end: settings UI, preference fields, registration/conflict handling, the Tauri global-shortcut plugin and dependency (plus its lockfile subtree), and both smoke-harness shortcut probes. Tray and in-app Space remain the only timer controls.
- Removed the reduce-motion preference, its settings checkbox, the `data-reduced-motion` plumbing, and related styles. The OS `prefers-reduced-motion` media query still applies.
- Stored desktop preferences stay compatible: serde ignores the removed keys in existing profiles, so no migration runs.
- Updated the desktop README, backlog, UI spec, implementation plan, and platform checklist to match; historical log entries and validation JSON were left as records.

Validation: svelte-check 0 errors/warnings; Playwright 11/11 including a new absence test for the removed settings (observed failing before the change); Vitest 6/6; desktop Rust lib 4/4 including rewritten preference-validation coverage; focus-core 20/20; smoke-test feature check, rustfmt, and workspace Clippy with -D warnings all clean; touched Python scripts compile. The Windows UI Automation and native smoke harnesses were updated but not executed here; they need an unlocked desktop session and built binaries.

## October 5, 2026 - Text-size removal, compact-only opacity, compact redesign, settings audit

- Removed Main text size and Compact text size modification: settings controls, preference fields, validation, zoom/text-scale plumbing, and related tests. Text renders at fixed sizes; old stored scale keys are ignored.
- Replaced Window background opacity with Compact mode background opacity (60-100%). Main-window surfaces are solid; the setting now drives the compact strip background only.
- Simplified compact mode: no phase dot, no right-side padding, a smaller 32 px action button with a smaller icon, and a context menu reduced to open/pin/sound/close (finish and exit removed). The 200 x 44 target, drag, keyboard handling, and auto-grow for long stopwatch hours are unchanged.
- Audited the four remaining settings buttons: both Save buttons were already covered by passing persistence tests, and a new reset test proves both Reset buttons restore saved values. No button defects found.

Validation: svelte-check 0 errors/warnings; Playwright 13/13 including new absence and reset tests (absence observed failing before the change); Vitest 6/6; desktop Rust lib 4/4; smoke-test feature check, rustfmt, and workspace Clippy with -D warnings all clean.

## October 5, 2026 - Compact opacity fix, settings autosave, close-to-tray

- Fixed Compact mode background opacity having no visible effect: the compact window was not transparent, so per-pixel alpha never composited. Added the transparent flag; a new Playwright test asserts the compact background follows the setting. Installed-app confirmation still needed.
- Settings now save automatically 500 ms after the last edit with a Saving/Saved indicator; invalid timer values are skipped until corrected. Both Save buttons were removed; Reset buttons and Enter-to-save remain.
- "Close compact timer" moved to the top of the compact context menu.
- "Keep compact timer on top" was already default-on in code and applied at startup; the reporter's profile has it stored off, so no change was needed.
- Added close-to-tray: closing the main window hides it to the tray by default while the timer keeps running. The behavior is a persisted setting (default on, including for old profiles via a serde default), tray left-click restores the window, and tray Exit still quits. The Windows UI Automation harness now opts out before its close-and-exit checks.

Validation: svelte-check 0 errors/warnings; Playwright 14/14 including new autosave, opacity, and absence coverage (Save-button absence observed failing before the change; reset timing made deterministic with fake clocks); Vitest 6/6; desktop Rust lib 5/5 including the close-to-tray default test; smoke-test feature check, rustfmt, and workspace Clippy with -D warnings all clean; touched Python script compiles. The Windows UI Automation harness was updated but not executed here.

## October 5, 2026 - Restore-defaults replaces dead reset buttons

- Diagnosis: with autosave, Reset (restore from the last-saved snapshot) is a no-op 500 ms after any edit, which is why the buttons looked broken. Probes confirmed an immediate reset still reverted and cancelled the pending save, while a post-save reset changed nothing.
- Reworked both buttons into "Restore defaults" / "Restore desktop defaults": they fetch authoritative defaults from new `timer_defaults` / `desktop_defaults` commands, ask for confirmation, and persist immediately through the autosave path.
- Synced the banner-dismiss test and Windows UI Automation matcher with the shortened recovery copy ("Your previous session was restored.").

Validation: svelte-check 0 errors/warnings; Playwright 14/14 (restore-button absence observed failing before the change); desktop Rust lib 5/5; rustfmt and workspace Clippy with -D warnings clean; touched Python script compiles.

## October 5, 2026 - Checkbox hit area fix

- Settings checkbox rows were full-width labels, so clicking empty space anywhere on the row toggled them. Constrained `.checkbox-row` to its content width; task-list checkboxes were already content-width and needed no change.

Validation: Playwright 15/15 including a new test that clicks empty row space (observed failing before the fix) and the label text.

## October 5, 2026 - Notifications on by default

- "Send completion notifications" is now checked by default for new profiles. Existing profiles keep their stored choice; docs updated from opt-in to on-by-default wording.

Validation: desktop Rust lib 5/5 including the new default assertion (observed failing before the change); Playwright 15/15 with mocks mirroring the new default.

## October 5, 2026 - Focus task dropdown locked to idle

- The timer-page task dropdown is now enabled only when no session is running (idle); it locks during running and paused work so the task is chosen before starting. Backend `select_task` stays permissive so completing or removing the selected task can still clear it mid-session.

Validation: svelte-check 0 errors/warnings; Playwright 16/16 including the new lock test (observed failing before the fix).

## October 5, 2026 - Focus task picker hidden while running

- The Focus task label and dropdown now render only when the timer is idle; they disappear during running and paused sessions and return when the session finishes. The "Current session" line still shows mid-run. Supersedes the idle-lock with full hiding per user request.

Validation: svelte-check 0 errors/warnings; Playwright 16/16 including the replacement visibility test (observed failing before the fix).


## October 5, 2026 - Last session card under Next session

- The timer page sidebar now shows a "Last session" card directly under the next-session block. It summarizes the most recent session record (task title, phase, active time, outcome) and shows "No sessions yet." when no records exist. Reuses the existing next-card style with no new CSS.

Validation: svelte-check 0 errors/warnings; Playwright 17/17 including the new last-session test (observed failing before the fix).



## October 5, 2026 - Reports table refreshes when sessions land mid-view

- Root cause: the report query only re-ran on page visits, preset clicks, or Apply dates. When a session completed while Reports was already open (auto-start chain or finishing from the compact window), the snapshot callback and session-completed handler reloaded only the Today totals, leaving the table, totals, and day chart stale. Added a refreshReportIfVisible helper (reports page visible, previously loaded, valid date range) called from both triggers; invalid mid-edit ranges skip silently instead of erroring.

Validation: svelte-check 0 errors/warnings; Playwright 18/18 including the new mid-view refresh test (observed failing with a frozen 3-row table before the fix).



## October 5, 2026 - Report table reordered with newest-first rows

- Report table columns are now Start time, Session, Task, Active time, Outcome (the Started header was renamed to Start time). Rows render from a derived newest-first sort on started_unix_ms, so the display is descending even if rows arrive unordered; the backend ORDER BY started_unix_ms DESC remains as the first guarantee.

Validation: svelte-check 0 errors/warnings; Playwright 19/19 including the new column-order/sort test (observed failing on the old header order before the fix).



## October 5, 2026 - Reports default to Today with active presets; Settings can reset reports

- Reports now open on Today. A Today preset joins Last 7 days / Last 30 days; the preset matching the selected range is highlighted via aria-pressed (same pressed styling as the mode switch, both themes), and custom ranges highlight nothing. The highlight derives from the selected dates, so manual edits and day rollover stay truthful.
- Settings has a new Session data card with a confirmed Reset reports action. The backend reset_reports command clears the sessions table and the worker record cache, bumps the revision, publishes a fresh snapshot to all windows, and the UI reloads Today totals (Reports reloads on next visit).
- Also fixed the Playwright spec file, which had accumulated thousands of blank lines from a CRLF double-translation bug in prior append scripts; it is back to 366 clean lines. The new reset test needed the dialog-first click pattern because window.confirm blocks the click promise.

Validation: focus-core 22/22 (new store + service reset tests), desktop lib 5/5, Vitest 6/6, svelte-check 0/0, Playwright 20/20 (rewritten preset test, new reset test), rustfmt and clippy -D warnings clean. Docs (README, backlog, plan, ui-design-spec) updated; spec table-column list corrected to start time, session, task, active time, outcome.

