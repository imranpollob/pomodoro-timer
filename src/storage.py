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
}


class StorageManager:
    """Manages application settings, todos, and history storage."""

    def __init__(self, settings_file=None, todos_file=None, history_file=None):
        self.settings_file = Path(settings_file) if settings_file else CONFIG_DIR / "settings.json"
        self.todos_file = Path(todos_file) if todos_file else CONFIG_DIR / "todos.json"
        self.history_file = Path(history_file) if history_file else CONFIG_DIR / "history.json"
        
        self.settings = DEFAULT_SETTINGS.copy()
        self.todos = []
        self._drive_sync = None
        
        self.load_settings()
        self.load_todos()

    def set_drive_sync(self, drive_sync):
        """Set the Google Drive sync manager."""
        self._drive_sync = drive_sync

    def _trigger_sync(self):
        """Trigger a background sync if drive sync is connected."""
        if self._drive_sync and self._drive_sync.is_connected:
            data = self.get_all_data()
            self._drive_sync.queue_sync(data)

    def load_settings(self):
        """Loads settings from the settings file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        """Saves current settings to the settings file."""
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
            self._trigger_sync()
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_todos(self):
        """Loads the todo list from the todos file."""
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
        """Saves the current todo list to the todos file."""
        try:
            with open(self.todos_file, "w") as f:
                json.dump(self.todos, f, indent=4)
            self._trigger_sync()
        except Exception as e:
            print(f"Error saving todos: {e}")

    def load_history(self):
        """Loads the session history from the history file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def log_session(self, session_type, duration_seconds):
        """Logs a completed session to the history."""
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
            self._trigger_sync()
        except Exception as e:
            print(f"Error saving history: {e}")

    def reset_today_stats(self):
        """Resets the statistics for the current day."""
        today = date.today().isoformat()
        history = self.load_history()
        new_history = [s for s in history if s.get("date") != today]
        try:
            with open(self.history_file, "w") as f:
                json.dump(new_history, f, indent=4)
            self._trigger_sync()
            return True
        except Exception as e:
            print(f"Error resetting history: {e}")
            return False

    def get_all_data(self):
        """Consolidate all data into a single dict for sync."""
        return {
            "settings": self.settings.copy(),
            "todos": list(self.todos),
            "history": self.load_history(),
            "metadata": {
                "last_modified": datetime.now().isoformat(),
                "device_id": "",
                "sync_version": 0,
            },
        }

    def load_all_data(self, data):
        """Restore settings, todos, and history from consolidated data."""
        if not data:
            return False

        try:
            if "settings" in data:
                self.settings.update(data["settings"])
                with open(self.settings_file, "w") as f:
                    json.dump(self.settings, f, indent=4)

            if "todos" in data:
                self.todos = data["todos"]
                with open(self.todos_file, "w") as f:
                    json.dump(self.todos, f, indent=4)

            if "history" in data:
                with open(self.history_file, "w") as f:
                    json.dump(data["history"], f, indent=4)

            return True
        except Exception as e:
            print(f"Error loading all data: {e}")
            return False
