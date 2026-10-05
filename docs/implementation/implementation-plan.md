# Pomodoro Timer implementation plan

Prepared October 4, 2026. Based on the [project review](../research/project-review-2026-10-04.md), the existing 0.3.1 implementation, 43 passing baseline tests, and [seven reproduced defects](../research/probe-results.json).

**Delivery objective:** a reliable, polished desktop focus companion with Pomodoro, stopwatch, tasks, reports, and optional synchronization, supported on **Windows, macOS, and Linux**. Every stable release must satisfy all three platform gates.

**Proposed stack:** Tauri 2 + Rust + Svelte/TypeScript + SQLite. This is the planning default, subject to a packaged platform prototype. If a mandatory capability fails, implement an adapter or evaluate PySide6/Qt before proceeding. Do not drop an OS to make the rebuild easier.

M0 is closed following the user's October 4 confirmation that all three CI platforms pass. M1 has started in the separate [`desktop/`](../../desktop/README.md) workspace: Rust timer/SQLite service, Svelte main/compact views, settings, recent sessions, and a three-platform prototype workflow. Tauri's native platform gates remain open. See the [implementation log](implementation-log.md) and [platform validation checklist](platform-validation.md) for evidence and limits.

## 1. Approximate final product

The expanded [revision-2 gallery](mockups/v2/README.md) contains **18 design boards** covering the app windows, supporting dialogs, menus, and exceptional states. The [UI design specification](ui-design-spec.md) defines their behavior and maps every planned surface to a board. These generated concepts are not running software; sample data and platform chrome are illustrative. The written specification takes precedence over incidental image details.

### Main timer

![Ready, running, and paused timer concepts](mockups/v2/01-timer-states.png)

The main timer answers what you are focusing on, how much time remains, and what happens next. Pomodoro and Stopwatch are modes in the same destination. Main, compact, tray, and keyboard controls all use one authoritative session.

### Minimal compact mode

![Compact timer with one visible control](mockups/v2/03-compact-mode.png)

Compact mode targets **200 × 44 logical pixels** for countdown at default text scale, growing to about **240 × 44** for hours-based stopwatch time. It shows only time, a small phase indicator, and **one play/pause button**. Task text, title bar, pin, expand, stop, settings, and navigation buttons do not occupy the strip.

Clicking/double-clicking the time, native accessibility Invoke, or its keyboard equivalent opens the main window. Right-click or Shift+F10 opens the accessible menu for pinning, sound, finishing, and exit. A task tooltip provides context. Larger text grows the strip rather than clipping digits. The previous 340 × 110 mockup is superseded.

### Tasks, reports, settings, and supporting windows

![Tasks workspace, editor, project dialog, and archive](mockups/v2/04-tasks-and-projects.png)

![Reports, custom range, session details, and export](mockups/v2/05-reports-and-export.png)

The [full gallery](mockups/v2/README.md) also includes short/long breaks, stopwatch, all eight settings categories, shortcut capture, onboarding, migration, backup/import/restore, corrupted-data recovery, sync connection/conflicts, confirmations, empty/loading/error states, tray, notifications, updates, release notes, licenses, diagnostic export, and system-owned file/permission dialog concepts.

The Windows/macOS/Linux and accessibility board illustrates shared functionality with native chrome, keyboard focus, and larger text. Later break overlays, reminders/goals, and custom-theme concepts are visibly separated from first-stable-release scope. No OS is removed from the delivery requirement.

Use **Saved on this device**, **Syncing**, **Offline**, and **Needs attention** status language. Never show Saved when persistence failed. M1 must turn these concepts into a tested component/interaction specification; images alone do not prove accessibility or platform capabilities.

## 2. Release scope and operating assumptions

### Required for the replacement stable release

- Existing Pomodoro, stopwatch, work/break settings, font scaling, editable tasks, daily totals with Pomodoro/stopwatch breakdown, reset-today capability, and remembered geometry remain available.
- Compact/pinned timer remains a first-class experience; transparency is supported where the OS permits it and is clearly capability-aware.
- Accurate timekeeping, one timer authority, safe persistence, backup/recovery, and legacy-data migration.
- Projects and task attribution; completed/interrupted history; weekly/monthly reports; CSV/JSON export.
- Native notifications, consistent audio, keyboard operation, tray/menu-bar control with a safe reopen path.
- Light/dark appearance, readable focus states, reduced motion, and assistive-technology checks.
- Optional task sync that passes offline/concurrency tests. A local-only beta is permissible; silent removal of existing optional sync from the stable replacement is not.
- Tested installers, signed release/update artifacts, documented supported environments, and clean upgrade/uninstall behavior.

