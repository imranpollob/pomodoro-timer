# Pomodoro Timer

A local desktop focus timer for Windows, macOS, and Linux, built with Tauri 2, Rust, Svelte/TypeScript, and SQLite. App identifier: `com.imranpollob.pomodoro-timer`; version: `1.2.0`.

## Features

- Pomodoro and stopwatch modes, editable durations, pause/resume, and confirmed finish or skip.
- A 170 × 44 compact countdown with play/pause and an options menu. Closing compact keeps the timer running.
- To do / In progress / Done tasks. Choose a task before starting; saved sessions retain its title after edits or removal.
- Local-date session reports, a three-month task-completion heatmap, and a current streak. Reset reports deletes sessions and completion history while keeping the task board.
- Light/dark themes, completion sound and volume, notifications, pinning, and saved window placement.
- Installed version in Settings, with manual update checks and a link to newer GitHub releases.
- Optional Google sign-in and Supabase task sync, with durable offline edits and deletions.
- A single Rust timer authority with transactional persistence, checkpoints, and paused recovery after restart.

## Run

Install [Tauri's native prerequisites](https://v2.tauri.app/start/prerequisites/), Rust through rustup, and Node **24.19.0** with npm **11.17.0**. The Rust toolchain is pinned to **1.99.0**; both dependency lockfiles are committed. Python **3.12** runs the helper scripts.

| Platform | Native prerequisites |
| --- | --- |
| Windows | Microsoft C++ Build Tools with Desktop development with C++, Windows SDK, and WebView2. Restart the terminal after installing Rust. Native Windows builds use native Cargo, independently of WSL. |
| macOS | Xcode Command Line Tools: `xcode-select --install`. |
| Ubuntu/Debian | WebKitGTK 4.1, GTK 3, AppIndicator, OpenSSL, ALSA, librsvg, libxdo, and build tools; the exact packages are in [.github/workflows/ci.yml](.github/workflows/ci.yml). |

```sh
npm ci
npm run dev
```

`npm run dev` opens the desktop app. `npm run dev:frontend` starts only the frontend server and requires a desktop connection or test fixture.

## Build and test

```sh
npm run build:frontend
npm test
npm run test:sync-schema
npx playwright install chromium
npm run test:ui
cargo fmt --all --check
cargo test --locked -p focus-core
cargo test --locked -p pomodoro-desktop --lib
cargo clippy --locked --workspace --all-targets -- -D warnings
```

`npm run build` packages for the current OS. For a specific package:

| Host | Command |
| --- | --- |
| macOS | `npm run tauri -- build --ci --bundles dmg -- --locked` |
| Windows | `npm run tauri -- build --ci --bundles nsis -- --locked` |
| Linux | `npm run tauri -- build --ci --bundles deb -- --locked` |

Packages are written under `target/release/bundle/` and are unsigned. On Linux, repair the Debian dependencies before installation:

```sh
sh scripts/fix_deb_depends.sh target/release/bundle/deb/*.deb
```

CI validates and builds all three platforms on `v*` tags or manual dispatch. It uploads package artifacts; it does not publish a GitHub Release. Commits, tags, and pushes are managed by the repository owner.

Settings → About shows the installed version. **Check for updates** compares it with the latest published stable GitHub Release. When a newer version is available, **View release** opens its GitHub page in your browser so you can download and run the installer for your platform. Checks run only when requested and require an internet connection; draft releases, prereleases, and CI artifacts are not offered as updates.

For native IPC checks, build a separate test executable with an isolated temporary profile:

```sh
cargo build --locked -p pomodoro-desktop --features custom-protocol,smoke-test
python3 scripts/native_smoke.py target/debug/pomodoro-desktop
```

Use `python` and the `.exe` suffix on Windows. On headless Linux, prefix the Python command with `dbus-run-session -- xvfb-run --auto-servernum`. Never distribute the `smoke-test` feature. The Windows UI and installer harnesses are in `scripts/`; their dependencies are pinned in `scripts/requirements-windows-ui.txt`.

Browser tests mock IPC. Verify installed builds separately on each desktop: main/compact/tray controls, keyboard and screen-reader access, audio/notification delivery, sleep/lock, scaling, and monitor changes. Record the revision, OS, architecture, desktop session, scale, and results with the change.

## Google sign-in and task sync setup

The app works locally without a Supabase project. Until a project is configured, Settings → Account & sync explains that Google sign-in is unavailable and keeps its sign-in button disabled.

1. Create a **Free** project at [Supabase](https://supabase.com/dashboard). Save the database password in your password manager; the desktop app does not need it.
2. In the project's **SQL Editor**, run [the task sync migration](supabase/migrations/202610210001_task_sync.sql). This creates the task table, access policy and transactional `sync_tasks` function. The PostgreSQL tests use PGlite and run with `npm run test:sync-schema`.
3. In **Authentication → URL Configuration → Redirect URLs**, add exactly:
   ```text
   http://127.0.0.1:43821/auth/callback/*
   ```
   The final segment is a random, one-use value generated by the app. The callback listener binds only to the loopback interface while signing in and closes on completion, cancellation or timeout.
4. In [Google Cloud Console](https://console.cloud.google.com/auth/clients), configure your OAuth consent screen and create an OAuth client with application type **Web application**. Add this authorized redirect URI, replacing the project reference:
   ```text
   https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
   ```
   While your Google consent screen is in Testing, add your Google account as a test user.
5. In Supabase **Authentication → Sign In / Providers → Google**, enable Google and enter the Google client ID and client secret. Keep the secret in Supabase; never include it in the desktop app or source repository. See [Supabase's Google provider instructions](https://supabase.com/docs/guides/auth/social-login/auth-google).
6. Copy [.env.example](.env.example) to `.env.local` in the repository root. Set `SUPABASE_URL` to your project's HTTPS URL and `SUPABASE_PUBLISHABLE_KEY` to its publishable key (a legacy **anon** key also works). Find these in the project's Connect dialog or API settings. The app rejects secret/service-role keys. Restart `npm run dev` after changing the file; configuration is embedded at build time.
7. For GitHub builds, add those same two public values as repository **Actions variables**, named `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`. The workflow passes them into each desktop build. All devices must use builds configured for the same Supabase project.

Settings → Account & sync opens Google sign-in in the system browser using PKCE. The app stores only the refresh token in the OS credential store: macOS Keychain, Windows Credential Manager, or Linux Secret Service. A locked/unavailable store is reported as an error; tokens are never saved in SQLite or browser storage. Linux sign-in requires an available, unlocked Secret Service provider such as GNOME Keyring or KWallet.

Task names, status and deletions sync after edits and at roughly 30-second intervals while signed in. **Sync now** triggers a manual pass. The first sign-in uploads the tasks already on that device and downloads the account's tasks. Focus sessions, completion-history reports, streaks and device preferences remain local in this version.

Edits are queued durably in SQLite, including while signed out or offline. Server revisions detect concurrent changes without relying on device clocks. When two devices edit the same task from an older revision, the server's existing copy wins and the app reports the conflict. Deletion markers remain on the server so stale offline edits do not resurrect deleted tasks. Requests can be retried without creating duplicate tasks, and edits made during an upload remain queued.

A local profile is bound to the first signed-in account and project. Signing out keeps its tasks on the device; it does not erase them or sign out other devices. Signing into a different account/project cannot upload that profile's tasks. Use a separate `POMODORO_DATA_DIR` profile for another account. A cloud project and Google OAuth configuration are required to test real sign-in and cross-device sync; the automated tests use isolated local databases and mocked UI sessions.

## Profiles and backups

Set `POMODORO_DATA_DIR` **before launch** to choose a profile. Defaults:

| OS | Directory |
| --- | --- |
| Windows | `%APPDATA%\com.imranpollob.pomodoro-timer\` |
| macOS | `~/Library/Application Support/com.imranpollob.pomodoro-timer/` |
| Linux | `$XDG_DATA_HOME/com.imranpollob.pomodoro-timer/`, or `~/.local/share/com.imranpollob.pomodoro-timer/` |

Close the app and back up the entire profile, including `pomodoro.sqlite3` and any `-wal`/`-shm` sidecars. Uninstalling the app leaves profile data in place. Upgrading a pre-v4 database clears its task list once; saved sessions, task-title snapshots, settings, and checkpoints are preserved.

The retired Python app (`v0.3.1`) is recoverable from Git history and has no automatic import. Its profiles are `%APPDATA%\pomodoro-timer\` on Windows and `~/.config/pomodoro-timer/` on macOS/Linux. Back up `todos.json` and `history.json`; recreate tasks manually and retain the backup for history or rollback. The current app does not modify those files.

For sample data, seed an isolated profile while the app is closed:

```sh
python3 scripts/seed_demo_profile.py --profile .demo-profile
POMODORO_DATA_DIR="$PWD/.demo-profile" npm run dev
```

In PowerShell, use `python` and set `$env:POMODORO_DATA_DIR` to the demo profile before launching. Repeated seeding uses stable IDs to avoid duplicates.

## Desktop behavior and limits

- Windows pauses on native suspend/lock and requires explicit resume. macOS/Linux have no native suspend adapter in v1.0.0.
- Windows/Linux close to tray by default. On macOS, closing the window keeps the app running; use Dock/menu-bar controls to reopen it and Cmd+Q or Quit to exit.
- Compact options include Close compact, Open main, Pin, and Sound. Drag the time or empty strip to move the window. Escape closes compact; Enter/double-click on the time opens main. Space starts/pauses/resumes. Long stopwatch hours grow the strip automatically.
- Settings save automatically. Failed session writes remain visible and require retry; a crash can lose time since the last checkpoint.
- Notifications and sound depend on OS settings and devices. API success or browser tests do not establish physical delivery or installed-app accessibility.
- Projects, session-history sync, legacy import, data export, custom themes, and automatic updates are outside the current scope.

## Code layout and contributions

`crates/focus-core/` owns the clock-injected timer service and SQLite storage; `src-tauri/` owns native integrations; `src/` renders Svelte views; `tests/` contains browser tests; `scripts/` contains demo, smoke, and packaging helpers.

Keep timer authority in Rust, use isolated profiles for tests, and preserve saved history. Use rustfmt and two-space TypeScript/Svelte indentation. Run the checks above and describe behavior, tests, platform limitations, and UI screenshots with changes. Keep credentials, personal data, and build outputs out of Git. Report vulnerabilities privately through the repository's GitHub Security page.

Earlier design mockups, implementation logs, and platform records are retained in Git history. This README is the current documentation.
