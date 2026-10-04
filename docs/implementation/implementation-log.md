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
