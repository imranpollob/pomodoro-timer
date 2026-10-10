# Development guide

Build, test, package and validate Pomodoro Timer locally. For a product overview see the [README](../README.md); for contribution rules see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Run locally

Install the [Tauri native prerequisites](https://v2.tauri.app/start/prerequisites/), Rust through rustup, and Node **24.19.0** (npm **11.17.0**). Rust **1.99.0**, rustfmt, and Clippy are selected by `rust-toolchain.toml`. Frontend dependencies and Cargo dependencies are locked.

- Windows: Microsoft C++ Build Tools with Desktop development with C++, WebView2, and Python 3.12 for the UI harness.
- macOS: Xcode Command Line Tools (`xcode-select --install`).
- Ubuntu/Debian: WebKitGTK 4.1, GTK 3, AppIndicator, OpenSSL, ALSA headers (`libasound2-dev`), librsvg and build tools. See the prerequisite guide and `.github/workflows/ci.yml` for packages.

```text
npm ci
npm run tauri -- dev
```

`npm run dev` alone opens the frontend with a desktop-connection message; production code never substitutes a browser timer for the Rust authority.

### Seed demo data for UI review

To inspect Tasks, rolling 7-day/30-day and custom Reports, and settings, run the seeder while the app is closed. It adds four demo tasks and two months of focus, short/long break, stopwatch, completed, skipped, and interrupted sessions to the selected profile. Existing tasks, sessions, settings, and checkpoints are kept. Stable IDs make repeated runs safe and avoid duplicate demo records. On Windows, macOS, and Linux the default is the Tauri app-data directory; `POMODORO_DATA_DIR` or `--profile PATH` selects another profile. Restart the app after seeding so tasks and reports reload.

Windows PowerShell, from the repo root:

```powershell
python scripts/seed_demo_profile.py
npm run tauri -- dev
```

macOS/Linux, from the repo root:

```sh
python3 scripts/seed_demo_profile.py
npm run tauri -- dev
```

Pass `--profile PATH` to seed a different profile. Close the app before seeding to avoid competing writers.

### Windows first-time setup

Node/npm alone are insufficient to launch the native application. If Tauri reports `cargo metadata ... program not found`, Rust/Cargo is missing or the terminal has not picked up its installation. Install the C++ workload from an **administrator PowerShell**, and Rust from your normal user PowerShell:

```powershell
winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --source winget --override "--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
winget install --id Rustlang.Rustup --exact --source winget
```

The C++ workload includes MSVC and the Windows SDK; its installer requires administrator approval. Installer exit code **1602** indicates cancellation, not a completed installation. After both installations finish, restart the IDE and terminal so they pick up Cargo's PATH, then run:

```powershell
cd C:\Users\imran\Coding\pomodoro-timer
rustup toolchain install 1.99.0 --profile minimal --component rustfmt --component clippy
cargo --version
npm ci
npm run tauri -- dev
```

Use your checkout's path if different. Install [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) if Windows reports that it is missing. A `link.exe not found` or Windows SDK error means the C++ workload is incomplete; installing Rust alone does not supply these tools. Rust installed inside WSL is separate from native Windows Rust.

## Version 1 behavior

- Pomodoro, short/long breaks, stopwatch, precise pause/resume and explicit finish confirmation.
- Main window and **200 × 44** compact countdown with one action button. Click/double-click time, use an assistive-technology invoke, or press Enter there to reopen main; right-click/Shift+F10 opens the native menu. Escape or **Close compact timer** hides only the strip; it does not quit the app or reopen main. Space starts/pauses/resumes. Main remains reachable if the desktop has no tray.
- Settings save automatically shortly after each edit; invalid timer values are skipped. On Windows and Linux, closing the main window hides it to the system tray by default while the timer keeps running; left-click the tray icon or choose Open Pomodoro to restore it, and Exit to quit. The close behavior can be changed in Settings. On macOS, closing the main window always keeps the app running; Dock-icon clicks reopen it, and Cmd+Q or Quit exits. macOS Settings offer Show in menu bar (default on) and Hide Dock icon (default off, requires the menu bar icon so the app stays reachable) instead of the close-to-tray option.
- One serialized Rust service processes UI/tray commands. Window subscriptions accept monotonically increasing revisions. No frontend timer decrements session duration.
- SQLite transactions save completed/interrupted/skipped sessions and paused checkpoints together. Checkpoints occur on transitions and every 15 seconds while running. Restart restores paused and excludes time while the process was absent. A crash can lose active time since the last checkpoint.
- Failed saves freeze active time, block replacement sessions, and expose retry. Preferences apply to future sessions. The Tasks view supports add/edit/complete/remove; a task can be selected for the next session and its title is saved with the session. Removing a task preserves its title in existing session history.
- The timer page shows a local-calendar-day total split between Pomodoro and stopwatch time and session counts. Reports is the only session-history page and includes all saved records in the selected range.
- Reports open on Today and provide Last 7 days / Last 30 days presets (the preset matching the selected range is highlighted) and custom local-date ranges, aggregate and per-day focus summaries, and session rows with task titles and outcomes. CSV export and per-row Details actions are removed. A confirmed Reset reports action in Settings deletes every recorded session. An opt-in setting auto-starts the next focus/break only after natural timer completion; manual finish, skip, and stopwatch remain manual.
- Appearance settings are a light/dark theme and compact-mode background opacity. All four pages use shared typography and concise content titles. Promotional headers and sidebar slogans are removed; Compact mode opens from the timer page.
- Native audio works independently of webview visibility, with volume control and output-device errors. Completion notifications are on by default.
- Windows suspend/lock broadcasts pause active work using the notification's timestamp; wake/unlock requires explicit resume. The listener bounds its checkpoint wait to one second. Failed or slow writes retain the existing retry/recovery behavior. Native macOS/Linux suspend adapters are not included in v1.0.0.
- SQLite stores desktop preferences, compact pinning, and debounced main/compact placement. Placement is clamped to connected monitor work areas on Windows. The compact strip keeps a fixed text size and grows automatically for long stopwatch hours; manual edge resizing is disabled. The compact strip has no native shadow to preserve its height on Windows.

Set `POMODORO_DATA_DIR` **before launching** to use an isolated profile. The default is Tauri's app-data directory for the app identifier. `pomodoro.sqlite3` and its WAL/SHM sidecars belong to this profile. Back up the whole profile with the app closed. Schema 3 upgrades earlier Tauri schemas transactionally and retains existing sessions/checkpoints. Legacy Python data and old JSONBin data are not imported or modified; see [MIGRATION.md](../MIGRATION.md) for the manual steps.

## Verify and build

```text
npm run build
npm test
npx playwright install chromium
npm run test:ui
cargo fmt --all --check
cargo test --locked -p focus-core
cargo test --locked -p pomodoro-desktop --lib
cargo clippy --locked --workspace --all-targets -- -D warnings
npm run tauri -- build --ci -- --locked
```

Rust tests inject clocks and persistence failures. Vitest verifies event ordering and listener cleanup. Playwright exercises actual Svelte views with a test-only IPC fixture; it does not prove native menus, assistive technology, or OS behavior. Normal builds have no simulated backend or embedded test driver.

Production packages use normal features. A separate executable with the `smoke-test` feature validates native webview IPC, shared commands, session persistence and checkpoint read-back:

```text
cargo build --locked -p pomodoro-desktop --features custom-protocol,smoke-test
python scripts/native_smoke.py target/debug/pomodoro-desktop
```

Use `.exe` on Windows; on headless Linux wrap the Python command with `dbus-run-session -- xvfb-run --auto-servernum`. The smoke uses a temporary profile and exits itself. Smoke code is compiled out of normal builds, and this feature must never be enabled for distributed artifacts.

### CI and release packages

The **Validate Pomodoro** workflow runs when a `v*` version tag is pushed or when started manually from GitHub Actions. Ordinary branch pushes and pull requests do not start it. To run validation for a release, push its version tag, for example:

```sh
git tag v1.0.1
git push origin v1.0.1
```

The workflow's native runners build unsigned Linux `.deb`, Windows NSIS `.exe`, and macOS `.dmg` packages, then store them as workflow artifacts. It does not publish a GitHub Release or attach assets automatically. The v1.0.0 packages are available from the [GitHub release](https://github.com/imranpollob/pomodoro-timer/releases/tag/v1.0.0).

### Local packages

By default, Tauri builds a package for the operating system where the command runs; one macOS build does not produce all three platform packages. Use the macOS command below for a local `.dmg`. The Windows and Linux sections below give the local `.exe` and `.deb` commands. Packages are unsigned; signing and notarization are not configured.

#### macOS `.dmg`

On macOS, with the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) installed:

