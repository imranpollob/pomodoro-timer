# Pomodoro Timer: project review and upgrade proposal

Review date: October 4, 2026. Required outcome: a high-quality desktop application for **Windows, macOS, and Linux**. This requirement governs the architecture and release plan.

Implementation follow-up: [phased plan and product mockups](../implementation/implementation-plan.md), with a [reviewable task backlog](../implementation/backlog.md).

## Recommendation

Build toward **Tauri 2 + Rust + Svelte/TypeScript + SQLite**, with a small platform integration layer and an offline-first product. First fix the current app's data-loss and timing defects, then validate the proposed stack on all three operating systems before committing to the replacement. Keep **Python + PySide6/Qt** as the fallback if the prototype exposes unacceptable desktop integration or accessibility problems.

A rebuild is reasonable because the current application is small and most behavior lives in one UI class. However, changing languages alone will not fix timer semantics, unsafe writes, sync conflicts, or release quality. Those requirements must be designed and tested explicitly.

The most promising product direction is a **compact focus companion that combines Pomodoro, stopwatch, task-linked time tracking, useful statistics, and optional sync**. Preserve the current app's small always-visible timer as a first-class experience.

## Scope, evidence, and limitations

Reviewed the project's Python source, tests, settings, screenshots, dependency files, installers, and release workflow. Reviewed all three local reference repositories, focusing on timer engines, storage, desktop adapters, UI state, features, tests, and packaging. Checked GitHub metadata, release assets, selected public issue reports, and official framework documentation.

The GitHub compare API reported each local reference checkout identical to its default branch during this review. The recorded commits make the code findings reproducible:

