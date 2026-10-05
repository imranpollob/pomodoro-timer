# Implementation backlog

Execution companion to [implementation-plan.md](implementation-plan.md). Its milestone checkboxes are the source of completion status. B01–B04/M0 are closed following the user's confirmation that three-OS CI passes. **B05 is in progress:** M1.1 scaffolding is implemented in [`desktop/`](../../desktop/README.md); M1.2 package/capability acceptance remains open. See the [implementation log](implementation-log.md) and [native checklist](platform-validation.md) for evidence and limits. This file groups tasks into reviewable change sets.

October 5: Windows B05/B06 integration and automated installed-build checks are implemented. Physical Windows power/assistive/monitor/delivery checks remain, and macOS/Linux-specific work is deferred until the user is on those platforms. This does not close the three-platform M1 gate or later feature-parity batches.

## First batch: stabilize timer and data

UI planning now has a [complete revision-2 gallery](mockups/v2/README.md) and [window/state inventory](ui-design-spec.md). B07 must resolve that inventory before B11 grows the app UI. A static board does not mark an implementation task complete.

### B01 — Regression cases and one authoritative timer scheduler

Plan tasks: M0.1–M0.2. Depends on: none.

**Problem:** rapid pause/resume leaves an old callback alive and schedules a new one; displayed and recorded duration depend on different clocks.

**Work:** add a small UI-independent timing model; inject a clock; derive active duration from monotonic elapsed segments; keep one scheduled UI refresh handle; invalidate older callback generations on transitions. Route countdown and stopwatch through the same timing contract. Preserve the existing UI behavior while separating domain state from widget changes.

**Likely files:** `src/pomodoro.py`, a new `src/timer.py`, `tests/test_pomodoro.py`, and focused timer tests. Research probes remain unchanged as historical reproductions.

**Acceptance:**

- Pause/resume repeatedly before the prior callback fires; the stale callback cannot advance the new timer.
- A delayed refresh of five seconds computes elapsed duration correctly, without decrementing only one second.
- Stopwatch display and persisted duration agree, including multiple pauses.
- Stop/mode switch/close reject all earlier callbacks and do not finalize a session twice.
- Existing work/short-break/long-break cycle behavior remains covered; UI tests assert user behavior rather than callback count.

**Verification:** deterministic fake-clock tests plus pytest across the three CI environments. No two-hour real sleep is required for unit tests; real-time soak testing belongs to the packaged acceptance stage.

### B02 — Validated settings and per-session configuration

Plan task: M0.3. Depends on: B01's session/timing contract.

**Problem:** zero intervals crash completion, and changing work duration while running changes the calculation of already elapsed work.

**Work:** define typed/bounded settings validation; validate disk input and UI input; snapshot work/break/cycle configuration when a session starts; display a useful error for invalid settings. Apply changed durations to the next session by default.

**Likely files:** `src/storage.py`, `src/pomodoro.py`, optional `src/settings.py`, and regression tests.

**Acceptance:** zero/negative/non-numeric intervals and durations are rejected safely; malformed saved settings do not crash launch; one minute of a 25-minute session remains one recorded minute after a setting changes to 30 minutes; invalid saves do not partially mutate unrelated settings.

**Verification:** boundary cases, load/save tests, mid-session settings regression, and a manual settings-window check.

### B03 — Atomic JSON persistence and recoverable errors

Plan task: M0.4. Depends on: settings validation contract; can be implemented separately from timer work.

**Problem:** direct truncating writes can destroy prior data; malformed history is treated as empty and overwritten by the next session.

**Work:** centralize JSON read/write results; use a temporary file in the destination directory and atomic replacement; flush before replacement; maintain recoverable backups; preserve malformed files; distinguish missing/invalid/unreadable data; propagate save errors to UI state. Keep file encoding explicit.

**Likely files:** `src/storage.py`, `src/pomodoro.py`, and focused storage tests.

**Acceptance:** simulated write failure leaves the previous valid file intact; truncated history is preserved and never silently replaced; Unicode task text round-trips; the UI does not report saved state after failure; backup recovery is validated for settings/tasks/history separately.

**Verification:** fault-injected replace/write errors, malformed-file fixtures, backup round-trip, and full pytest. Avoid tests that merely repeat `json.dump` behavior.

### B04 — Sync bridge and three-OS CI