```sh
npm ci
npm run tauri -- build --ci --bundles dmg -- --locked
```

The `.app` bundle is written under `target/release/bundle/macos/`; the disk image is under `target/release/bundle/dmg/`. This builds for the Mac's architecture. For a universal Apple Silicon and Intel DMG, install both Rust targets and use the universal target:

```sh
rustup target add aarch64-apple-darwin x86_64-apple-darwin
npm run tauri -- build --ci --bundles dmg --target universal-apple-darwin -- --locked
```

The latest recorded local attempt built the `.app` but stopped during Finder formatting of the DMG; the CI runner produced a DMG for that revision. See the [platform record](implementation/platform-validation.md) for the recorded result.

If the DMG command fails with `Not authorised to send Apple events to Finder (-1743)`, allow the terminal app to control Finder in **System Settings → Privacy & Security → Automation**, then rerun it. See [Apple's Automation settings guide](https://support.apple.com/en-nz/guide/mac-help/mchl108e1718/mac).

#### Windows NSIS `.exe` from macOS (optional)

Tauri supports cross-compiling an NSIS installer from macOS, with caveats. Install the required tools and Windows target:

```sh
brew install nsis llvm
export PATH="$(brew --prefix llvm)/bin:$PATH"
rustup target add x86_64-pc-windows-msvc
cargo install cargo-xwin --version 0.23.1 --locked
```

Then build the installer:

```sh
npm ci
npm run tauri -- build --ci --bundles nsis --runner cargo-xwin --target x86_64-pc-windows-msvc -- --locked
```

The installer is under `target/x86_64-pc-windows-msvc/release/bundle/nsis/`. Tauri describes this cross-build as less tested than building on Windows; this repository's automated Windows package build uses a native Windows runner. See the [Tauri cross-compilation instructions](https://v2.tauri.app/distribute/windows-installer/#build-windows-apps-on-linux-and-macos).

Create the Linux `.deb` on Linux. From macOS, use a Linux VM/container or download the Linux artifact from the workflow; this repository does not include a container build recipe. Tauri recommends Docker or GitHub Actions for Linux builds because the base distribution affects compatibility; see its [Linux packaging guidance](https://v2.tauri.app/distribute/debian/).

### Windows packages and normal-build checks

On Windows, install the prerequisites in [Windows first-time setup](#windows-first-time-setup). From the repo root, run:

```powershell
npm ci
npm run tauri -- build --ci --bundles nsis -- --locked
py -3.12 -m venv build/windows-uia-env
$testPython = (Resolve-Path build/windows-uia-env/Scripts/python.exe).Path
& $testPython -m pip install -r scripts/requirements-windows-ui.txt
& $testPython scripts/windows_ui_smoke.py target/release/pomodoro-desktop.exe
$installer = Get-ChildItem target/release/bundle/nsis/*-setup.exe | Select-Object -First 1
./scripts/windows_install_smoke.ps1 -Installer $installer.FullName -Python $testPython
```

The installer is written under `target/release/bundle/nsis/` with a `*-setup.exe` name. This is distinct from the app executable at `target/release/pomodoro-desktop.exe`; the smoke commands below check both.

Use Python 3.12 to create a separate environment for the UI test dependencies. The harness drives a normal binary through Windows UI Automation, with temporary data and no embedded driver. It checks compact size, accessible reopen, settings save, single-instance behavior, checkpointing and restart recovery. An unlocked desktop session is required.

The installer probe refuses to replace an existing installation, verifies its install directory inside the workspace, and removes only that test installation. Silent uninstall retains application data. The v1.0.0 packages are unsigned; code signing and an in-app updater are not included.

Sound and notification delivery require manual confirmation on the installed app; API success does not confirm hearing or receipt, and desktop permission APIs do not establish Windows Focus Assist or notification-center delivery.

### Linux packages and normal-build checks

Install the native prerequisites (same set as CI):

```sh
sudo apt-get update
sudo apt-get install --yes build-essential libwebkit2gtk-4.1-dev libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libxdo-dev libasound2-dev xvfb dbus-x11 x11-utils
```

From the repo root, build the package, repair its dependencies, and install:

```sh
npm ci
npm run tauri -- build --ci --bundles deb -- --locked
sh scripts/fix_deb_depends.sh target/release/bundle/deb/*.deb
sudo apt-get install --yes ./target/release/bundle/deb/*.deb
```

`fix_deb_depends.sh` rewrites the bundler's `libgtk-3-0` dependency into a `libgtk-3-0t64 | libgtk-3-0` alternate and adds the ALSA runtime the audio backend needs. The unpatched package refuses to install on Ubuntu 24.04+, Linux Mint 22+, and Debian 13+; the script is idempotent and leaves the data archive untouched. The `N: Download is performed unsandboxed ... _apt` notice during install is harmless; confirm with `dpkg -l pomodoro`. From macOS, create the `.deb` inside a Linux VM/container with the prerequisites above, or download the workflow's Linux artifact.

Launch the installed app with an isolated profile for acceptance checks:

```sh
POMODORO_DATA_DIR=/tmp/pomodoro-test pomodoro-desktop
```

`sudo apt-get remove pomodoro` removes the package but leaves per-user profile data in place.

## Architecture and platform checks

`crates/focus-core` owns the clock-injected domain, service and SQLite access, without Tauri dependencies. `src-tauri` supplies windows, events, tray, notifications and process lifecycle. `src` contains presentation and typed IPC consumers.

Use the [native platform checklist](implementation/platform-validation.md) for current evidence. CI builds all three platforms. The recorded Linux automated checks pass; its installed-app journey and physical checks remain open. On macOS, core/frontend tests and native IPC smoke passed on October 10, 2026; installed-app and native capability checks remain open. Windows also has physical and accessibility checks outstanding. Projects, automatic legacy-data import, cloud sync, data export, session-detail views, reset-today, custom themes, goals/reminders, and in-app updates are not included in v1.0.0.