| Project | Reviewed version / commit | GitHub stars observed | Distribution evidence |
| --- | --- | ---: | --- |
| Our app | 0.3.1; `8ed689f3e101181c370ea47377a24fa94bbfb465` | Not used as a quality metric | Release workflow builds Windows installer, macOS app ZIP, Linux amd64 DEB |
| [FocusTimer](https://github.com/focustimerhq/FocusTimer) | `c2e3dffb4c42fd00294750ea35d91d3886ce3bee`; NEWS describes 1.1.5 | 2,267 | Flatpak and distro packages described; GitHub releases API returned no releases |
| [Pomatez](https://github.com/zidoro/pomatez) | 1.11.0; `c2727800c6272573590911e9ee81637b89e55d5f` | 4,906 | Stable Electron packages and Tauri beta packages on the same release |
| [Pomotroid](https://github.com/Splode/pomotroid) | 1.7.1; `f9f0b266f7a04b895599ca660544219c0d0df054` | 5,525 | Windows installer/EXE, universal macOS DMG, Linux AppImage/DEB/RPM |

Stars are evidence of interest and longevity; they do not prove correctness, performance, accessibility, or platform parity. Values above are a dated observation, stored in [upstream-snapshot.json](upstream-snapshot.json).

Validation performed:

- Installed the project's locked dependencies into an ignored `.venv`, using Python 3.12.15. The default shell initially had neither `uv` nor the project dependencies available.
- Ran the existing suite: **43 tests passed in 5.75 seconds**.
- Ran seven additional deterministic probes against the existing implementation, using temporary files and fake UI widgets. All seven reproduced the findings described below.
- Measured history append cost with synthetic datasets and five appends per dataset.

The reference apps were not built or benchmarked. There is no measured ranking of their RAM, CPU, startup time, or battery use. Their performance discussion below is architectural analysis. Public issue reports are attributed reports, not independently reproduced failures. Existing screenshots were inspected; this was not a live accessibility or three-OS GUI certification.

Reproducible evidence: [review_probes.py](review_probes.py), [probe-results.json](probe-results.json). These probes document current defects and are deliberately separate from the production test suite.

## 1. Current project review

### Strengths worth preserving

The app has a clear purpose and a small interaction surface. It supports configurable work and break cycles, an endless stopwatch, editable tasks, daily totals, adjustable timer text, transparency on supported platforms, and a compact timer view. The stopwatch and task sync already give it useful capabilities absent from some references.

The dependency graph is modest: ttkbootstrap/Tk, requests, and a macOS-specific Cocoa dependency. Python is not intrinsically unsuitable for this workload. A correct timer needs very little computation.

Storage and JSONBin communication are already separate modules. Sync runs in a worker thread, with a request timeout, a local snapshot, debouncing, and a guard against overlapping local sync jobs. Deletion tombstones show awareness of multi-device behavior. These are useful starting decisions, although their implementation needs stronger guarantees.

Packaging is already automated for all three operating systems. Versioning reads `pyproject.toml`. The Linux release job installs its DEB and runs an Xvfb launch smoke test. Windows installation is per-user and does not require elevation. Headless fake widgets make the existing behavior testable.

### Confirmed defects and their consequences

| Priority | Finding | Evidence | Consequence / recommended correction |
| --- | --- | --- | --- |
| P0 | An in-flight sync can overwrite newer local edits | `src/pomodoro.py:548` takes a snapshot; `:572` replaces current todos with the old merged result. Probe changes a title during sync and receives the old title afterward. | Merge the response against current local revisions in a transaction; preserve an outbox until the relevant revision is acknowledged. Queuing another sync alone does not recover an edit already overwritten. |
| P0 | Corrupt history is silently treated as empty and overwritten | `src/storage.py:79` returns `[]` on read failure; `:88` then writes a new history list. Probe supplies truncated JSON and logs one session. | Preserve the damaged file, report the failure, recover from a backup, and never silently replace unknown existing data. |
| P1 | Rapid pause/resume can create multiple ticking loops | `src/pomodoro.py:823`, `:834`, `:917`: pause does not cancel the callback; resume calls `update_timer()` immediately. Probe sees two scheduled callbacks, zero cancellations, and an old callback reducing the resumed timer. | One scheduler handle, cancellation on every transition, and a generation/token check rejecting stale callbacks. |
| P1 | Countdown accuracy depends on callback delivery | `src/pomodoro.py:925` subtracts one second per callback. | UI stalls and delayed callbacks extend the timer. Calculate elapsed time from an authoritative monotonic clock and deadline instead of callback count. |
| P1 | Changing duration settings during a session corrupts accounting | `src/pomodoro.py:700` mutates settings while running; `:873` derives elapsed duration from the new setting. Probe changes a 25-minute session to 30 minutes after one minute and records **360 seconds instead of 60**. | Snapshot configuration at session start; explicitly apply new durations to the next session unless the user requests an adjustment. |
| P1 | An invalid long-break interval crashes completion | `src/pomodoro.py:707` accepts any integer; `:955` performs modulo by the interval. Probe uses zero and gets `ZeroDivisionError`. | Typed settings schema with bounds and visible validation errors. Validate loaded settings and IPC inputs as well as UI entries. |
| P1 | Deletions can reappear after a device stays offline | `src/sync.py:8`, `:79` purge tombstones after seven days; `:55` retains items present on only one side. Probe reconnects an old live item after its tombstone was purged. | Garbage-collect deletions only after acknowledgement by relevant devices, or require stale devices to rebase from a full snapshot. |
| P1 | Timezone-aware sync timestamps crash tombstone cleanup | `src/sync.py:90` uses a naive cutoff; `:97` may parse an aware timestamp. Probe gets `TypeError`. | Normalize timestamps to UTC and validate the schema. The worker currently catches `ValueError` and request errors, not this `TypeError`. |

P0 here means data protection comes first; P1 means timer correctness and reliability must be addressed before a major feature release. The latter five non-drift rows plus the first two rows are the seven executable probes; drift is a separate source-level finding.

Additional weaknesses observed in code:

- **JSON writes are not atomic.** Settings, tasks, and history use direct truncating writes, with no transaction, file locking, fsync/replace protocol, or backup. Multiple app instances can race. Exceptions are generally printed, which is ineffective in a windowed packaged app.
- **History grows without efficient queries.** Every session append reads and rewrites every previous session. Opening the daily report reads all history and filters it on the UI thread.
- **Task rendering rebuilds every row.** `render_todos()` destroys and recreates all widgets after a small edit. This is reasonable for a short list but causes unnecessary work and risks losing edit state as lists grow.
- **Sync does whole-document GET/merge/PUT.** The client does not use any server-side revision or conditional write. Two devices can read the same old version and the later PUT can discard the other device's new data, despite the local merge logic.
- **IDs and ordering depend on clocks.** Millisecond timestamp IDs can collide across devices. Naive ISO timestamp strings do not establish a trustworthy ordering across timezones, clock skew, or differently formatted timestamps.
- **Malformed task objects are insufficiently validated.** The HTTP client checks the top-level list, but merge/render assume required keys. Missing IDs or incompatible fields can raise errors outside the worker's current catch list.
- **Credential storage is plaintext.** JSONBin access keys are stored in settings JSON. Put credentials in the OS credential store and redact them from diagnostics.
- **Stopwatch display and recording use different clocks.** The display increments per callback, while logging uses `datetime.now()` differences. They can disagree, and wall-clock changes affect recorded durations.
- **Sleep, crash recovery, and restart semantics are undefined.** There is no persisted active timer state or explicit OS suspend/resume adapter. Closing logs a partial session; a crash can lose active-session progress.
- **Statistics have limited semantics.** There is no completed/interrupted distinction or task association. The report's total session count includes any logged break records. Automatic break completion does not log breaks, while skip/close can log partial breaks. Dates reflect logging time; sessions crossing midnight are not split.
- **Desktop feedback is inconsistent.** Linux invokes `paplay` through a shell; Windows/macOS use the system bell. Linux package metadata declares no dependency on the external player. There are no native completion notifications or tray controls.
- **UI and logic are tightly coupled.** The approximately 1,125-line `PomodoroApp` contains timer transitions, windows, task operations, sync orchestration, reporting, and platform branches. Existing tests mirror several implementation details and miss the concurrency scenarios above.

### Measured performance finding

Current `StorageManager.log_session()` benchmark, Windows 11 / Python 3.12.15, synthetic equal-sized session records, median of five appends:

| Existing records | Median append time | Approximate history size after appends |
| ---: | ---: | ---: |
| 100 | 13.5 ms | 15.8 KB |
| 10,000 | 121.5 ms | 1.50 MB |
| 100,000 | 1,153.7 ms | 15.0 MB |

These are local end-to-end file read/parse/write timings, not universal predictions. Antivirus, filesystem caching, record shape, and hardware affect them. The important finding is the **linear full-file work on the UI thread**. SQLite inserts and indexed date-range queries address this without requiring a language change.

### Cross-platform and distribution gaps

The project builds on three OS runners, but the release workflow does not run pytest or gate pull requests. Only Linux has an installed-app launch check. There is no explicit Windows ARM64, Linux ARM64, or macOS universal/two-architecture matrix. A moving `macos-latest` runner does not establish Intel support.

The Linux package is amd64-only, built on Ubuntu 24.04, and has no declared runtime dependencies; compatibility with other distributions or older glibc is not established. macOS uses a ZIP and has no configured signing/notarization. Windows installers have no configured code signing. There is no updater, checksum publication, rollback process, or automated upgrade/migration check.

The PyInstaller spec builds a one-file executable. This extracts support files at startup; the official documentation identifies a startup tradeoff compared with one-folder bundles. Measure a one-folder installed build before attributing slow startup to Python itself. [PyInstaller operating modes](https://pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works).

macOS settings use `~/.config`, instead of a platform-specific application support location; Linux does not honor a configurable XDG path. Move toward appropriate platform directories with legacy-data discovery. Fonts, emoji controls, transparency, mixed DPI, multi-monitor positions, screen readers, and keyboard-only use need actual OS testing.

Repository polish also needs attention: no project LICENSE was found, the description remains a placeholder, and Linux maintainer metadata uses an example email. The README is useful but should state tested OS/architecture combinations, expected platform limitations, privacy behavior, and recovery/export options. `.gitignore` excludes `uv.lock`, `.python-version`, and `*.spec`, although the current lockfile/version/spec are already tracked; those entries do not remove tracked files, but can hide future files that should be committed.

## 2. FocusTimer review

### Architecture and strengths

FocusTimer uses **Vala/C, GTK 4, libadwaita, GLib, Gom/SQLite, GStreamer, and Meson**. The source separates timer state, sessions, scheduling, statistics, notifications, sound, desktop providers, and UI. Plugins handle GNOME, KDE, XFCE, freedesktop services, portals, Wayland, status notifier indicators, and media integration.

Its most valuable lessons are below:

- **Timekeeping and sleep are explicit.** `src/core/timer.vala` bridges monotonic and real time, aligns display ticks, calculates remaining time from state, removes scheduler sources, and reacts to a sleep monitor. Sleep time is excluded through offsets. This is a substantially stronger model than callback counting.
- **Session history is a domain model.** There are time blocks, gaps, session objects, timezone history, and separate stats management. This supports meaningful accounting across interruptions and local-time changes.
- **Data protection is designed in.** `src/core/database.vala` includes schema migrations, SQLite health checking, preserving corrupted databases, restore from backup, and backup creation through SQLite's backup API and a temporary destination.
- **Desktop integration is modular.** The portal global-shortcut provider is particularly relevant to Linux Wayland. Notification, lock, idle, overlay, and background behavior have separate providers instead of scattered UI conditionals.
- **Tests cover the core concepts.** Meson defines 22 test executables spanning timer, timezone, sessions, stats, database, scheduler, event bus, notifications, and actions. This is breadth of test targets, not an executed test count.

Feature strengths include break overlays, a compact timer, statistics over longer periods, ambient/alert sounds, idle and lock integration, configurable actions, CLI/D-Bus control, and deeper GNOME integration. The local NEWS also describes recent media integration and desktop improvements.

### Performance assessment

Compiled application logic and event-driven GLib scheduling provide a sensible foundation for a background timer. Database queues and separation between core and UI help keep long work out of display callbacks. However, a native toolkit does not guarantee low CPU: NEWS 1.1.4 specifically records a fix for excessive CPU in the statistics view. This demonstrates why actual workload profiling still matters.

### Weaknesses and constraints

1. **It does not meet our platform requirement.** The product and its integrations target Linux desktop environments. Adopting its stack as-is would make Windows/macOS delivery a substantial porting project.
2. **Its environment assumptions are strong.** The build requires GTK >=4.18 and libadwaita >=1.7. Deep desktop integrations increase dependencies and compatibility work.
3. **It has less task-management breadth than our desired product.** A named/task-linked workflow, richer task lists, and cross-device task sync are not established by the reviewed implementation.
4. **The architecture is relatively complex for our current size.** Its provider framework and expression/automation machinery should inspire small interfaces, not be copied wholesale into an MVP.
5. **Documentation can lag behavior.** README says Flatpak lacks custom-script automation, while NEWS 1.1.5 says the automation panel is now available there. Verify packaged functionality rather than assuming README/NEWS agree.
6. **License differs.** The repository declares GPL-3.0, while Pomatez and Pomotroid declare MIT. Reimplement the useful ideas independently unless GPL distribution is intentionally chosen; do not casually transplant its source into a differently licensed project.

Public issues include sleep behavior preferences, timer presets, and named tasks. Some are inherited from older gnome-pomodoro releases and do not establish current defects. [FocusTimer issues](https://github.com/focustimerhq/FocusTimer/issues).

**Borrow:** timer/sleep semantics, safe backup and recovery, timezone accounting, platform providers, and meaningful core tests.

**Avoid adopting as our base:** its Linux-centered product stack and the full complexity of its plugin/automation architecture.

## 3. Pomatez review

### Architecture and strengths

Pomatez has **React/TypeScript with Redux**, a renderer shared by **Electron** and a newer **Tauri 2/Rust** backend, and a workspace structure for shared IPC events. Its published 1.11.0 release includes stable Electron artifacts and explicitly named Tauri beta artifacts. Treat those paths separately when assessing readiness. [Pomatez 1.11.0 release](https://github.com/zidoro/pomatez/releases/tag/v1.11.0).

Its product strengths are the richest of the three in everyday focus workflow:

- Task lists with cards, descriptions, reordering, completion, priority selection, and undoable task state.
- Scheduled special breaks such as lunch, alongside standard cycles.
- Full-screen breaks, strict mode, voice cues, advance notifications, auto-start work, and compact mode.
- Tray progress, close/minimize to tray, always on top, launch at login, theme settings, and localization.
- Extensive packaging across architectures, installer formats, and operating systems.

The connector boundary makes the renderer's system actions explicit, which is worth borrowing. User control over animation and behavior is also valuable for a background utility.

### Performance assessment

The Electron path includes Chromium/Node and their process model. That introduces a runtime footprint relevant to a small timer, although its size and memory use were not measured here. [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model).

The Tauri path reduces dependence on bundled Chromium, but it shares the same timer design. `CounterContext.tsx` calculates elapsed differences using `Date.now()`, an improvement over blind one-second subtraction. However, the timer still belongs to the renderer. The effect repeatedly recreates intervals as `count` and `lastCountTime` change, and its `count % 1` interval can be zero at integer counts. This deserves profiling and clock-change tests; it is not a measured CPU defect.

`useTrayIconUpdates.tsx` creates a canvas/image, rasterizes SVG, encodes a PNG data URL, and sends it to the backend as progress changes. A backend-rendered/cached tray icon with limited updates avoids much of that work. `store.ts` serializes complete config/settings/task state to localStorage with a one-second debounce. This reduces write frequency but still uses whole-state persistence and a delay before durability.

### Weaknesses and constraints

1. **Two desktop backends increase maintenance.** System behavior, IPC, packaging, signing, updates, and tests need parity between Electron and Tauri. Our small project should choose one primary runtime after validation.
2. **The UI toolchain carries older generations.** Reviewed manifests use React 16, Create React App/react-scripts, TypeScript 4.9, and older supporting packages. This is migration/maintenance work, not proof of an exploitable vulnerability.
3. **Authoritative timing remains in the renderer.** Renderer stalls, wall-clock jumps, special-break scheduling, and lifecycle changes can affect behavior. Rust backend code alone does not solve that.
4. **Persistence is not a task/session database.** localStorage and debounced state writes do not provide the transactional outbox, migrations, backup/recovery, or indexed history needed for our target.
5. **Statistics are a gap.** The reviewed source does not expose a comparable session analytics subsystem. A public request asks for work/break tracking. [Statistics request #698](https://github.com/zidoro/pomatez/issues/698).
6. **Full-screen breaks have a documented monitor limitation.** The README states they do not cover multiple monitors. A long-running issue discusses it. [Multi-monitor breaks #89](https://github.com/zidoro/pomatez/issues/89).
7. **Security defaults require care.** Tauri config has `csp: null`. The Electron path does use context isolation; do not infer that it has no security controls. A new build should have explicit scoped capabilities and a CSP.
8. **Testing is uneven.** An Electron full-screen test exists. I found no dedicated renderer test files in the reviewed tree; the Tauri build workflow contains a comment about adding basic testing. Do not treat the package's test script as comprehensive coverage.

**Borrow:** task-list ergonomics, task descriptions, undo, special breaks, opt-in strict/overlay behavior, advance notifications, and a platform-action boundary.

**Improve beyond it:** reliable backend timing, session analytics, transactional storage, and one validated runtime.

## 4. Pomotroid review

### Architecture and strengths

Current Pomotroid uses **Tauri 2 + Rust + Svelte 5/TypeScript + SQLite**. It is the closest match to the proposed architecture. Older descriptions of Pomotroid as an Electron/Vue application would mischaracterize the checked-out project.

The Rust core has separate timer engine/sequence/controller, database migrations/queries, typed settings, audio, tray, shortcuts, notifications, themes, and optional WebSocket integration. Svelte receives timer snapshots rather than owning the countdown.

Specific strengths:

- **Background timing independent of rendering.** The engine thread uses `Instant` and schedules against absolute tick targets with command channels. Idle/paused phases block on input instead of polling continuously.
- **Explicit transitions.** Start, pause, resume, reset, skip, reconfigure, suspend, wake, and shutdown are commands with corresponding events. Sequence logic is separate.
- **SQLite with migrations and indices.** Sessions/settings have an explicit schema; migrations are transactional and tested. WAL is enabled.
- **Rich focused UI.** Themes, OS appearance, localization, compact controls, dynamic tray progress, native notifications, configurable shortcuts, audio, and detailed statistics are implemented.
- **Practical diagnostics and packaging.** Rotating logs, three-OS CI builds, universal macOS output, and several Linux formats are useful examples. Linux CI runs type checking, Clippy, and Rust tests.
- **Optional integrations.** The local WebSocket server is disabled by default and binds loopback. This can support a streaming overlay without forcing a cloud service.

### Performance assessment

This is the strongest reference for separating timing from UI workload. SQLite avoids rewriting complete history; Svelte reactive state receives small snapshots. Tray icons are rendered in Rust with tiny-skia rather than passed through the renderer as base64 images.

There are still opportunities to improve. One mutex wraps the SQLite connection, serializing access at the application layer even though WAL is enabled. Some stats queries apply local-date functions to `started_at`; ordinary timestamp indices may not provide the range filtering those queries need. Prefer a dedicated database worker, timestamp bounds, and explain-query-plan measurements for large datasets.

The engine catches up by delivering overdue ticks against its fixed schedule. Our replacement should derive elapsed duration directly and coalesce UI updates after a large stall. Its pause state also captures whole ticks rather than subsecond elapsed position; preserve precise active duration in our design.

### Weaknesses and constraints

1. **Tasks and sync are missing from its core product.** The reviewed schema centers on sessions, settings, and themes. It is not a ready-made replacement for our stopwatch + tasks + sync workflow.
2. **Suspend commands are not equivalent to real OS support.** The engine and controller expose suspend/wake operations and unit tests exercise them, but I did not find an OS adapter calling those controller methods in the reviewed source. Do not copy a tested command and claim end-to-end sleep handling.
3. **Statistics prioritize completed work rounds.** Query totals use completed work sessions. Our existing partial-session accounting is worth preserving and clarifying; a request also asks for interrupted-session tracking. [Request #388](https://github.com/Splode/pomotroid/issues/388).
4. **Linux tray/Wayland complexity remains.** Source contains dependency probes and a workaround for KDE tray initialization. GNOME tray availability is also documented as desktop-dependent. An unavailable tray must never make a hidden app impossible to reopen.
5. **Platform issue reports remain.** Users report macOS secondary-window problems and Ubuntu 22.04 launch failure. These were not reproduced. The macOS issue's claim that `show()` is never called is incomplete: the reviewed settings/stats pages do call it after initialization. Initialization failures can still leave an invisible window, so failure handling needs testing. [macOS report #506](https://github.com/Splode/pomotroid/issues/506), [Ubuntu report #505](https://github.com/Splode/pomotroid/issues/505).
6. **Platform signing and updater signing are different.** README says the app is unsigned; release/config files contain updater signing and Linux signatures. Do not assume those provide macOS notarization or Windows Authenticode. Published release assets and upgrade behavior need verification.
7. **UI maturity still needs OS QA.** Multiple WebViews, fixed-size secondary windows, custom titlebar behavior, screen-reader interaction, and reduced-motion behavior are not certified by backend tests.

**Borrow:** backend-owned timer, separated sequence logic, typed state/events, transactional migrations, themes, diagnostics, and build/test conventions.

**Improve beyond it:** accurate stopwatch and interrupted time, task attribution, backup/recovery, end-to-end sleep adapters, Linux portals, and crash-safe optional sync.

## 5. Feature comparison

“Not established” means no corresponding product feature was found in the reviewed source/docs; it is not a claim that implementation is impossible. Platform-dependent features need runtime verification.

| Capability | Our app | FocusTimer | Pomatez | Pomotroid | Proposed target |
| --- | --- | --- | --- | --- | --- |
| Windows + macOS + Linux product | Builds exist; QA gaps | Linux-focused | Yes; Electron stable / Tauri beta | Yes; integration gaps | Required at every release |
| Compact timer | Yes | Yes | Yes | Yes | Preserve with full keyboard controls |
| Stopwatch | Yes | Not established as equivalent mode | Not established | Not established | Accurate backend mode |
| Task management | Flat todos | Limited named/task workflow | Lists/cards/descriptions/undo | Not established | Projects, task focus, estimates, undo |
| Task-to-session attribution | No | Not established | Priority task display; attribution not established | No task schema | Required |
| Multi-device task sync | JSONBin; correctness gaps | Not established | Not established | Not established | Optional, conflict-aware |
| History and analytics | Daily totals | Day/week/month | Analytics gap | Day/week/heatmap | Task/project trends plus exports |
| OS notifications | Bell / external Linux audio | Desktop providers | Yes | Yes | Native, actionable, permission-aware |
| Tray/menu bar | No | Yes | Yes | Yes | Controls with safe reopen fallback |
| Global shortcuts | No | Desktop/portal providers | Yes; documented limitations | Yes; backend limitations | Native + portal adapters |
| Scheduled special breaks | No | General scheduling/actions | Yes | Not established | After reliable core |
| Break overlay / strict mode | No | Overlay | Both | Not established as equivalent enforcement | Optional with explicit escape |
| Themes/localization | One theme; English | GNOME styling/translations | Themes/translations | Extensive themes/translations | OS theme, accessible themes, translations |
| Backup/recovery | No | Implemented | Not established | Migrations; backup not established | Required |
| External automation | No | CLI, D-Bus, actions | Some integrations | Opt-in WebSocket | Later, scoped local API |

## 6. Upgrade priorities

### P0 — protect users and establish a reliable baseline

1. Fix the sync overwrite and corrupt-history paths immediately in the Python app.
2. Make JSON persistence atomic as a bridge to SQLite; preserve damaged data, surface failures, and prevent conflicting app instances.
3. Replace callback-count timing with an independent timer model; cancel/reject stale callbacks and use monotonic active duration for countdown and stopwatch.
4. Validate all settings and task schemas; snapshot per-session duration settings; normalize UTC timestamps and adopt UUIDs for new task IDs.
5. Stop unsafe seven-day deletion garbage collection. Make legacy JSONBin's multi-device consistency limits explicit until a revision-aware protocol replaces it.
6. Run tests and packaging smoke checks on pull requests and release tags across Windows/macOS/Linux.

### P1 — deliver a professional desktop foundation

| Upgrade | User benefit | Main dependency |
| --- | --- | --- |
| Backend timer state machine with sleep/lock adapters | Accurate sessions while hidden; defined suspend behavior | Platform prototype |
| SQLite with migrations, backup/recovery, active-session checkpoint | Durable history and fast reports | Schema and migration design |
| Tray/menu bar, notifications, local/global shortcuts | Control focus without keeping the main window open | Per-OS capability detection |
| Task-linked sessions and projects | Understand where focus time went | Durable task/session identifiers |
| Clear daily/weekly/monthly statistics; CSV/JSON export | Useful history with completed/interrupted distinctions | Session segments/timezone policy |
| Responsive main/mini layouts, light/dark themes | Polished experience at varied screen sizes | UI design tokens |
| Keyboard navigation, accessible labels, reduced motion, scalable text | Wider usability across all OSs | Actual assistive-technology QA |
| Signed release process and safe updates | Predictable installation and upgrade | Certificates, artifact verification, migration tests |

### P2 — differentiation after the foundation is proven

Add named timer presets, task estimates versus actual time, daily goals, optional reminders, scheduled lunch/movement breaks, and custom sounds. Provide opt-in break overlays with multi-monitor handling and an obvious emergency escape. Strict mode should express the user's preference without claiming OS-level enforcement.

Introduce conflict-aware sync for tasks first, then optionally history/settings. Keep running timers local to each device unless an explicit handoff feature is designed. Add language packs and task search/filters as needed. A local API/stream overlay can come later. Avoid beginning with plugin marketplaces, arbitrary script execution, a mandatory account, or three separate native applications: they expand maintenance before the core is trustworthy.

### Specific performance upgrades to implement

| Change | Current cost addressed | Implementation direction |
| --- | --- | --- |
| Deadline-based timer | Drift and repeated callback chains | Monotonic active segments; one scheduler; display refresh separate from completion |
| Transactional session inserts | Full-history read/rewrite on every session | SQLite append with an explicit database worker and bounded checkpoints |
| Indexed report queries | Reading all history to show today | UTC timestamp bounds; relevant composite indices; inspect query plans |
| Incremental task rendering | Recreating every task widget on a checkbox/edit | Stable keyed rows; pagination/virtualization only when profiling large lists justifies it |
| Load reports/settings on demand | Unnecessary startup work and extra windows | Defer nonessential queries and views; reuse the main UI where practical |
| Limit animation when hidden | Background redraws with no visible benefit | Pause visual interpolation and honor reduced motion; keep the timer independent |
| Render/cache tray states in backend | Repeated SVG/canvas/base64 work seen in Pomatez | Small icon buffers updated at most at useful second/progress boundaries |
| Efficient optional sync | Whole-document transfer and repeated network setup | Persisted outbox, batching, connection reuse, backoff, acknowledgement-based cleanup |
| Profile installed startup | PyInstaller extraction and runtime initialization | Compare one-folder Python baseline against production replacement; measure total process-tree cost |

Apply these according to measured workload. A timer does not need high-frequency polling, task lists do not need virtualization at ten rows, and WAL does not remove an application-level mutex bottleneck.

## 7. Technology decision

| Option | Advantages for this project | Costs / risks | Judgment |
| --- | --- | --- | --- |
| Python + current Tk/ttkbootstrap | Smallest change; existing skills/tests; sufficient timer computation | More custom work for polished UI, accessibility, native integrations; current monolith needs extraction | Good stabilization path; possible final choice if ambitions remain modest |
| Python + PySide6/Qt | Reuse Python domain code; mature desktop widgets, model/view and platform support | Rebuild UI; packaging footprint and platform adapters still need measurement | Strong fallback and credible alternative |
| Tauri 2 + Rust + Svelte/TypeScript | Closely demonstrated by Pomotroid; explicit backend; web UI styling; system WebViews | Rust + JS toolchains; WebView differences; Linux dependencies/Wayland work; accessibility must be verified | Recommended after platform prototype |
| Electron + TypeScript | Familiar web tooling; consistent bundled Chromium; broad desktop ecosystem | Bundled runtime and process overhead for a tiny utility; updates and native adapters still need work | Use if validated integrations or team expertise outweigh footprint goals |
| Flutter + Dart | Official Windows/macOS/Linux desktop support; consistent rendered UI; future mobile option | Desktop integrations rely on adapters/plugins; new toolchain and full rewrite | Viable, but mobile is not the stated goal |
| Vala + GTK/libadwaita as in FocusTimer | Excellent Linux integration pattern | Existing product does not establish Windows/macOS support | Reject as the primary product stack |

Qt officially supports the three desktop families, and Flutter has official desktop support. Those facts establish candidate viability, not feature parity or benchmark results. [Qt supported platforms](https://doc.qt.io/qt-6/supported-platforms.html), [Flutter desktop support](https://docs.flutter.dev/platform-integration/desktop).

Tauri uses Windows WebView2, macOS WKWebView, and Linux WebKitGTK. This creates a smaller bundled-runtime opportunity than shipping Chromium, but UI behavior and runtime dependencies differ by OS. Measure total process-tree memory rather than just the Rust process. Do not promise that it will use less RAM than the existing Tk application without comparing production builds. [Tauri WebViews](https://v2.tauri.app/reference/webview-versions/), [Tauri architecture](https://v2.tauri.app/concept/architecture/).

### Proposed architecture

```text
Svelte UI: timer / mini mode / tasks / reports / settings
    |
Typed commands and snapshots through Tauri IPC
    |
Rust application services
    |-- timer domain: countdown + stopwatch + cycle + precise active segments
    |-- database worker: SQLite transactions, migrations, indexed queries
    |-- task/session services: attribution, undo, export, recovery
    |-- optional sync worker: outbox, revisions, retries, conflict handling
    |-- platform adapters: sleep, lock, tray, shortcuts, notifications, audio
```

The core should be a small library independent of Tauri and the UI. Use explicit states such as idle/running/paused/suspended/completed and immutable session configuration. Commands from UI, tray, and shortcuts all go through the same core. A generation/session ID prevents a delayed completion event from affecting a new session. The UI presents snapshots and derives visual progress; it does not decide whether work completed.

Store tasks, projects, sessions, session segments, schema version, and sync outbox in SQLite. A session needs a UUID, task/project association, intended duration, actual active duration, UTC start/end, timezone information, and a completion reason. Segments allow pauses and midnight boundaries to be handled accurately. Persist meaningful transitions and bounded checkpoints rather than writing every animation frame. Do database work outside the rendering path.

For sync, persist local changes and their outbox entries in one transaction. Use server revisions/conditional updates or append-only operations, idempotent operation IDs, acknowledgements, retries with backoff, and conflict presentation. Retain deletion knowledge until stale devices cannot resurrect data. A whole-bin GET/PUT client cannot guarantee this by client-side merging alone. Do not select a new hosted service before its protocol, costs, privacy model, and migration needs are specified.

## 8. Cross-platform requirement as a release gate

Supporting all three OS families is mandatory. Optional desktop integrations can have platform-specific implementations, but the application must launch, remain controllable, and preserve all core timer/task/history/export behavior without them.

| Platform | Required validation targets | Distribution target |
| --- | --- | --- |
| Windows | Windows 11 x64; ARM64 validated natively before claiming it; DPI scaling; notifications; sleep/lock; tray; installer upgrade/uninstall | Signed per-user installer; optional portable build; planned WebView2 offline/bootstrap behavior |
| macOS | Apple Silicon and Intel where included in the published support policy; menu bar; permissions; Spaces/full-screen; wake; VoiceOver | Signed/notarized universal DMG or separately tested arm64/x64 builds |
| Linux | Explicit Ubuntu/Debian and Fedora baselines; GNOME and KDE; Wayland and X11; audio, notifications, portals, DPI | DEB + RPM + AppImage initially; Flatpak when portals/background behavior are validated |

CPU architecture and minimum OS versions must be stated explicitly. “All mac/windows/linux” means all three product families, not every historical OS version or arbitrary Linux distribution. Publish a tested matrix, maintain support for all three families, and keep compatibility claims tied to evidence. Add Linux ARM64 when packaged dependencies and real hardware validation are available; do not label a cross-compiled artifact as tested support.

### Linux risks that the prototype must resolve

- **Global shortcuts:** the `global-hotkey` backend used in this ecosystem documents Linux support as X11-only. Use a Linux GlobalShortcuts portal adapter where supported, with local keyboard controls and desktop-configured shortcuts as reachable alternatives. FocusTimer already demonstrates the provider pattern. [global-hotkey platform support](https://docs.rs/global-hotkey/latest/global_hotkey/), [XDG GlobalShortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html).
- **Tray availability:** runtime detection must determine whether a tray can be created and reached. Do not enable close-to-tray as the only reopening path when the desktop lacks a visible tray. Maintain launcher/single-instance activation and notification or main-window controls.
- **Always on top, positioning, transparency, and overlays:** validate each under target compositors. A framework API does not grant unrestricted Wayland window control. Use supported compositor/desktop mechanisms and expose actual capabilities; if pinning is a must-have on a particular desktop, it must pass there before the stack is approved.
- **Runtime dependencies:** test clean installations without development packages, build against intentional Linux baselines, and verify required WebKitGTK/audio/tray libraries. An AppImage label does not itself establish compatibility with every distro.

The same principle applies to macOS permissions and Windows runtime installation. Tests must include denied permissions, missing integrations, and offline use. Core behavior cannot depend on network access or granting optional permissions.

### Platform prototype acceptance

Before the rebuild proceeds, produce a minimal production-packaged app on each OS that proves countdown + stopwatch, hide/reopen, notifications, sound, keyboard controls, suspend/resume, persistent data, mini mode, and accessible navigation. Test tray/pinning/global shortcuts on both GNOME/KDE and Wayland/X11. Capture unsupported capability behavior. Compare with a small PySide6 prototype only if a must-have Tauri capability fails.

This gate is a genuine architecture decision: a failure must lead to an adapter, revised implementation, or alternative stack while keeping all three operating systems in scope.

## 9. Performance and quality acceptance criteria

These are proposed targets, not measured achievements:

| Area | Initial target and measurement |
| --- | --- |
| Timer | Less than one second accumulated error over a two-hour awake run; rapid toggles and five-second UI stalls produce no duplicate transitions; exact-once session finalization |
| Suspend/clock changes | Default excludes sleeping time; explicit policy for lock/idle; forward/backward clock adjustments do not alter active duration; OS wake events tested on each platform |
| Responsiveness | Common controls respond in under 100 ms; persistence/network work does not block UI; cached views render immediately |
| History | At 100,000 records, common date-range reports below 100 ms after warmup and transactional append below 20 ms on documented reference hardware |
| Startup | Warm usable window within one second and cold within two seconds on reference machines; separately measure installer/extraction and WebView initialization |
| Background cost | Paused/idle core blocks on events; no continuous animation when hidden; average CPU target below 1% of one logical core in documented idle tests |
| Memory | Record total process-tree memory for idle/running/reports; no rising trend after 100 open/close cycles; set an absolute budget after prototype measurements |
| Durability | Crash/restart, disk-full, malformed import, and failed migration preserve existing data; active work loss bounded by the checkpoint interval |
| Sync | Concurrent edit/delete, retry, offline rejoin, clock skew, and stale snapshot tests retain acknowledged changes and show unresolved conflicts |
| Accessibility | Keyboard-only completion of key flows; Narrator, VoiceOver, and Orca checks; enlarged text/high DPI; focus visibility; reduced-motion mode |
| Updates | Artifact signatures verified; Windows/macOS platform signing addressed separately; failed download or migration preserves the working install/data |

Use deterministic fake-clock tests for domain correctness, integration tests for migrations/sync, packaged smoke tests, and real OS testing for desktop APIs. Add UI tests for actual journeys and accessibility, not just snapshots of implementation details. macOS Tauri WebDriver support should be verified before choosing a single end-to-end harness; do not assume one UI test tool works everywhere.

For any framework comparison, use production builds, identical hardware/workloads, total process trees, several repeated runs, and median/p95 startup/control timings. Include running hidden, paused, reports with 100k records, large task lists, offline sync, and sleep/wake. No framework choice should be justified by an unmeasured “Rust is faster” claim.

## 10. Staged implementation and migration plan

| Stage | Scope | Exit condition |
| --- | --- | --- |
| 1. Stabilize 0.x | P0 data protection, timer correctness, settings validation, CI, baseline profiling | Reproduced defects covered by meaningful regression tests; no loss of existing features |
| 2. Validate stack | Three-OS packaged Tauri prototype and desktop adapters; optional Qt fallback evaluation | Mandatory behavior passes the published matrix |
| 3. Build foundation | Independent timer library, SQLite schema/migrations, basic main/mini UI, crash recovery | Pomodoro + stopwatch + current tasks/reports/settings work on all three OSs |
| 4. Product beta | Task attribution, reports/export, tray/notifications/shortcuts, themes/accessibility, signing | Feature parity and migration proven; performance targets measured |
| 5. Sync and polish | Revision-aware sync, presets, goals, special breaks, optional overlays, localization | Offline/concurrency tests pass; user-facing behavior stays coherent |
| 6. Replace stable app | Release candidate, installation/update testing, docs and support procedures | Windows/macOS/Linux release gates all pass; recovery path documented |

Do not delete the existing implementation before the replacement passes the gate. Avoid maintaining two permanent desktop runtimes; use a temporary stabilization branch and a separately versioned replacement beta.

Migration must discover the current `%APPDATA%/pomodoro-timer` and `~/.config/pomodoro-timer` data. Back up original files securely; validate settings/tasks/history; map legacy IDs to stable UUIDs; import in one SQLite transaction; record migration completion so retries cannot duplicate data. Preserve ambiguous legacy timestamps with their original values and an explicit import-time timezone interpretation. Do not invent precise timezone/segment data that the old format never recorded.

Preserve task sync identity through an explicit coordinated ID migration. Do not silently convert one device's IDs while another still uses the old JSONBin schema. Migrate credentials to OS storage without writing them to logs or reports. Validate imported counts/totals and provide a migration summary. Keep a documented rollback to preserved data; avoid letting old and new apps concurrently write one database or bin with incompatible schemas.

Release quality also requires clear ownership of supported architectures, OS versions, signing credentials, migration rollback, issue triage, screenshots, contribution guidance, license/attributions, and update channels. Tauri updater signatures are mandatory and separate from platform signing. [Tauri updater documentation](https://v2.tauri.app/plugin/updater/).

The recommended next implementation milestone is **stabilize the Python app and produce the three-OS platform prototype**. After that evidence exists, the full rebuild decision can be made without putting Windows, macOS, or Linux support at risk.

## Source navigation

The code findings above refer to these reviewed local files and directories:

- Our implementation: [timer, UI, and sync orchestration](../../src/pomodoro.py), [storage](../../src/storage.py), [sync protocol](../../src/sync.py), [tests](../../tests/test_pomodoro.py), [release workflow](../../.github/workflows/release.yml), [PyInstaller spec](../../pomodoro.spec).
- FocusTimer: [timer](../../motivating-projects/FocusTimer/src/core/timer.vala), [database protection](../../motivating-projects/FocusTimer/src/core/database.vala), [portal shortcuts](../../motivating-projects/FocusTimer/src/plugins/portal/global-shortcuts-provider.vala), [test targets](../../motivating-projects/FocusTimer/tests/meson.build), [NEWS](../../motivating-projects/FocusTimer/NEWS).
- Pomatez: [renderer timer](../../motivating-projects/pomatez/app/renderer/src/contexts/CounterContext.tsx), [state persistence](../../motivating-projects/pomatez/app/renderer/src/store/store.ts), [task operations](../../motivating-projects/pomatez/app/renderer/src/store/tasks/index.ts), [tray rendering](../../motivating-projects/pomatez/app/renderer/src/hooks/useTrayIconUpdates.tsx), [Tauri configuration](../../motivating-projects/pomatez/app/tauri/tauri.conf.json).
- Pomotroid: [timer engine](../../motivating-projects/pomotroid/src-tauri/src/timer/engine.rs), [controller](../../motivating-projects/pomotroid/src-tauri/src/timer/mod.rs), [database](../../motivating-projects/pomotroid/src-tauri/src/db/mod.rs), [queries](../../motivating-projects/pomotroid/src-tauri/src/db/queries.rs), [tray](../../motivating-projects/pomotroid/src-tauri/src/tray/mod.rs), [build workflow](../../motivating-projects/pomotroid/.github/workflows/build.yml).
