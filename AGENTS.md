# Repository Guidelines

## Rebuild Direction & Product Requirements

Follow `docs/implementation/implementation-plan.md`, `docs/implementation/backlog.md`, and `docs/implementation/ui-design-spec.md`; record evidence in `docs/implementation/implementation-log.md`. Proposed stack: **Tauri 2, Rust, Svelte/TypeScript, SQLite**, subject to packaged prototypes on Windows, macOS, and Linux. All three are mandatory. Resolve capability gaps with adapters or evaluate Qt.

Develop the replacement in a separate workspace. Keep the Python app usable until migration, feature parity, and platform acceptance pass. Preserve legacy data with backed-up, validated, idempotent migration. Pin toolchains and commit dependency lockfiles.

Keep one backend timer authority with injected clocks, session snapshots, explicit sleep/wake handling, and transactional persistence. UI/tray/shortcuts share commands/state. Compact countdown targets **200 × 44 logical pixels**: time, phase indicator, one play/pause button. Other actions belong in the accessible context menu. Follow the window/state inventory.

## Project Structure

Python UI/core services and runtime assets live in `src/`; screenshots are in `images/`, tests in `tests/`, smoke scripts in `scripts/`, packaging in platform directories and `pomodoro.spec`.

## Build, Test, and Development Commands

From the repository root:

- `uv sync --locked`: install dependencies.
- `uv run --locked python src/pomodoro.py`: launch locally.
- `uv run --locked python -m pytest -q`: run regressions.
- `uv run --locked python scripts/smoke_app.py`: check real Tk widgets.
- `uv run --locked pyinstaller --noconfirm pomodoro.spec`: package the app.

See `README.md` for installer commands. Headless Linux needs `xvfb-run --auto-servernum`. Document replacement commands when its workspace exists.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions/modules, `PascalCase` types, and `UPPER_CASE` constants. Python has no configured formatter/linter. Configure Rust formatting/linting and frontend checks with the replacement workspace. Tk operations stay on the main thread.

## Testing Guidelines

Use pytest `test_*.py`/`test_*`, fake clocks/responses, and temporary profiles. Preserve regressions; research probes document historical failures. Add core, migration, and packaged UI tests during rebuilding.

The user has native macOS/Linux machines available for testing; coordinate commands/results without assuming remote access. Supplement CI/WSL with installed-build checks: sleep/wake, tray/reopen, notifications/audio, shortcuts, monitors/scaling, accessibility, and Linux Wayland/X11. Record OS/version, architecture, desktop session, build revision, and results. Require three-platform evidence before closing platform gates.

## Commit & Pull Request Guidelines

Use descriptive subjects, following “Fix Linux release packaging.” PRs explain behavior, tests, platform limitations, related issues, and UI screenshots. Python version bumps use `uv version --bump patch`.

## Configuration & Data Safety

Use `POMODORO_DATA_DIR` for isolated legacy profiles. Keep credentials/personal data/build outputs out of Git. Preserve backups and deletion knowledge; JSONBin whole-bin concurrency requires a replacement protocol.
