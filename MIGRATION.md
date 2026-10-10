# Migration guide

How to move from the legacy Python app or the beta builds to the v1 Tauri app, without losing data.

## Pinned versions

| Stream | Version | Technology | Status |
| --- | --- | --- | --- |
| Legacy (v1) | `0.3.1` (git tag `v0.3.1`) | Python + Tk | Removed from this repo in October 2026; recoverable from git history and the Releases page |
| Beta (interim) | `0.1.0-beta.1` | Tauri 2 + Rust + Svelte | Unsigned CI builds only, never released |
| Current | `1.0.0` | Tauri 2 + Rust + Svelte | Primary version at the repository root |

## Scope

- There is **no automatic importer**. Legacy JSON data is not converted, and beta profiles are not moved for you. Both paths below are short manual procedures.
- Back up before you start. Every step below copies data; nothing deletes your old profile until you choose to remove it.
- The beta install on your machine (if any) keeps working until you replace it. The new package upgrades it in place (Linux) or sits alongside until you uninstall the old one (Windows/macOS, unsigned builds).

## 1. Back up your data

Find your current profile and copy the whole directory somewhere safe (USB drive, cloud folder, or `/tmp/migration-backup`).

| Stream | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Legacy `0.3.1` | `%APPDATA%\pomodoro-timer\` | `~/.config/pomodoro-timer/` | `~/.config/pomodoro-timer/` |
| Beta `0.1.0-beta.1` | `%APPDATA%\com.imranpollob.pomodoro-timer.beta\` | `~/Library/Application Support/com.imranpollob.pomodoro-timer.beta/` | `~/.local/share/com.imranpollob.pomodoro-timer.beta/` |

If you set a custom profile location, back that up instead:

- Legacy and current releases both honor `POMODORO_DATA_DIR`. Note the meaning changed: under `0.3.1` it pointed at JSON files (`settings.json`, `todos.json`, `history.json`); under `1.0.0` it points at the SQLite profile directory. If you export this variable globally, update it to the new location (Section 4) or unset it to use the default.
- Beta builds used `POMODORO_BETA_DATA_DIR`, which `1.0.0` ignores. Rename it to `POMODORO_DATA_DIR` if you rely on it.

Legacy contents worth keeping: `todos.json` (your task list) and `history.json` (your session history). Beta contents: `prototype.sqlite3` plus its `-wal`/`-shm` sidecars.

## 2. Path A: legacy `0.3.1` → `1.0.0`

1. Close the legacy app and back up its profile (Section 1).
2. Install `1.0.0` by following [development guide](docs/development.md) for your OS. The installers and binaries use different names from the legacy ones (`pomodoro-desktop` vs `pomodoro`), so installing does not overwrite the old app.
3. Launch `1.0.0` once and confirm a fresh profile is created (Timer page loads, no save errors).
4. Recreate your tasks in the Tasks page, using your backed-up `todos.json` as reference. Your legacy history stays in the backup as an archive; it is not imported.
5. Optional: uninstall the legacy app once you are settled:
   - Linux: `sudo apt-get remove pomodoro-timer` (leaves `~/.config/pomodoro-timer/` in place).
   - Windows/macOS: remove via Add/Remove Programs / Applications as usual.

## 3. Path B: beta `0.1.0-beta.1` → `1.0.0`

The database schema is unchanged (v3), so your beta data carries over with a file copy. The profile directory changes because the app identifier dropped the `.beta` suffix.

1. Close the beta app completely (tray → Exit/Quit, not just window close).
2. Back up the beta profile directory (Section 1).
3. Install `1.0.0`:
   - Linux: the package name is still `pomodoro`, so installing upgrades in place: `sudo apt-get install --yes ./Pomodoro_1.0.0_amd64.deb`. The old `/usr/bin/pomodoro-desktop-beta` binary is replaced by `/usr/bin/pomodoro-desktop`.
   - Windows/macOS: install the new package, then uninstall the old unsigned build at your convenience.
4. Launch `1.0.0` once so it creates the new profile directory, then close it again. The new locations are:
   - Windows: `%APPDATA%\com.imranpollob.pomodoro-timer\`
   - macOS: `~/Library/Application Support/com.imranpollob.pomodoro-timer/`
   - Linux: `~/.local/share/com.imranpollob.pomodoro-timer/`
5. Copy the database files from the beta directory into the new directory, renaming them:

   ```sh
   # Linux/macOS example (adjust paths per the table above)
   cp ~/.local/share/com.imranpollob.pomodoro-timer.beta/prototype.sqlite3* \
      ~/.local/share/com.imranpollob.pomodoro-timer/
   cd ~/.local/share/com.imranpollob.pomodoro-timer/
   for ext in "" "-wal" "-shm"; do
     [ -f "prototype.sqlite3$ext" ] && mv "prototype.sqlite3$ext" "pomodoro.sqlite3$ext"
   done
   ```

   Copy all sidecar files that exist (`-wal`, `-shm`); skipping them can lose recent sessions. Settings, tasks, sessions, and checkpoints all live in this database, so one copy carries everything.
6. If you used `POMODORO_BETA_DATA_DIR`, set `POMODORO_DATA_DIR` to the same directory (after renaming the files inside it) or unset it to use the new default.
7. Launch `1.0.0` and verify (Section 5). The beta directory is left untouched — delete it only after verification.

## 4. Default profile locations in `1.0.0`

| OS | Location |
| --- | --- |
| Windows | `%APPDATA%\com.imranpollob.pomodoro-timer\` |
| macOS | `~/Library/Application Support/com.imranpollob.pomodoro-timer/` |
| Linux | `~/.local/share/com.imranpollob.pomodoro-timer/` |

Override with `POMODORO_DATA_DIR` (must be set before launching). The profile holds `pomodoro.sqlite3` plus `-wal`/`-shm` sidecars; back up the whole directory with the app closed.

## 5. Verification checklist

- [ ] App launches with no save errors or retry banners.
- [ ] Tasks page shows your expected tasks (Path B: carried over; Path A: recreated).
- [ ] Reports totals match what you expect (Path B: compare against the beta before deleting it).
- [ ] Timer starts, pauses, resumes, and finishes one short session; the session appears in Reports.
- [ ] Compact mode opens at the small strip size and closes without quitting the app.
- [ ] Linux only: `dpkg -l pomodoro` shows `1.0.0`, and `which pomodoro-desktop` resolves.

## 6. Rollback

- Path A: uninstall `1.0.0`, reinstall `0.3.1` from the [Releases page](../../releases) (tag `v0.3.1`), restore your profile backup, and relaunch. Your legacy data was never modified by `1.0.0`.
- Path B: your beta directory is untouched (Section 3 copies, never moves). Reinstall the beta build, rename the files back if needed, and relaunch. Keep the backup from Section 1 until the new version has run cleanly for a few days.

## 7. Troubleshooting

- **Empty Tasks/Reports after Path B:** the files were likely copied while the beta was still running (tray icon), so the `-wal` sidecar is inconsistent. Close both apps and copy again from the backup.
- **`POMODORO_DATA_DIR` seems ignored:** it must be set before launching, and it must point at a directory, not the `.sqlite3` file itself.
- **Two Pomodoro entries after upgrading (Linux):** you have both the legacy `pomodoro-timer` and the new `pomodoro` packages installed. Remove the legacy one (Section 2, step 5) if you no longer need it.
- **Old beta binary still on PATH (Linux):** an upgrade from the beta `.deb` replaces `/usr/bin/pomodoro-desktop-beta` with `/usr/bin/pomodoro-desktop`. If the old path persists, the upgrade did not complete — reinstall.
- **Notifications or sound missing:** delivery depends on OS settings (Windows Focus Assist/notification settings, Linux desktop notification settings). This is unchanged from the beta; see [README.md](README.md#current-app).

## References

- [development guide](docs/development.md) — install, run, and build instructions.
- [Backlog](docs/implementation/backlog.md) — what is implemented, deferred, and still needs acceptance.
- [Platform checklist](docs/implementation/platform-validation.md) — installed-app verification per OS.