### Follow-up releases

Scheduled special breaks, advanced goals/reminders, multi-monitor break overlays, opt-in strict mode, custom theme import, broader localization, history sync, and a scoped local integration API follow the reliable foundation. Mobile, arbitrary scripts, a plugin marketplace, and a mandatory cloud account are outside this plan.

### Effort assumptions

Plan for one experienced full-time developer, access to Windows/Linux/macOS test environments, and time for real desktop QA. Effort below is an initial estimate in developer-days, not a promised calendar schedule. Add learning time if Rust/Tauri is new; waiting for hardware, signing credentials, hosting decisions, or external testing can extend elapsed time.

| Milestone | Effort estimate | Dependency | Deliverable |
| --- | ---: | --- | --- |
| M0: stabilize current app | 5–8 days | None | Safer 0.x baseline and PR CI |
| M1: validate platform and design | 5–8 days | M0 baseline | Three-OS prototype, architecture decision, UI specification |
| M2: timer/storage foundation | 8–12 days | M1 approval by evidence | Tested Rust core, SQLite, migration and recovery |
| M3: desktop timer experience | 7–10 days | M2 | Main/compact timer with native adapters |
| M4: tasks and reporting | 7–10 days | M2; M3 shell | Task-linked workflow and export |
| M5: quality and release infrastructure | 6–10 days | M3/M4; starts during M1 | Accessibility, performance evidence, installers/signing |
| M6: safe optional sync | 8–14 days | M2/M4; provider decision | Conflict-aware task sync and coordinated migration |
| M7: release candidate and cutover | 4–7 days | M0–M6 gates | Validated stable replacement and rollback guide |

Total initial range: **50–79 developer-days**, about **10–16 full-time working weeks**, before contingency or external delays. Estimates must be revised after M1. M5 work begins early; it is shown separately to make the release-quality effort visible.

## 3. Milestones and exit gates

### M0 — Stabilize the Python application

Keep `src/`, the current tests, and current packaging working while the new app is developed separately.

- [x] M0.1 Turn the seven research reproductions into isolated regression tests asserting desired behavior. Keep the research probes as historical evidence; they intentionally assert the original failures.
- [x] M0.2 Track one timer callback ID; cancel it on pause/stop/mode change/close; reject stale generations. Introduce a UI-independent timing model using monotonic elapsed duration for countdown and stopwatch.
- [x] M0.3 Snapshot duration/cycle configuration when a session starts. Validate positive durations and a positive long-break interval, including values loaded from disk; show useful validation feedback.
- [x] M0.4 Write JSON through a same-directory temporary file and atomic replacement, with flush/fsync where supported, explicit errors, and last-known-good backup. Preserve malformed originals before recovery.
- [x] M0.5 Merge sync results against current local revisions, preserve edits that occurred during requests, and normalize timestamps. Validate every task object, use stable new IDs, and surface worker errors through a main-thread result queue.
- [x] M0.6 Stop time-only tombstone purging. Preserve deletion knowledge. Document that whole-bin GET/PUT still cannot ensure cross-device consistency; do not claim the bridge fix is the final sync protocol.
- [x] M0.7 Prevent conflicting application instances or writes. Preserve existing data paths and configuration behavior.
- [x] M0.8 Add PR CI for locked dependencies and pytest on all three OSs; retain Linux installed-app smoke testing and add feasible Windows/macOS launch checks.

**Exit:** existing behavior remains covered; rapid pause/resume, in-flight edits, malformed history, invalid settings, timezone-aware timestamps, and offline deletion cases pass regression tests. Failed writes remain visible and leave recoverable data. Outstanding baseline startup, history timings, and process-tree resource measurements carry forward to the prototype comparison and M5.3; they are not claimed as measured.

