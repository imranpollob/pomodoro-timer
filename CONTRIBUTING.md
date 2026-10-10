# Contributing

Thanks for helping improve Pomodoro Timer.

## Setup

Follow the [development guide](docs/development.md), then run `npm ci`.

## Before opening a pull request

Run the same checks as CI from the repo root:

```sh
npm run build && npm test && npm run test:ui
cargo fmt --all --check
cargo test --locked -p focus-core
cargo test --locked -p pomodoro-desktop --lib
cargo clippy --locked --workspace --all-targets -- -D warnings
```

CI runs on Linux, Windows and macOS. Code that is only used on one platform must be gated with `#[cfg]` so the other platforms stay warning-free under `-D warnings`.

## Guidelines

- Keep one backend timer authority; frontend views must not own timer state.
- Use rustfmt, two-space indentation for TypeScript/Svelte, and the repo's naming conventions (`snake_case` Rust, `camelCase` TypeScript, `PascalCase` types/components).
- Inject clocks and failures in tests, and isolate profiles with `POMODORO_DATA_DIR`.
- Never enable the `smoke-test` feature in distributed builds.
- Do not commit credentials, personal data or build output.
- Use descriptive commit subjects. In the PR, explain behavior, tests, platform limitations and include UI screenshots.

Native desktop behavior is validated with [platform-validation.md](docs/implementation/platform-validation.md); CI and browser fixtures do not replace it.
