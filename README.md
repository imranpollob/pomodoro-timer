# Pomodoro Timer
A simple pomodoro timer featuring useful functionalities.

## Features
- Customizable Pomodoro cycles: Work, Short Break, Long Break
- Endless Timer/Stopwatch mode for custom focus sessions
- Daily Report with today's focus statistics and a statistics reset option in settings
- Audio notifications on session completion
- Adjustable font size for a customizable desktop clock feel
- Always on top, with transparency option when unfocused
- Timer maximize and minimize option for minimal distraction
- Collapsible & Resizable Todo management sidebar
- Remembers and restores custom window dimensions

## Screenshots

![screen-1](images/main.png)

![screen-1](images/stopwatch.png)

![screen-2](images/todos.png)

![settings](images/settings.png)

![report](images/report.png)

## Setup

We use `uv` for dependency management. Install it from [here](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

## Running

### Run directly (all platforms)
```bash
uv run pomodoro.py
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

## Configuration
Settings (`settings.json`) and session statistics (`history.json`) are stored in the user profile directory:
- **Windows**: `%APPDATA%\pomodoro-timer\` (e.g., `C:\Users\<username>\AppData\Roaming\pomodoro-timer\`)
- **Linux**: `~/.config/pomodoro-timer/`

## Running tests
```bash
uv run pytest
```

#### Icon attribution
<a href="https://www.flaticon.com/free-icons/timer" title="timer icons">Timer icons created by Freepik - Flaticon</a>
