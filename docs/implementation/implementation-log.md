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
