# Repository Guidelines

## Rebuild Direction & Product Requirements

Follow the MVP scope in `docs/implementation/backlog.md` and UI specification; record evidence in `implementation-log.md`. M0 is closed; M1 uses **Tauri 2, Rust, Svelte/TypeScript, SQLite**, provisionally. Windows, macOS, and Linux are mandatory. Resolve capability gaps with adapters or evaluate Qt.

Keep the Python app available while the beta is developed. Legacy data migration and old JSONBin data are outside MVP scope; protect data created by the beta. Pin toolchains and lock dependencies; the user owns commits and pushes.

Keep one backend timer authority with injected clocks, session snapshots, sleep/wake handling, and transactional persistence. Tasks are assigned before a session starts and saved with its title. UI/tray/shortcuts share commands/state. Compact countdown targets **200 × 44 logical pixels**: time, phase indicator, one play/pause button. Close, pin, finish, and exit actions belong in the accessible context menu; closing compact must not quit the app or reopen main.

## Project Structure

`desktop/crates/focus-core/` owns timer/service/SQLite; `desktop/src-tauri/` owns native integration; `desktop/src/` contains Svelte views. Frontend tests use `desktop/tests/`; Rust tests accompany modules. Python source/assets remain in `src/`, tests in `tests/`, smoke scripts in `scripts/`, and packaging in platform directories/`pomodoro.spec`.

## Build, Test, and Development Commands

Legacy commands from the root:

- `uv sync --locked`: install; `uv run --locked python src/pomodoro.py`: launch.
- `uv run --locked python -m pytest -q`: regressions.

From `desktop/`, install native prerequisites per its README:

- `npm ci`; `npm run tauri -- dev`: install/start.
- `npm run build`; `npm test`; `npm run test:ui`: frontend checks.
- `cargo test --locked -p focus-core`: core regressions.
- `cargo fmt --all --check`; `cargo clippy --locked --workspace --all-targets -- -D warnings`: style/lint.

## Coding Style & Naming Conventions

Use four-space Python indentation, rustfmt, and two-space TypeScript/Svelte indentation. Rust/Python functions use `snake_case`, TypeScript uses `camelCase`, types/components use `PascalCase`. Python has no formatter/linter. Tk operations stay on the main thread; frontend views must not own timer state.

## Testing Guidelines

Use pytest `test_*.py`/`test_*`, Rust unit tests, Vitest `*.test.ts`, and Playwright `*.spec.ts`. Inject clocks/failures and isolate profiles. Research probes document historical failures. Never distribute the `smoke-test` feature.

Use `platform-validation.md` for installed-build checks on all three OSs, including the user's Mac/Linux. Record revision, OS, architecture, desktop session and results. CI/WSL/browser fixtures do not establish physical desktop acceptance.

## Commit & Pull Request Guidelines

Use descriptive subjects. PRs explain behavior, tests, platform limitations, issues, and UI screenshots. Python version bumps use `uv version --bump patch`.

## Configuration & Data Safety

Use `POMODORO_DATA_DIR` for legacy profiles and `POMODORO_BETA_DATA_DIR` for beta profiles. Never modify legacy data from the prototype. Keep credentials/personal data/build outputs out of Git. Preserve backups and deletion knowledge.