**Current gate status: closed.** The user confirms Windows/macOS/Linux CI passes following the Linux geometry fix and explicitly requests M0 closure. Local evidence includes 106 legacy tests and native Tk smoke on Windows/WSL, and the earlier Windows package build/launch. The new Tauri workflow has separate pending results; M0 closure does not establish replacement-platform readiness.

### M1 — Prove the stack and establish the product contract

- [x] M1.1 Create the new desktop workspace without moving/deleting the working Python app. Pin a supported stable toolchain and include both Rust and frontend lockfiles in the change set.
- [ ] M1.2 Package a minimal timer on Windows, macOS, and Linux. Prove native notifications/audio, minimize/reopen, single-instance activation, compact geometry, sleep/wake events, keyboard controls, and a persisted record.
- [ ] M1.3 Test GNOME/KDE on Wayland/X11: tray availability, portal shortcuts, pinning/position/opacity, and notification behavior. Add adapters or explicit capability handling. An unavailable tray must not strand a hidden app.
- [ ] M1.4 Prove the UI automation harness on all three OSs and disable any embedded driver/test endpoints in production builds.
- [ ] M1.5 Check keyboard navigation, screen-reader labels, larger text, and contrast on the prototype before building the complete UI.
- [ ] M1.6 Finalize the [revision-2 UI specification](ui-design-spec.md) and its complete surface inventory: tokens, light/dark components, modal focus, error/recovery paths, adaptive layouts, and keyboard/assistive equivalents. Prototype and validate the 200 × 44 compact strip with one visible control before locking geometry.
- [ ] M1.7 Write architecture decisions for stack, timer/sleep semantics, storage, supported platform baselines, sync protocol requirements, and release distribution.
- [ ] M1.8 Decide a revision-aware sync provider or protocol implementation. Record its conditional-write/operation guarantees, migration support, privacy behavior, credentials, hosting responsibility, and recurring costs. Leave vendor selection open until these facts are established.

**Current progress, October 5:** M1.1 is implemented and Windows launch is user-confirmed. The Windows integration batch adds native audio, notification opt-in, editable global shortcuts/conflict handling, persisted placement/pinning, 100–200% compact text, and Windows suspend/lock interruption. Automated evidence: 20 Rust tests, six frontend unit tests, six browser UI tests, native rendered-control/IPC smoke, and normal Windows UI Automation. The unsigned NSIS package passes current-user install/UI/uninstall checks. See the [platform record](platform-validation.md) for evidence and remaining human checks. At the user's request, macOS/Linux-specific work waits until they are on those platforms; M1.2–M1.8 and the mandatory three-platform gate remain open. [ADR 0002](architecture/0002-windows-integrations.md) records these integration boundaries.

**Exit:** the mandatory timer/task/history interaction path is viable on all three OSs, desktop capability results are recorded, and the selected stack has no unresolved mandatory-platform blocker. If it fails, evaluate Qt before growing the Tauri implementation. Revised estimates and support policy are recorded.

### M2 — Build the timer and storage foundation

- [ ] M2.1 Implement the timer domain as a Rust library independent of Tauri, OS APIs, and the renderer. Inject clocks for deterministic tests.
- [ ] M2.2 Define typed commands/events/snapshots and one serialized command processor. UI, tray, and shortcuts use the same processor.
- [ ] M2.3 Model countdown, stopwatch, cycle progress, precise active segments, and generation/session IDs. Snapshot settings at session start; settings changes apply to future sessions by default.
- [ ] M2.4 Implement OS sleep/lock policy through adapters. Do not assume that a monotonic clock includes/excludes suspension identically on every OS. Record pre-sleep state and reconcile on wake.
- [ ] M2.5 Add SQLite migrations, integrity checks, bounded busy behavior, backups, and a database worker. Use transactions and avoid doing database work on the rendering path.
- [ ] M2.6 Persist transition state and active-duration checkpoints, initially every 15 seconds while running. Make completion idempotent by session/transition identity.
- [ ] M2.7 Implement legacy import with dry-run validation, secure backup, ID mapping, original timestamp preservation, transactional import, and an idempotent migration marker.
- [ ] M2.8 Add restart recovery: restore interrupted work as paused, show recovered duration and available actions, and exclude the unobserved process-down gap. Never replay missed work/break cycles automatically.

**Exit:** deterministic transition tests pass; time adjustments and delayed UI updates do not corrupt duration; kill/restart and failed migrations preserve data; repeated import/completion cannot create duplicates. Imported counts/totals reconcile with legacy data within documented timestamp ambiguity.

