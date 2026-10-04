"""Atomic, validated legacy JSON storage with explicit recovery."""
import json
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from datetime import datetime, date
from settings import DEFAULT_SETTINGS, validate_settings
from sync import validate_todos

if os.environ.get("POMODORO_DATA_DIR"):
    CONFIG_DIR = Path(os.environ["POMODORO_DATA_DIR"]).expanduser().resolve()
elif sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "pomodoro-timer"
else:
    CONFIG_DIR = Path.home() / ".config" / "pomodoro-timer"

class StorageError(Exception):
    """A read/write failed; callers must not report success or discard drafts."""

def validate_history(items):
    if not isinstance(items, list):
        raise ValueError("History must be a JSON list.")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each history record must be an object.")
        date.fromisoformat(item.get("date", ""))
        if item.get("type") not in ("Work", "Stopwatch", "Short Break", "Long Break"):
            raise ValueError("Unknown session type.")
        duration = item.get("duration_seconds")
        if type(duration) is not int or duration < 0:
            raise ValueError("Session duration must be a non-negative integer.")
        if "timestamp" in item:
            datetime.fromisoformat(item["timestamp"])
    return items

def atomic_write(path, payload):
    """Flush a same-directory temporary file before replacing the destination."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

class StorageManager:
    def __init__(self, settings_file=None, todos_file=None, history_file=None):
        self.settings_file = Path(settings_file) if settings_file else CONFIG_DIR / "settings.json"
        self.todos_file = Path(todos_file) if todos_file else CONFIG_DIR / "todos.json"
        self.history_file = Path(history_file) if history_file else CONFIG_DIR / "history.json"
        self.settings = DEFAULT_SETTINGS.copy()
        self.todos = []
        self.errors = {}
        self.preserved_files = {}
        self._blocked = set()
        self._lock = threading.RLock()
        self.load_settings()
        self.load_todos()
        try:
            self.load_history()
        except StorageError:
            pass

    def _path(self, kind):
        return getattr(self, f"{kind}_file")

    @staticmethod
    def _validate(kind, value):
        if kind == "settings":
            return validate_settings(value)
        if kind == "todos":
            return validate_todos(value)
        return validate_history(value)

    @classmethod
    def _decode(cls, kind, payload):
        def invalid_constant(value):
            raise ValueError("Non-finite JSON values are not supported.")
        return cls._validate(kind, json.loads(payload.decode("utf-8"), parse_constant=invalid_constant))

    def _preserve(self, kind):
        path = self._path(kind)
        payload = path.read_bytes()
        previous = self.preserved_files.get(kind)
        if previous is not None and previous.exists() and previous.read_bytes() == payload:
            return
        preserved = path.with_name(f"{path.name}.corrupt-{uuid.uuid4().hex}")
        atomic_write(preserved, payload)
        self.preserved_files[kind] = preserved

    def _read(self, kind):
        path = self._path(kind)
        try:
            value = self._decode(kind, path.read_bytes())
        except FileNotFoundError:
            # A missing file is fresh data only if no unreadable original was seen.
            if kind in self._blocked:
                raise StorageError(f"{path.name} needs explicit recovery.")
            self.errors.pop(kind, None)
            return DEFAULT_SETTINGS.copy() if kind == "settings" else []
        except (OSError, ValueError, TypeError) as exc:
            self._blocked.add(kind)
            self.errors[kind] = f"Could not read {path.name}: {exc}"
            try:
                self._preserve(kind)
            except OSError:
                pass  # Original remains untouched even when a copy cannot be made.
            raise StorageError(self.errors[kind]) from exc
        self.errors.pop(kind, None)
        self._blocked.discard(kind)
        return value

    def _write(self, kind, value, *, recovery=False):
        path = self._path(kind)
        try:
            value = self._validate(kind, value)
            payload = json.dumps(value, indent=4, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if not recovery:
                self._read(kind)  # Never replace malformed input with a fresh list.
            if path.exists():
                original = path.read_bytes()
                try:
                    self._decode(kind, original)
                except (ValueError, TypeError):
                    if not recovery:
                        raise StorageError(f"{path.name} needs explicit recovery.")
                    self._preserve(kind)
                else:
                    atomic_write(path.with_name(path.name + ".bak"), original)
            atomic_write(path, payload)
        except (OSError, ValueError, TypeError) as exc:
            self.errors[kind] = f"Could not save {path.name}: {exc}"
            raise StorageError(self.errors[kind]) from exc
        self.errors.pop(kind, None)
        self._blocked.discard(kind)
        return value

    def load_settings(self):
        with self._lock:
            try:
                values = self._read("settings")
            except StorageError:
                return
            self.settings.clear()
            self.settings.update(values)

    def save_settings(self, candidate=None):
        with self._lock:
            values = self._write("settings", self.settings if candidate is None else candidate)
            self.settings.clear()
            self.settings.update(values)

    def load_todos(self):
        with self._lock:
            try:
                self.todos = self._read("todos")
            except StorageError:
                return

    def save_todos(self, candidate=None):
        with self._lock:
            self.todos = self._write("todos", self.todos if candidate is None else candidate)

    def load_history(self):
        with self._lock:
            return self._read("history")

    def log_session(self, session_type, duration_seconds):
        if duration_seconds < 10:
            return  # Retain the 0.x short-session policy until the new core.
        with self._lock:
            history = self._read("history")
            history.append({
                "date": date.today().isoformat(), "type": session_type,
                "duration_seconds": int(duration_seconds),
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            self._write("history", history)

    def reset_today_stats(self):
        with self._lock:
            try:
                today = date.today().isoformat()
                history = self._read("history")
                self._write("history", [s for s in history if s["date"] != today])
                return True
            except StorageError:
                return False

    def restore_backup(self, kind, backup_file=None):
        if kind not in ("settings", "todos", "history"):
            raise ValueError("Choose settings, todos, or history.")
        path = self._path(kind)
        backup = Path(backup_file) if backup_file else path.with_name(path.name + ".bak")
        with self._lock:
            try:
                values = self._decode(kind, backup.read_bytes())
            except (OSError, ValueError, TypeError) as exc:
                raise StorageError(f"The selected {kind} backup is not valid.") from exc
            self._write(kind, values, recovery=True)
            if kind == "settings":
                self.settings.clear()
                self.settings.update(values)
            elif kind == "todos":
                self.todos = values
