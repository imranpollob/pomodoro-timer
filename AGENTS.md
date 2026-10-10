# Repository Guidelines

## Product & Scope

Pomodoro Timer v1: **Tauri 2, Rust, Svelte/TypeScript, SQLite** on Windows, macOS, and Linux. Follow the MVP scope in `docs/implementation/backlog.md` and the UI specification; record evidence in `implementation-log.md`. The legacy Python app was removed in October 2026 (recoverable from git history); no legacy import exists. Pin toolchains and lock dependencies; the user owns commits and pushes.

App identity is `com.imranpollob.pomodoro-timer` (version 1.0.0); profiles live in Tauri's app-data directory for that identifier unless `POMODORO_DATA_DIR` overrides it. Keep one backend timer authority with injected clocks, session snapshots, sleep/wake handling, and transactional persistence. Tasks are assigned before a session starts and saved with its title. UI/tray/shortcuts share commands/state. Compact countdown targets **200 × 44 logical pixels**: time, phase indicator, one play/pause button. Close, pin, finish, and exit actions belong in the accessible context menu; closing compact must not quit the app or reopen main.

## Project Structure

`crates/focus-core/` owns timer/service/SQLite; `src-tauri/` owns native integration; `src/` contains Svelte views. Frontend tests use `tests/` (Playwright) and colocated Vitest files; Rust tests accompany modules. Helper scripts (native smoke, Windows UI harness, demo seeder, deb fix) live in `scripts/` and run with system Python 3.12.

## Build, Test, and Development Commands

From the repo root, install native prerequisites per the README:

- `npm ci`; `npm run tauri -- dev`: install/start.
- `npm run build`; `npm test`; `npm run test:ui`: frontend checks.
- `cargo test --locked -p focus-core`; `cargo test --locked -p pomodoro-desktop --lib`: core regressions.
- `cargo fmt --all --check`; `cargo clippy --locked --workspace --all-targets -- -D warnings`: style/lint.
- `cargo build --locked -p pomodoro-desktop --features custom-protocol,smoke-test`, then `python scripts/native_smoke.py target/debug/pomodoro-desktop` (wrap with `dbus-run-session -- xvfb-run --auto-servernum` on headless Linux): native IPC smoke.
- `npm run tauri -- build --ci --bundles deb -- --locked`, then `sh scripts/fix_deb_depends.sh target/release/bundle/deb/*.deb`: Linux package.

## Coding Style & Naming Conventions

Use rustfmt and two-space TypeScript/Svelte indentation. Rust functions use `snake_case`, TypeScript uses `camelCase`, types/components use `PascalCase`. Frontend views must not own timer state.

## Testing Guidelines

Use Rust unit tests, Vitest `*.test.ts`, and Playwright `*.spec.ts`. Inject clocks/failures and isolate profiles via `POMODORO_DATA_DIR`. Never distribute the `smoke-test` feature.

Use `platform-validation.md` for installed-build checks on all three OSs, including the user's Mac/Linux. Record revision, OS, architecture, desktop session and results. CI/WSL/browser fixtures do not establish physical desktop acceptance.

## Commit & Pull Request Guidelines

Use descriptive subjects. PRs explain behavior, tests, platform limitations, issues, and UI screenshots.

## Configuration & Data Safety

Use `POMODORO_DATA_DIR` for isolated profiles. Never modify user data outside the selected profile. Keep credentials/personal data/build outputs out of Git. Preserve backups and deletion knowledge.
