# Pomodoro Timer
A simple pomodoro timer featuring useful functionalities. 

### Features
- Classic Pomodoro cycles: Work (25m), Short Break (5m), Long Break (15m)
- Automatic break tracking (Long break after 4 work sessions)
- Audio notifications on session completion
- Dedicated settings window with persistent preferences (`settings.json`)
- Simplest interface
- Always stays on top of all windows
- Includes basic transparency settings, applies on window unfocus
- Font size can be modified 

### Setup

We use `uv` for dependency management. If you don't have it, install it from [here](https://docs.astral.sh/uv/getting-started/installation/).

## Usage 
Just use the `pomodoro.exe` file for windows. It's inside of the `dist` folder. No installation is required.

Otherwise, run the `pomodoro.py` file using `uv`:
```py
uv run pomodoro.py
```

## Screenshots
Application:

![App](app.png)

Settings:

![Settings](settings.png)


## Making an installer
```bash
uv run pyinstaller --onefile --windowed --icon=stopwatch.ico pomodoro.py
```

#### Icon attribution
<a href="https://www.flaticon.com/free-icons/timer" title="timer icons">Timer icons created by Freepik - Flaticon</a>