### M3 — Deliver the desktop timer experience

- [ ] M3.1 Build the main timer, explicit Pomodoro/Stopwatch switch, work/break controls, selected-task card, daily summary, and structured settings.
- [ ] M3.2 Build the minimal compact strip specified in [ui-design-spec.md](ui-design-spec.md): time, phase indicator, one play/pause control; adaptive text scaling; geometry restoration and safe placement; pin/finish/exit in its accessible context menu; double-click/keyboard return to main. All visible views subscribe to backend state; the backend remains the source of session truth.
- [ ] M3.3 Implement tray/menu-bar actions, safe close/minimize preferences, and launch activation. Closing-to-tray is enabled only when a reachable reopen mechanism exists.
- [ ] M3.4 Implement notification permission handling, completion actions, consistent audio, volume/mute, and unavailable-audio feedback. Avoid shelling out to an undeclared Linux player.
- [ ] M3.5 Implement local and global shortcut adapters, registration conflict feedback, and portal/desktop fallback behavior on Linux.
- [ ] M3.6 Implement settings for automatic work/break transitions, appearance, reduced motion, and optional launch at login. Keep launch/sync/permission features opt-in where appropriate.

**Exit:** start → pause → resume → complete → break works consistently from UI/compact/tray/shortcuts. Hidden sessions continue correctly. Missing tray/notifications/permissions do not make the app unusable. All three OSs pass an installed-build journey.

### M4 — Add tasks, attribution, reports, and export

- [ ] M4.1 Preserve existing task CRUD, add projects, notes, estimates, archive, search/filter, and undo for recent changes. Use stable keyed rows; preserve unsaved edits on focus loss.
- [ ] M4.2 Start focus from a task and snapshot task/project attribution for that session. Changing the focused task during active work requires ending the current attribution segment or finishing/starting a session explicitly.
- [ ] M4.3 Track actual active time independently of planned duration. Preserve completed, interrupted, skipped, and stopwatch outcomes separately.
- [ ] M4.4 Build today/week/month/date-range summaries, project and Pomodoro/stopwatch breakdowns, and clear total-focus/round-count definitions. Query timestamp ranges through useful indices. Preserve reset-today behind explicit confirmation, a protective backup, an atomic date-scoped transaction, and a no-active-session guard; reconcile affected task totals and retain all other days.
- [ ] M4.5 Handle midnight and DST with explicit segment/timezone rules. Make current-timezone versus session-local date interpretation explicit.
- [ ] M4.6 Add CSV for human analysis and versioned JSON for lossless export/import, including validation, preview, duplicate handling, and failure feedback.

**Exit:** task/project totals reconcile with session active durations; archiving/deleting tasks does not destroy history; completed rounds are never inferred from an interrupted record; reports/exports agree across filters and timezones. Reports remain responsive at 100,000 history records.

### M5 — Accessibility, performance, and distribution

Start packaging and accessibility work during M1 instead of deferring it to the end.

- [ ] M5.1 Finish keyboard journeys, visible focus, semantic labels, chart text summaries, text scaling, reduced motion, and high-contrast verification.
- [ ] M5.2 Test Narrator, VoiceOver, and Orca on actual target environments. Fix functional failures before cosmetic polish.
- [ ] M5.3 Profile production builds: startup, click-to-state latency, hidden/paused CPU, total process-tree memory, large task lists, reports, and sleep/wake.
- [ ] M5.4 Stop visual animation when hidden, coalesce delayed timer events, cache tray icon states, reuse views, and optimize SQL from observed query plans.
- [ ] M5.5 Build clean-machine installation/upgrade/uninstall jobs, artifact checksums, dependency declarations, and version consistency checks. Maintain separate beta/stable identities and updater channels.
- [ ] M5.6 Configure platform signing and notarization, signed updates, secure key handling, and disabled-by-default or user-configurable update checking. Match each package type to its supported update mechanism.
- [ ] M5.7 Add redacted structured logs, error recovery screens, optional diagnostic export, privacy documentation, license/attributions, contribution instructions, and updated screenshots.

**Exit:** measured budgets pass or are explicitly re-evaluated with evidence before release; no accessibility blocker remains; installers work without development dependencies; unsigned test builds cannot leak into the stable channel.

