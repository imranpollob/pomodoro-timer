import json
import os
import sys
from pathlib import Path
from datetime import datetime, date

if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "pomodoro-timer"
else:
    CONFIG_DIR = Path.home() / ".config" / "pomodoro-timer"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SETTINGS = {
    "work_time": 25,
    "short_break": 5,
    "long_break": 15,
    "long_break_interval": 4,
    "sound_enabled": True,
    "unfocus_transparency": 0.8,
    "label_font_size": 42,
    "timer_mode": "Pomodoro",
    "window_width": 290,
    "window_height": 290,
    "maximized_window_width": 240,
    "maximized_window_height": 80,
    "is_maximized_state": False,
    "todo_sidebar_visible": False,
    "todo_sidebar_width": 250,
}


class StorageManager:
    def __init__(self, settings_file=None, todos_file=None, history_file=None):
        self.settings_file = Path(settings_file) if settings_file else CONFIG_DIR / "settings.json"
        self.todos_file = Path(todos_file) if todos_file else CONFIG_DIR / "todos.json"
        self.history_file = Path(history_file) if history_file else CONFIG_DIR / "history.json"
        
        self.settings = DEFAULT_SETTINGS.copy()
        self.todos = []
        
        self.load_settings()
        self.load_todos()

    def load_settings(self):
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_todos(self):
        if self.todos_file.exists():
            try:
                with open(self.todos_file, "r") as f:
                    self.todos = json.load(f)
            except Exception as e:
                print(f"Error loading todos: {e}")
                self.todos = []
        else:
            self.todos = []

    def save_todos(self):
        try:
            with open(self.todos_file, "w") as f:
                json.dump(self.todos, f, indent=4)
        except Exception as e:
            print(f"Error saving todos: {e}")

    def load_history(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def log_session(self, session_type, duration_seconds):
        if duration_seconds < 10:
            return
        history = self.load_history()
        history.append({
            "date": date.today().isoformat(),
            "type": session_type,
            "duration_seconds": int(duration_seconds),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        try:
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            print(f"Error saving history: {e}")

    def reset_today_stats(self):
        today = date.today().isoformat()
        history = self.load_history()
        new_history = [s for s in history if s.get("date") != today]
        try:
            with open(self.history_file, "w") as f:
                json.dump(new_history, f, indent=4)
            return True
        except Exception as e:
            print(f"Error resetting history: {e}")
            return False
