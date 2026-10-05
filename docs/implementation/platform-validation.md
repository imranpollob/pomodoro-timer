# Native prototype validation

M0 is closed following the user's confirmation that Windows/macOS/Linux CI passed. These checks apply to the **new Tauri prototype**, whose platform gate remains open. The new workflow builds beta packages and runs native IPC smoke tests on all three OSs; its remote results are pending.

## Available evidence

| Environment | Core/frontend | Native IPC | Packaged installation | Desktop capabilities |
| --- | --- | --- | --- | --- |
| Windows 11 Home 10.0.26300, x64, 125% DPI | 20 Rust / 6 frontend / 6 browser UI tests pass; native development launch user-confirmed | Native rendered controls, real IPC and SQLite passed | Unsigned current-user NSIS install / normal UIA / uninstall passed | Background keys, pinning, compact geometry, single-instance and restart recovery automated; physical power cycle/Narrator/manual delivery pending |
| WSL Ubuntu 26.04.1, x86_64, Xvfb | Rust tests/build/lint passed | Both webviews and SQLite smoke passed | Pending | Physical desktop checks pending |
| User's native macOS | Pending | Pending | Pending | Pending |
| User's native Linux | Pending | Pending | Pending | Pending |

WSL/Xvfb establishes compilation, webview IPC and storage behavior. A browser fixture verifies rendered UI interactions. Record native evidence separately; neither establishes physical audio delivery, desktop tray visibility, screen-reader support, suspend behavior or installed-package readiness.

## Windows record — October 5, 2026

Source: base revision `1c362b9` plus the working-tree integration changes. Tools: Rust 1.99.0, Node 24.19.0/npm 11.17.0, Python 3.12.15, Microsoft C++ Build Tools, WebView2. Display DPI: 120 (125%). Windows-specific work is in scope now; the user requests macOS/Linux-specific work when on those machines.

Normal-build UI Automation invokes real accessible controls and proves focus-independent global timer/reopen shortcuts using a separate foreground test window. It confirms a 200 × 44 logical-pixel compact client area, one session record, native minimize/reopen, single-instance activation, driver absence and paused restart recovery. A separate feature-enabled harness checks rendered main/compact IPC, pin/text preference propagation, clamping, shortcut conflict preservation, and simulated native Windows suspend/lock messages.

The unsigned NSIS installer was tested in a new verified directory under `build/`; registry installation location and uninstall cleanup passed. Test SQLite profiles are temporary and separate from existing beta and Python data. `desktop/scripts/windows_install_smoke.ps1` refuses to replace a pre-existing beta installation.

The audio device accepted native playback and the installed notification request returned without an error. The user missed the test, so hearing and notification receipt are **unconfirmed**. Real sleep/wake, lock/unlock, tray visibility, Narrator, multiple monitors/removal and remaining display scales require manual Windows checks. Simulated broadcasts and UIA semantics do not satisfy those human checks.

## Test record

For each run, record date, commit SHA, OS/version, CPU architecture, desktop environment, Wayland/X11 session, display scale, package/build type and command. Use an isolated `POMODORO_BETA_DATA_DIR` and no real credentials. Attach results/screenshots and concise reproduction steps for failures. Do not mark an unsupported capability passed because its API call returned success.

## Installed-build journey

1. Build a normal prototype package using [desktop/README.md](../../desktop/README.md), install it, and launch without development servers. Confirm beta identity and isolated data directory.
2. Start focus, pause, wait, resume, finish; confirm one record and active time excluding pauses. Change durations mid-session; confirm that only the next session changes. Exercise stopwatch above an hour.
3. Open compact: exactly one visible play/pause action at 200 × 44 for countdown. Check time/phase, Space, time-region Enter, double-click, right-click, Shift+F10, drag, pin and main-window reopen. Main/compact/tray must control the same session.
4. Finish through the context menu; confirm the finish dialog opens in main. Close compact; main remains reachable. Close main with an active session; relaunch and confirm paused recovery without process-down time.
5. Launch a second instance; confirm the existing main window is focused and no second timer/record is created. On Linux also exercise desktops with no tray extension.
6. Test sound and notifications from Settings, then a real completion. Record permission prompts, disabled-system notification behavior, hidden-main audio, volume and mute. Test completion at a one-minute setting rather than waiting 25 minutes.
7. Test 100%, 125%, 150%, 200% display/text scale, narrow main windows, multiple monitors and monitor removal. Confirm readable digits and reachable controls. Compact geometry restoration/monitor clamping remain pending work.
8. Check keyboard focus, modal focus/return, semantic labels and reduced motion with Narrator, VoiceOver or Orca. Timer ticks must not create repeated spoken announcements.
9. Suspend/wake and lock/unlock during focus and stopwatch. Windows now pauses on native suspend/lock broadcasts using notification-time accounting and requires explicit resume. Verify that behavior on a real power/lock cycle. Native macOS/Linux suspend adapters and Wayland portal shortcuts remain pending; their current behavior is evidence, not acceptance.
10. Restart/kill during work, simulate a blocked write using only a disposable profile, and confirm recovery or visible retry without duplicated records. Preserve copies before fault injection.

## Gate decision

Track missing adapters, platform-specific defects and support baselines here. B05/M1.1 scaffolding can complete independently; M1.2–M1.5 remain open until native package and capability evidence is collected. Tauri remains provisional until all mandatory capabilities work on Windows, macOS and Linux. Signing, stable migration and release cutover are later gates.