### M6 — Implement safe optional task synchronization

- [ ] M6.1 Local changes and outbox operations commit together in SQLite. Use operation UUIDs, per-record/server revisions, idempotent acknowledgements, and serialized local application.
- [ ] M6.2 Implement incremental transfers, conditional writes or ordered operations, retries/backoff, offline states, cancellation, and credential storage through OS facilities.
- [ ] M6.3 Merge returned data against current revisions without discarding in-flight edits. Preserve losing concurrent edits for conflict resolution rather than silently overwriting them.
- [ ] M6.4 Retain deletion knowledge until acknowledged or force stale devices to rebase against a snapshot epoch. Never garbage-collect solely because seven days elapsed.
- [ ] M6.5 Coordinate migration from JSONBin. Preserve legacy IDs until all participating devices have upgraded/rebased; make old/new incompatible-client behavior explicit. Back up before any remote schema conversion.
- [ ] M6.6 Build conflict resolution and sync status flows, disconnect/revoke behavior, and tests using two simulated clients and a controllable server.

**Exit:** concurrent edit/edit, edit/delete, repeated retries, clock skew, schema mismatch, disconnect/rejoin, stale snapshot, and long-offline rejoin preserve acknowledged changes and communicate conflicts. The app remains fully usable offline. No active timer is synchronized between devices in this milestone.

### M7 — Release candidate and stable cutover

- [ ] M7.1 Exercise fresh install, legacy import, beta upgrade, current-stable upgrade, failed migration, failed update, and rollback on every supported platform family.
- [ ] M7.2 Run the complete acceptance matrix on production-packaged artifacts; verify versions, signatures, hashes, metadata, and installer contents.
- [ ] M7.3 Run sustained timer and open/close soak tests plus a realistic beta trial. Fix data/timing/platform blockers before release.
- [ ] M7.4 Publish tested support boundaries, known optional capability limitations, migration summary, backups/export instructions, and rollback guidance.
- [ ] M7.5 Switch the default release to the replacement only after all gates pass. Archive the Python implementation for reproducibility after the rollback window, rather than keeping two indefinitely active products.

**Exit:** Windows, macOS, and Linux are green together; migration and optional task sync are safe; production installers and update paths are verified. Releasing only the easiest platforms is not an acceptable shortcut.

## 4. Behavior decisions to lock before implementation

| Question | Proposed default |
| --- | --- |
| Do work/break phases auto-start? | Preserve manual transitions by default; allow independent auto-start-work/auto-start-break preferences |
| What counts as a completed Pomodoro? | Reaching the configured work deadline; finishing early records active time but does not increment completed-round count |
| How does an interruption affect a cycle? | Preserve completed work count; restart work as a new session; entering/ending a long break has an explicit cycle reset rule |
| What happens while sleeping? | Exclude sleeping time; restore prior run/pause intent according to an explicit setting, without counting the sleep interval |
| What happens on screen lock? | Separate opt-in auto-pause setting; locking is not silently treated as sleeping |
| What happens after a crash/restart? | Recover checkpointed active duration into a paused session; show resume/finish actions; exclude downtime |
| What if settings change while running? | Apply to the next session; offer an explicit duration-adjustment action if added later |
| What does Finish early do? | Save actual active duration as interrupted, stop the session, and leave the next phase awaiting user action |
| What happens when a task is archived? | Preserve history/attribution; hide from active lists; do not cascade-delete sessions |
| Which device owns an active timer? | Each device independently; sync tasks only initially; no implicit timer handoff |
| What if writing data fails? | Keep the in-memory state visible, mark it unsaved, offer retry/export, and do not falsely acknowledge durability |

Specify exact cycle rules, notification wording, and shortcut defaults in M1 tests/design notes. The images cannot decide these semantics.

## 5. Architecture and repository layout

```text
src/ and tests/                   Existing Python app during stabilization
apps/desktop/
  src/                           Svelte views, components, state presentation
  src-tauri/                     IPC, OS adapters, app composition, packaging
crates/
  focus-core/                    Clock-injected timer/cycle/session domain
  focus-storage/                 SQLite, migrations, backup, legacy import
  focus-sync/                    Provider-neutral outbox/revision protocol
tests/
  fixtures/                      Legacy/corrupt/timezone/schema datasets
  desktop/                       Packaged cross-platform user journeys
docs/
  adrs/                          Decisions and platform evidence
  implementation/                This plan, backlog, product mockups
```

