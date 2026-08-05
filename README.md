# Pomodoro Timer
A desktop Pomodoro timer and stopwatch app that always stays on top. It includes todo management, daily stats, syncing, and more.



## Quick Start

### Download
Prebuilt executables for Windows, macOS, and Linux are published on the [Releases page](../../releases).

### Command Line
Requires the `uv` package manager. Run:
```bash
uv run src/pomodoro.py
```



## Features
- Customizable Pomodoro cycles: Work, Short Break, Long Break
- Endless Stopwatch mode
- Todo management
- Optional todo sync across devices via [JSONBin](https://jsonbin.io)
- Daily Report
- Adjustable font size
- Always on top, with transparency option (transparency support on macOS is in progress)
- Remembers and restores custom window dimensions



## Screenshots

![main](images/main.png)

![stopwatch](images/stopwatch.png)

![maximized](images/maximized.png)

![todos](images/todos.png)

![settings](images/settings.png)

![report](images/report.png)




## Setup

We use `uv` for dependency management. Install it from [here](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

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



## Todo Sync (JSONBin)
Todos can be synced across devices using [JSONBin](https://jsonbin.io) as free cloud storage. 

### 1. Create a bin
JSONBin doesn't allow creating an empty bin, so seed it with a sample todo.
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

1. Go to **API Keys** and click **Create Access Key**.
2. Give it a name (e.g. `pomodoro-todos`)
3. Grant **Read** and **Update** permissions
4. Copy the generated **X-Access-Key** value, not the shorter 'Access Key ID'.

### 3. Configure the app
1. Open **Settings** in the app.
2. Under **JSONBin Sync**, paste the **Bin ID** from step 1 and the **Access Key** from step 2.
3. Click **Save Settings**.

### 4. Sync
Open the **Todos** window — it syncs automatically. 



## Contribution Guidelines 

### Versioning

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

### Configuration Files
Settings (`settings.json`) and session statistics (`history.json`) are stored in the user profile directory:
- **Windows**: `%APPDATA%\pomodoro-timer\` (e.g., `C:\Users\<username>\AppData\Roaming\pomodoro-timer\`)
- **macOS & Linux**: `~/.config/pomodoro-timer/`

### Running tests
```bash
uv run pytest
```


## Icon attribution
<a href="https://www.flaticon.com/free-icons/timer" title="timer icons">Timer icons created by Freepik - Flaticon</a>
