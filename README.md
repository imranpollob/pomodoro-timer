# Pomodoro Timer
A desktop Pomodoro timer and stopwatch app built with Python and Tkinter (ttkbootstrap). It includes todo management, daily stats, sound alerts, and customizable window sizes and transparency.

## Features
- Customizable Pomodoro cycles: Work, Short Break, Long Break
- Endless Timer/Stopwatch mode for custom focus sessions
- Todo management in a separate window with add, edit, delete, and completion tracking
- Daily Report with today's focus statistics and a statistics reset option in settings
- Audio notifications on session completion
- Adjustable font size for a customizable desktop clock feel
- Always on top, with transparency option when unfocused (transparency on macOS in progress)
- Timer maximize and minimize option for minimal distraction
- Remembers and restores custom window dimensions
- Google Drive sync for settings, todos, and session history across devices

## Screenshots

![main](images/main.png)

![maximized](images/maximized.png)

![stopwatch](images/stopwatch.png)

![todos](images/todos.png)

![settings](images/settings.png)

![report](images/report.png)

## Setup

We use `uv` for dependency management. Install it from [here](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

## Running

### Run directly (all platforms)
```bash
uv run src/pomodoro.py
```

### Linux — Install as a desktop app (.deb)
Build and install a native `.deb` package for full desktop integration:

```bash
bash build_deb.sh
sudo dpkg -i pomodoro-timer_amd64.deb
```

### Windows — Build standalone executable
```bash
uv run pyinstaller --clean --noconfirm pomodoro.spec
```
Then run `dist/pomodoro.exe`.

### macOS — Build standalone app bundle
```bash
uv run pyinstaller --clean --noconfirm pomodoro.spec
```
Then run `open dist/Pomodoro.app` (or double-click the bundle in Finder).

## Configuration
Settings (`settings.json`) and session statistics (`history.json`) are stored in the user profile directory:
- **Windows**: `%APPDATA%\pomodoro-timer\` (e.g., `C:\Users\<username>\AppData\Roaming\pomodoro-timer\`)
- **macOS & Linux**: `~/.config/pomodoro-timer/`

## Google Drive Sync

Sync your settings, todos, and session history across multiple devices using Google Drive. Data is stored locally first; Google Drive acts as a secondary backup that automatically syncs in the background.

### For Users

1. Open the app → **Settings** → **Google Drive Sync** → Click **Connect**
2. A browser window will open — sign in with your Google account
3. Review the permissions and click **Allow**
4. The status will show **Connected** — sync is now active

### Managing Sync

- **Sync Now**: Force an immediate upload to Google Drive
- **Disconnect**: Remove Google Drive credentials and stop syncing (local data is preserved)

### How It Works

- **Local-first**: All reads and writes go to local JSON files first
- **Auto-sync**: Changes are automatically uploaded to Google Drive in the background
- **Multi-device**: Data from multiple devices is intelligently merged (settings override by newest, todos merged by ID, history deduplicated by timestamp)
- **Offline-capable**: The app works fully without an internet connection; sync resumes when online

## Developer Setup — Google Drive API

These instructions are for the app developer to configure Google Drive sync. End users do not need to follow these steps.

### One-Time Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services** → **Library** → Search for **Google Drive API** → Click **Enable**
4. Go to **APIs & Services** → **OAuth consent screen**
   - Choose **External** user type
   - Fill in the required app information
   - Add the scope `https://www.googleapis.com/auth/drive.file`
   - Add your Google account as a test user
5. Go to **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **OAuth client ID**
7. Choose **Desktop app** as the application type
8. Click **Create** — you'll receive a **Client ID** and **Client Secret**

### Embedding Credentials

Open `src/drive_sync.py` and replace the placeholders in `EMBEDDED_CLIENT_CONFIG`:

```python
EMBEDDED_CLIENT_CONFIG = {
    "installed": {
        "client_id": "YOUR_CLIENT_ID_HERE",
        "client_secret": "YOUR_CLIENT_SECRET_HERE",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}
```

### Publishing for Public Use

**Testing mode** allows up to 100 users. To support unlimited users:

1. Complete the Google Cloud verification process for your OAuth app
2. Submit your app for review in the OAuth consent screen settings
3. Once verified, remove the test user restriction

## Running tests
```bash
uv run pytest
```

#### Icon attribution
<a href="https://www.flaticon.com/free-icons/timer" title="timer icons">Timer icons created by Freepik - Flaticon</a>