Plan tasks: M0.5–M0.8. Depends on: B02/B03.

**Work:** retain local edits made during requests, normalize/validate timestamps and task schema, preserve tombstones, marshal worker results safely, guard process shutdown, and prevent conflicting local instances/writes. Add a PR validation workflow and feasible installed-build smoke checks.

**Acceptance:** the in-flight edit survives; aware timestamps and malformed remote records produce usable outcomes; stale offline clients cannot immediately revive deleted records; closing during a request is safe; CI validates Windows/macOS/Linux. Whole-bin concurrency remains a documented limitation until B18.

**Verification:** delayed fake HTTP responses and deterministic two-snapshot scenarios, request/error tests, shutdown lifecycle checks, and CI artifacts. Do not transmit real JSONBin credentials or user tasks during tests.

## Remaining delivery batches

| Batch | Plan tasks | Depends on | Reviewable outcome |
| --- | --- | --- | --- |
| B05 | M1.1–M1.2 | B04 | Separate Tauri workspace and minimal production packages for all three OSs |
| B06 | M1.3–M1.5 | B05 | Desktop capability evidence, OS adapters, automation harness, early accessibility results |
| B07 | M1.6–M1.8 | B06 | Product specification, architecture decisions, support policy, sync protocol/provider decision |
| B08 | M2.1–M2.4 | B07 | Typed, clock-injected timer core and sleep/lock contract |
| B09 | M2.5–M2.6 | B08 | SQLite schema/worker, transactional completion, checkpoints, backups |
| B10 | M2.7–M2.8 | B09 | Idempotent legacy migration and paused recovery after restart |
| B11 | M3.1–M3.2 | B08–B10 | Main timer, stopwatch, settings, 200 × 44 compact strip with one play/pause control, accessible context menu, restored geometry |
| B12 | M3.3–M3.6 | B06/B11 | Tray, notifications, audio, shortcuts, transition preferences, desktop behavior |
| B13 | M4.1–M4.2 | B09/B11 | Projects/tasks/undo and durable task-to-session attribution |
| B14 | M4.3–M4.6 | B13 | Accurate reports, timezone rules, export/import, indexed queries |
| B15 | M5.1–M5.4 | B12/B14 | Accessibility fixes, measured performance, targeted optimization |
| B16 | M5.5–M5.7 | Starts with B05; completes after B15 | Clean-machine packaging, signing/updates, diagnostics and release docs |
| B17 | M6.1–M6.2 | B07/B09/B13 | Transactional outbox, revision-aware provider, retry/credential lifecycle |
| B18 | M6.3–M6.6 | B17 | Conflict/deletion safety, coordinated JSONBin transition, complete sync journeys |
| B19 | M7.1–M7.3 | B10/B15/B16/B18 | Packaged upgrade/recovery/soak evidence and release candidate |
| B20 | M7.4–M7.5 | B19 | Support/rollback documentation and stable cutover |

The order above is a dependency sequence, not authorization to release or modify a remote sync schema. Infrastructure work in B16 starts early; it should not be treated as a final-week task.

## Feature-parity checkpoint before stable replacement

- [ ] Configurable Pomodoro work/short/long breaks and cycle interval.
- [ ] Stopwatch with precise active duration and pause/resume.
- [ ] Minimal compact mode: default countdown target 200 × 44 logical pixels, one visible play/pause control, pin/finish/exit through an accessible context menu, keyboard return to main, scalable text, supported transparency, remembered geometry.
- [ ] Existing task add/edit/complete/delete behavior, with archive/undo and preserved history.
- [ ] Optional task synchronization, documented migration, clear offline/conflict state.
- [ ] Daily focus totals with Pomodoro/stopwatch breakdown, richer reports/export, and the existing reset-today action with confirmation, backup, atomic date-scoped deletion, and no-active-session guard.
- [ ] Audio and native notifications, accessible controls, reachable background app.
- [ ] Existing data imported with verified counts and duration totals.
- [ ] Windows, macOS, and Linux pass packaged acceptance together.

## Release blockers

Any data-loss path, timer duplication/accounting error, failed legacy migration, inaccessible essential control, unreachable hidden app, unsafe sync overwrite/resurrection, missing supported-platform package, or invalid update signature blocks stable cutover. A generated mockup, a successful compile, or a cross-compiled artifact cannot satisfy those checks.