Use a small Rust workspace. Do not build a generic plugin framework. A background command processor owns timer state; an OS adapter sends sleep/lock events; a database worker serializes transactions. IPC handlers validate input and delegate rather than implementing domain behavior.

Snapshots carry a session ID, generation, revision, kind/phase, state, precise active duration, planned duration, cycle progress, and task attribution. The frontend ignores stale revisions and requests a fresh snapshot when it reconnects. It may animate between snapshots but cannot finalize a session.

### Storage outline

| Entity | Essential fields / rules |
| --- | --- |
| Projects/tasks | UUID, text/title, project relation, status, notes, estimate, revision, created/updated UTC, deletion/archive metadata |
| Sessions | UUID, kind, phase, planned duration, actual active duration, completion reason, task/project snapshot, start/end UTC |
| Active segments | Session ID, start/end UTC, active milliseconds, timezone/offset interpretation; unique segment identity |
| Active checkpoint | Session/generation, state, accumulated active duration, settings snapshot, checkpoint UTC, schema version |
| Settings | Typed, bounded values; versioned schema; credentials excluded |
| Migration journal | Source fingerprint, import mapping, imported counts, status; repeated import is idempotent |
| Sync outbox/metadata | Operation ID, entity/revision, payload, retry state, server revision/ack; deletion acknowledgement or epoch |

Protect credentials and backups containing legacy keys. Use SQLite's backup mechanism for a live database; do not copy only the main DB file while WAL writes are active. Validate recovery and rollback against the actual schema version.

## 6. Migration and rollback procedure

1. Discover legacy Windows `%APPDATA%/pomodoro-timer` and macOS/Linux `~/.config/pomodoro-timer` paths, plus new platform-native application directories.
2. Confirm the legacy process is closed; read source files without rewriting them; classify valid, missing, and malformed records.
3. Create a protected backup and dry-run import summary. Preserve raw timestamp values and record any chosen timezone interpretation.
4. Map task IDs deterministically for repeated import; preserve a legacy-ID alias needed by sync. Import settings/tasks/history in one transaction with a schema/migration marker.
5. Compare counts and active-duration totals, and retain rejected records with reasons for recovery. Abort safely on invalid mandatory data rather than silently skipping it.
6. Store migrated credentials using OS facilities and redact all diagnostics. Do not change a remote bin until the coordinated sync migration step is ready.
7. Show a summary and retain the protected legacy snapshot through the rollback window. Back up before subsequent schema upgrades.
8. On failure, keep the working executable/data, restore from a compatible backup, and explain recovery steps. A binary downgrade cannot safely open every newer schema; rollback must use the matching backup or a supported downgrade migration.

Stable and beta apps use separate data/identity/update channels until explicit import. Do not let both apps simultaneously write the same sync namespace with different schemas.

## 7. Platform acceptance matrix

M1 freezes the exact minimum OS/WebView versions using current toolchain requirements and clean-machine tests. Older versions are supported only after verification. Proposed initial architecture scope: Windows x64, macOS Intel + Apple Silicon, Linux x64; Windows/Linux ARM64 is a separately validated expansion and must not be advertised solely from cross-compilation.

| Platform | Required environments | Packaging / checks |
| --- | --- | --- |
| Windows | Windows 11 x64; scaling 100/150/200%; sleep/lock; denied notifications; unavailable WebView runtime | Per-user signed installer; install/update/uninstall; offline/runtime bootstrap strategy |
| macOS | Intel and Apple Silicon; Spaces/full-screen; menu bar; permissions; VoiceOver; sleep/wake | Universal or separately tested binaries; signed/notarized DMG; Gatekeeper and update verification |
| Linux | Ubuntu/Debian baseline and Fedora; GNOME/KDE; Wayland/X11; missing tray; portals/audio; Orca | DEB/RPM/AppImage with dependency/ABI checks; clean-system launch; add Flatpak after portal validation |

Each environment must pass timer + stopwatch + task CRUD + reports/export + restore/recovery. Optional integrations require available/denied/unavailable behavior. Pinning and compact visibility are mandatory design requirements on declared supported desktop environments; record implementation evidence or solve the adapter before claiming that environment is supported.

