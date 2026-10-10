# Migration guide

This guide covers moving from the legacy Python app (`0.3.1`) to Pomodoro Timer `1.0.0`.

## What to expect

Pomodoro Timer `1.0.0` does not import data from the Python app. Back up your old profile before installing the new app. You can use the saved task list to recreate your tasks; session history remains available in the backup.

## 1. Back up the Python profile

Close the Python app, then copy its profile directory somewhere safe.

| OS | Profile directory |
| --- | --- |
| Windows | `%APPDATA%\pomodoro-timer\` |
| macOS | `~/.config/pomodoro-timer/` |
| Linux | `~/.config/pomodoro-timer/` |

The profile contains `todos.json` (tasks) and `history.json` (session history). The legacy app did not read `POMODORO_DATA_DIR`; its profile is in the default location above.

## 2. Install Pomodoro Timer 1.0.0

Download the Windows NSIS installer, macOS `.dmg`, or Linux `.deb` from the [v1.0.0 GitHub release](https://github.com/imranpollob/pomodoro-timer/releases/tag/v1.0.0). You can also build the app from source using the [development guide](docs/development.md).

The new app uses different installer and binary names from the Python app, so installing it does not replace the old app. Launch `1.0.0` and confirm that the Timer page opens without save errors.

## 3. Recreate your tasks

Use the backed-up `todos.json` as a reference to add your tasks in the new app. The Python app's session history is not imported; keep `history.json` in your backup if you need to refer to it later.

You can uninstall the Python app after you have confirmed that the new app works:

- Linux: `sudo apt-get remove pomodoro-timer` (the profile directory remains on disk).
- Windows and macOS: remove it through the usual app management tools.

## Pomodoro Timer 1.0.0 profile locations

| OS | Location |
| --- | --- |
| Windows | `%APPDATA%\com.imranpollob.pomodoro-timer\` |
| macOS | `~/Library/Application Support/com.imranpollob.pomodoro-timer/` |
| Linux | `~/.local/share/com.imranpollob.pomodoro-timer/` |

Set `POMODORO_DATA_DIR` before launching to use a different profile directory. The profile contains `pomodoro.sqlite3` and may include `-wal` or `-shm` sidecar files. Close the app before backing up the directory.

## Verification

- [ ] The app launches without save errors or retry banners.
- [ ] Your tasks have been recreated in the Tasks page.
- [ ] The timer starts, pauses, resumes, and finishes a short session; the session appears in Reports.
- [ ] Compact mode opens at the expected size and closes without quitting the app.
- [ ] Linux only: `dpkg -l pomodoro` shows version `1.0.0`, and `which pomodoro-desktop` resolves.

## Rollback

If you need to return to the Python app, uninstall `1.0.0`, reinstall [`v0.3.1`](https://github.com/imranpollob/pomodoro-timer/releases/tag/v0.3.1), and restore the profile backup. The new app does not modify the Python profile.

## Troubleshooting

- **`POMODORO_DATA_DIR` seems ignored:** set it before launching the app and point it to a directory, not to the `.sqlite3` file.
- **Two Pomodoro entries after installing on Linux:** both the legacy `pomodoro-timer` and current `pomodoro` packages may be installed. Remove the legacy package if you no longer need it.
- **Notifications or sound are missing:** delivery depends on OS settings, including Windows Focus Assist and notification settings, macOS notification settings, or Linux desktop notification settings. See [Version 1 behavior](docs/development.md#version-1-behavior).

## References

- [Development guide](docs/development.md) — install, run, and build instructions.
- [Backlog](docs/implementation/backlog.md) — implemented features and remaining acceptance checks.
- [Platform checklist](docs/implementation/platform-validation.md) — installed-app verification for each OS.
