# Pomodoro Timer
A desktop Pomodoro timer and stopwatch app built with Python and Tkinter (ttkbootstrap). It includes todo management, daily stats, sound alerts, and customizable window sizes and transparency.

## Download

Prebuilt executables for Windows, macOS, and Linux are published on the [Releases page](../../releases) for every tagged version.

## Features
- Customizable Pomodoro cycles: Work, Short Break, Long Break
- Endless Timer/Stopwatch mode for custom focus sessions
- Todo management in a separate window with add, edit, delete, and completion tracking
- Optional todo sync across devices via [JSONBin](https://jsonbin.io)
- Daily Report with today's focus statistics and a statistics reset option in settings
- Audio notifications on session completion
- Adjustable font size for a customizable desktop clock feel
- Always on top, with transparency option when unfocused (transparency on macOS in progress)
- Timer maximize and minimize option for minimal distraction
- Remembers and restores custom window dimensions

## Screenshots

![main](images/main.png)

![maximized](images/maximized.png)

![stopwatch](images/stopwatch.png)

![todos](images/todos.png)

![settings](images/settings.png)

![report](images/report.png)

## Setup

We use `uv` for dependency management. Install it from [here](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

## Versioning

The app version is defined once in `pyproject.toml`. Platform builds read that value for the Settings window, the Linux `.deb` package, the Windows installer, and the macOS app bundle.

Use `uv` to bump the version. This updates both `pyproject.toml` and the project entry in `uv.lock`; do not edit `uv.lock` manually:

```bash
uv version --bump patch
```

To publish a release, validate and commit the version change before creating the matching tag:

```bash
VERSION=$(uv version --short)

uv lock --check
uv run pytest -q

git add pyproject.toml uv.lock
git commit -m "Bump version to ${VERSION}"

git tag "v${VERSION}"
git push origin HEAD
git push origin "v${VERSION}"
```

Pushing the tag triggers the `Release` GitHub Actions workflow, which builds Linux, Windows, and macOS packages and attaches them to a new GitHub Release. Use `uv version --bump minor` or `uv version --bump major` instead when appropriate.

## Running

### Run directly (all platforms)
```bash
uv run src/pomodoro.py
```

### Linux — Install as a desktop app (.deb)
Build and install a native `.deb` package for full desktop integration:

```bash
./build_deb.sh
sudo dpkg -i pomodoro-timer_amd64.deb
```

### Windows — Build standalone executable
```bash
uv run pyinstaller --clean --noconfirm pomodoro.spec
```
Then run `dist/pomodoro.exe`.

### Windows — Build installer (.exe)
Creates a proper Windows installer with Start Menu shortcut and Add/Remove Programs entry.
Requires [NSIS](https://nsis.sourceforge.io/Download) installed and `makensis` in your PATH.

```bash
.\build_windows.bat
```
Then run `dist/pomodoro-timer-setup.exe` to install.

### macOS — Build standalone app bundle
```bash
uv run pyinstaller --clean --noconfirm pomodoro.spec
```
Then run `open dist/Pomodoro.app` (or double-click the bundle in Finder).

## Configuration
Settings (`settings.json`) and session statistics (`history.json`) are stored in the user profile directory:
- **Windows**: `%APPDATA%\pomodoro-timer\` (e.g., `C:\Users\<username>\AppData\Roaming\pomodoro-timer\`)
- **macOS & Linux**: `~/.config/pomodoro-timer/`

## Todo Sync (JSONBin)
Todos can be synced across devices using [JSONBin](https://jsonbin.io) as free cloud storage. The Sync button in the Todos window pulls the remote list, merges it with your local todos (the most recently edited version of each item wins), pushes the merged result back, and saves it locally.

### 1. Create a bin
JSONBin doesn't allow creating an empty bin, so seed it with a sample todo — the app will overwrite it on the first sync anyway:

1. Sign up / log in at [jsonbin.io](https://jsonbin.io).
2. Go to **Bins** and click **Create a Bin**.
3. Paste the following as the bin content and save:
   ```json
   [
       {
           "id": 1,
           "text": "Sample todo",
           "done": false
       }
   ]
   ```
4. Copy the **Bin ID** shown for that bin — you'll need it in step 3.

### 2. Create a scoped access key
Don't use your account's **X-Master-Key** in the app — it grants full access to every bin on your account. Instead create a key scoped to just this bin:

1. Go to **API Keys** and click **Create Access Key**.
2. Give it a name (e.g. `pomodoro-todos`) and restrict it to the bin you created above.
3. Grant **Read** and **Update** permissions — that's all the app uses (`GET .../latest` and `PUT ...`); Create and Delete aren't needed.
4. Copy the generated **X-Access-Key** value — this is a long string starting with `$2a$...`, not the shorter "Access Key ID".

### 3. Configure the app
1. Open **Settings** in the app.
2. Under **JSONBin Sync**, paste the **Bin ID** from step 1 and the **Access Key** from step 2.
3. Click **Save Settings**.

### 4. Sync
Open the **Todos** window and click **Sync**. The first sync will pull in the "Sample todo" from step 1 — just delete it once, and that deletion will sync to every device from then on. Repeat on each device using the same Bin ID and Access Key to keep todos in sync.

**Note:** merging is based on an `updated_at` timestamp per todo, not real-time collaboration — for the same todo edited on two devices before either syncs, the most recently edited (or deleted) version wins.

Deleted todos are kept as hidden "tombstones" for 7 days after deletion so the deletion has time to reach every device on its next sync, then they're purged automatically. If a device goes more than 7 days without syncing, a todo it deleted in that window could reappear.

## Running tests
```bash
uv run pytest
```

#### Icon attribution
<a href="https://www.flaticon.com/free-icons/timer" title="timer icons">Timer icons created by Freepik - Flaticon</a>