## 8. Test strategy and measurable budgets

### Test layers

- Domain tests: injected clocks; every state transition; invalid commands; stale-generation rejection; randomized command sequences; time adjustment; exact-once completion.
- Persistence tests: fresh/old schema, repeated import, corrupted input, disk full, locked DB, crash checkpoint, backup restore, and failing migration.
- Sync tests: two clients, delayed requests, duplicate operations, offline rejoin, conflicts, deletions, skewed clocks, and schema/epoch changes.
- Frontend tests: mode/control states, keyboard focus, task drafts, validation/errors, chart summaries, and stale snapshot handling.
- Packaged end-to-end tests: installed artifact journeys with real IPC on each OS; desktop-native checks additionally performed with OS tools/manual QA.

Current Tauri documentation recommends WebdriverIO with an embedded WebDriver option across Windows/Linux/macOS; direct `tauri-driver` alone has different coverage. Validate the chosen setup in M1 and ensure test instrumentation is absent from production. [Tauri WebDriver documentation](https://v2.tauri.app/develop/tests/webdriver/).

### Initial performance budgets

| Measurement | Proposed acceptance target |
| --- | --- |
| Awake timer accuracy | Under one second accumulated error over two hours; stalls and toggles produce no duplicate completion |
| Control latency | p95 under 100 ms on recorded reference machines |
| Cold/warm startup | Usable window under 2 s cold / 1 s warm; separate runtime setup from app launch |
| History append | Median under 20 ms at 100,000 records; no UI blocking |
| Common reports | Warm query under 100 ms at 100,000 records; larger ranges measured separately |
| Hidden/paused CPU | Idle command processor blocks; average background target below 1% of one logical core |
| Memory | Record total process tree; no sustained growth after 100 repeated window journeys; set absolute budget after M1 measurement |
| Recovery | Active-time loss bounded by 15-second checkpoint interval plus the measured write latency; completed history not duplicated |

Record hardware, OS, production build, dataset, repetitions, median/p95, and complete process-tree resource use. These are targets, not already achieved results. A slower baseline or strict OS constraint should prompt investigation and an explicit budget decision.

## 9. Delivery workflow and dependencies

Use small milestone/feature PRs with concrete acceptance evidence. CI runs locked installs, formatting/type checks, Rust lint/tests, Python tests while maintained, migration/sync integration tests, and artifact builds. Run packaged smoke tests on Windows/macOS/Linux for release candidates. Version the app, frontend, Rust crate, installer, and updater consistently.

Use a beta channel before stable replacement. Tauri updater signatures and OS platform signatures solve different requirements; preserve both. DEB/RPM and future Flatpak releases should respect their package managers, with package-manager update guidance where in-app update is inappropriate. [Tauri updater documentation](https://v2.tauri.app/plugin/updater/).

External prerequisites to resolve during M1: macOS Intel/Apple Silicon testing access, Linux desktop test access, signing/notarization credentials, artifact hosting/channel ownership, and the sync provider/protocol decision. No paid provider is selected by this plan.

| Risk | Response / decision point |
| --- | --- |
| Required Linux integration fails | Solve portal/native adapter during M1, or compare Qt before committing to Tauri |
| Rewrite loses existing behavior | Keep a feature-parity checklist and Python app operational until replacement gates pass |
| Scope expands prematurely | Gate later overlays/reminders/integrations behind the stable core milestones |
| Sync migration conflicts with old clients | Coordinate versions/epoch; refuse incompatible writes; preserve aliases and backups |
| Signing/hardware access arrives late | Identify during M1; it blocks stable release, not core development |
| Old timestamps are ambiguous | Preserve raw values; document import timezone interpretation; avoid invented precision |

## 10. First implementation batch

M0 is closed. The current reviewable batch is **B05**, the separate Tauri prototype and packaging workflow. Next, validate its normal packages on Windows, macOS and Linux and complete **B06** capability/automation evidence before growing the replacement beyond M1.

Track the individual tasks in [backlog.md](backlog.md). The design images and [exact generation prompts](mockup-prompts.json) are included for review; final UI decisions should be made from the behavior/accessibility specifications and prototype evidence.
