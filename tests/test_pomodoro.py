import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pomodoro
from storage import StorageManager
from pomodoro import PomodoroApp

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


class FakeWidget:
    def __init__(self):
        self.config_calls = []
        self.pack_calls = []
        self.pack_forget_calls = 0

    def config(self, **kwargs):
        self.config_calls.append(kwargs)

    configure = config

    def cget(self, key):
        for call in reversed(self.config_calls):
            if key in call:
                return call[key]
        return ""

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def pack_forget(self):
        self.pack_forget_calls += 1

    def bind(self, event, callback):
        pass

    def destroy(self):
        pass

    def update_idletasks(self):
        pass

    def itemconfig(self, *args, **kwargs):
        pass

    def set_text(self, text):
        self.config(text=text)


class FakeChild:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs)

    def destroy(self):
        pass


class FakeFrame(FakeWidget):
    def __init__(self, child_count=2):
        super().__init__()
        self.children = [FakeChild() for _ in range(child_count)]

    def winfo_children(self):
        return self.children


class FakeRoot:
    def __init__(self, current_geom="290x290+100+100"):
        self.after_calls = []
        self.bell_calls = 0
        self.attribute_calls = []
        self.wm_attribute_calls = []
        self.config_calls = []
        self.geometry_calls = []
        self.iconbitmap_calls = []
        self.iconphoto_calls = []
        self.current_geom = current_geom

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))

    def bell(self):
        self.bell_calls += 1

    def attributes(self, *args):
        self.attribute_calls.append(args)

    def wm_attributes(self, *args):
        self.wm_attribute_calls.append(args)

    def config(self, **kwargs):
        self.config_calls.append(kwargs)

    configure = config

    def geometry(self, geom_str=None):
        if geom_str is not None:
            self.geometry_calls.append(geom_str)
            self.current_geom = geom_str
            return geom_str
        return self.current_geom

    def update_idletasks(self):
        pass

    def iconbitmap(self, icon_path):
        self.iconbitmap_calls.append(icon_path)

    def iconphoto(self, *args):
        self.iconphoto_calls.append(args)


class FakeEntry(FakeWidget):
    def __init__(self, initial_text=""):
        super().__init__()
        self.text = initial_text

    def get(self):
        return self.text

    def delete(self, start, end):
        self.text = ""


def get_test_app(tmp_path):
    storage = StorageManager(
        settings_file=tmp_path / "settings.json",
        todos_file=tmp_path / "todos.json",
        history_file=tmp_path / "history.json"
    )
    storage.settings = DEFAULT_SETTINGS.copy()

    app = PomodoroApp(storage, headless=True)
    app.root = FakeRoot()
    app.mode_label = FakeWidget()
    app.timer_label = FakeWidget()
    app.timer_frame = FakeWidget()
    app.start_btn = FakeWidget()
    app.stop_btn = FakeWidget()
    app.skip_btn = FakeWidget()
    app.maximize_btn = FakeWidget()
    app.minimize_btn = FakeWidget()
    app.menu_bar = FakeWidget()
    app.mode_frame = FakeFrame()
    app.todo_entry = FakeEntry()
    app.todo_list_frame = FakeFrame()
    app.todo_list_canvas = FakeWidget()

    return app


def test_load_settings_updates_known_values(tmp_path):
    settings_file = tmp_path / "settings.json"
    with open(settings_file, "w") as f:
        json.dump({"work_time": 30, "timer_mode": "Stopwatch"}, f)

    storage = StorageManager(settings_file=settings_file)
    assert storage.settings["work_time"] == 30
    assert storage.settings["timer_mode"] == "Stopwatch"
    assert storage.settings["short_break"] == 5


def test_save_settings_writes_json_file(tmp_path):
    settings_file = tmp_path / "settings.json"
    storage = StorageManager(settings_file=settings_file)
    storage.settings["long_break_interval"] = 6
    storage.save_settings()

    saved = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved["long_break_interval"] == 6
    assert saved["timer_mode"] == "Pomodoro"


def test_get_resource_path_uses_meipass_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(pomodoro.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pomodoro.sys, "_MEIPASS", str(tmp_path), raising=False)

    icon_path = pomodoro.get_resource_path("stopwatch.ico")
    assert icon_path == str(tmp_path / "stopwatch.ico")


def test_apply_window_icon_uses_ico_on_windows(tmp_path, monkeypatch):
    ico_path = tmp_path / "stopwatch.ico"
    ico_path.write_bytes(b"fake")

    window = FakeRoot()
    monkeypatch.setattr(pomodoro.sys, "platform", "win32")
    monkeypatch.setattr(pomodoro, "get_resource_path", lambda filename: str(ico_path) if filename == "stopwatch.ico" else str(tmp_path / filename))
    monkeypatch.setattr(pomodoro.os.path, "exists", lambda path: path == str(ico_path))

    def fail_photo(*args, **kwargs):
        raise AssertionError("PNG icon path should not be used on Windows")

    monkeypatch.setattr(pomodoro.tk, "PhotoImage", fail_photo)

    pomodoro.apply_window_icon(window)

    assert window.iconbitmap_calls == [str(ico_path)]
    assert window.iconphoto_calls == []


def test_set_mode_work_updates_labels_and_remaining_time(tmp_path):
    app = get_test_app(tmp_path)
    app.completed_pomodoros = 1
    app.set_mode("Work")

    assert app.current_mode == "Work"
    assert app.pomodoro_time == 25 * 60
    assert app.mode_label.config_calls[-1] == {
        "text": "Work 2/4",
        "bootstyle": "primary",
    }
    assert app.timer_label.config_calls[-1] == {"text": "25:00"}


def test_set_mode_stopwatch_resets_to_zero(tmp_path):
    app = get_test_app(tmp_path)
    app.pomodoro_time = 99
    app.set_mode("Stopwatch")

    assert app.current_mode == "Stopwatch"
    assert app.pomodoro_time == 0
    assert app.mode_label.config_calls[-1] == {
        "text": "Stopwatch",
        "bootstyle": "secondary",
    }
    assert app.timer_label.config_calls[-1] == {"text": "00:00"}


def test_update_timer_countdown_schedules_next_tick(tmp_path):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Work"
    app.pomodoro_time = 120

    app.update_timer()

    assert app.timer_label.config_calls[-1] == {"text": "02:00"}
    assert app.pomodoro_time == 119
    assert app.root.after_calls == [(1000, app.update_timer)]


def test_update_timer_stopwatch_increments_and_schedules_next_tick(tmp_path):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Stopwatch"
    app.pomodoro_time = 5

    app.update_timer()

    assert app.timer_label.config_calls[-1] == {"text": "00:05"}
    assert app.pomodoro_time == 6
    assert app.root.after_calls == [(1000, app.update_timer)]


def test_update_timer_work_completion_moves_to_short_break(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Work"
    app.pomodoro_time = 0
    monkeypatch.setattr(pomodoro.sys, "platform", "win32")

    modes = []
    monkeypatch.setattr(app, "set_mode", lambda mode: modes.append(mode))

    app.update_timer()

    assert app.timer_running is False
    assert app.completed_pomodoros == 1
    assert modes == ["Short Break"]
    assert app.root.bell_calls == 1
    assert app.start_btn.config_calls[-1] == {
        "text": "Start",
        "command": app.start_pomodoro,
        "bootstyle": "primary",
    }
    assert all(
        child.states[-1] == {"state": "normal"}
        for child in app.mode_frame.children
    )


def test_update_timer_work_completion_moves_to_long_break(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Work"
    app.pomodoro_time = 0
    app.completed_pomodoros = 3

    modes = []
    monkeypatch.setattr(app, "set_mode", lambda mode: modes.append(mode))

    app.update_timer()

    assert app.completed_pomodoros == 4
    assert modes == ["Long Break"]


def test_update_timer_long_break_completion_resets_cycle(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Long Break"
    app.pomodoro_time = 0
    app.completed_pomodoros = 4

    modes = []
    monkeypatch.setattr(app, "set_mode", lambda mode: modes.append(mode))

    app.update_timer()

    assert app.completed_pomodoros == 0
    assert modes == ["Work"]


def test_stop_pomodoro_logs_work_session(tmp_path):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Work"
    app.settings["work_time"] = 25
    app.pomodoro_time = 15 * 60

    app.stop_pomodoro()

    assert app.timer_running is False
    history = app.storage.load_history()
    assert len(history) == 1
    assert history[0]["type"] == "Work"
    assert history[0]["duration_seconds"] == 10 * 60


def test_stop_pomodoro_logs_stopwatch_session(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Stopwatch"

    from datetime import datetime, timedelta
    start_time = datetime.now()
    app.stopwatch_start_time = start_time

    class MockDateTime:
        @classmethod
        def now(cls):
            return start_time + timedelta(seconds=30)
    monkeypatch.setattr(pomodoro, "datetime", MockDateTime)

    app.stop_pomodoro()

    assert app.timer_running is False
    history = app.storage.load_history()
    assert len(history) == 1
    assert history[0]["type"] == "Stopwatch"
    assert history[0]["duration_seconds"] == 30


def test_stop_pomodoro_logs_stopwatch_session_with_pauses(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Stopwatch"

    from datetime import datetime, timedelta
    start_time = datetime.now()
    app.stopwatch_start_time = start_time

    current_time = start_time + timedelta(seconds=20)

    class MockDateTime1:
        @classmethod
        def now(cls):
            return current_time

    monkeypatch.setattr(pomodoro, "datetime", MockDateTime1)
    app.pause_pomodoro()

    assert app.stopwatch_accumulated_seconds == 20
    assert app.stopwatch_start_time is None

    app.continue_pomodoro()
    assert app.stopwatch_start_time == current_time

    current_time = current_time + timedelta(seconds=15)

    class MockDateTime2:
        @classmethod
        def now(cls):
            return current_time

    monkeypatch.setattr(pomodoro, "datetime", MockDateTime2)
    app.stop_pomodoro()

    assert app.timer_running is False
    history = app.storage.load_history()
    assert len(history) == 1
    assert history[0]["type"] == "Stopwatch"
    assert history[0]["duration_seconds"] == 35


def test_skip_break_moves_to_work_mode(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.current_mode = "Short Break"
    app.timer_running = True

    modes = []
    monkeypatch.setattr(app, "set_mode", lambda mode: modes.append(mode))

    app.skip_break()

    assert app.timer_running is False
    assert app.stop_btn.pack_forget_calls == 1
    assert app.skip_btn.pack_forget_calls == 1
    assert modes == ["Work"]


def test_set_mode_break_packs_skip_btn(tmp_path):
    app = get_test_app(tmp_path)
    app.set_mode("Short Break")
    assert app.skip_btn.pack_calls[-1] == {"pady": 4}


def test_start_pomodoro_in_break_packs_skip_btn(tmp_path):
    app = get_test_app(tmp_path)
    app.current_mode = "Short Break"
    app.start_pomodoro()
    assert app.skip_btn.pack_calls[-1] == {"pady": 4}


def test_set_mode_break_hides_stop_btn(tmp_path):
    app = get_test_app(tmp_path)
    app.set_mode("Short Break")
    assert app.stop_btn.pack_forget_calls == 1


def test_log_session_ignores_short_sessions(tmp_path):
    storage = StorageManager(history_file=tmp_path / "history.json")
    storage.log_session("Work", 5)
    assert not (tmp_path / "history.json").exists()


def test_log_session_appends_to_history(tmp_path):
    storage = StorageManager(history_file=tmp_path / "history.json")
    storage.log_session("Work", 15 * 60)
    storage.log_session("Stopwatch", 30)

    history = storage.load_history()
    assert len(history) == 2
    assert history[0]["type"] == "Work"
    assert history[1]["type"] == "Stopwatch"


def test_maximize_timer_hides_controls(tmp_path):
    app = get_test_app(tmp_path)
    app.maximize_timer()

    assert app.is_maximized is True
    assert app.mode_frame.pack_forget_calls == 1
    assert app.mode_label.pack_forget_calls == 1
    assert app.start_btn.pack_forget_calls == 1
    assert app.maximize_btn.pack_forget_calls == 1

    assert app.root.geometry_calls[-1] == "240x80"

    assert app.timer_frame.pack_forget_calls == 1
    assert app.timer_frame.pack_calls[-1] == {"pady": (15, 5)}
    assert app.minimize_btn.pack_calls[-1] == {"side": "left", "padx": (5, 0), "anchor": "center"}


def test_minimize_timer_restores_controls_when_running(tmp_path):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.minimize_timer()

    assert app.is_maximized is False
    assert app.minimize_btn.pack_forget_calls == 1
    assert app.root.config_calls[-1] == {"menu": app.menu_bar}
    assert app.root.geometry_calls[-1] == "290x290"

    assert app.timer_frame.pack_forget_calls == 1
    assert app.timer_frame.pack_calls[-1] == {"pady": 0}

    assert len(app.mode_frame.pack_calls) == 1
    assert len(app.mode_label.pack_calls) == 1
    assert len(app.start_btn.pack_calls) == 1
    assert app.maximize_btn.pack_calls[-1] == {"side": "left", "padx": (5, 0), "anchor": "center"}


def test_minimize_timer_restores_controls_when_completed(tmp_path):
    app = get_test_app(tmp_path)
    app.timer_running = False
    app.minimize_timer()

    assert app.is_maximized is False
    assert app.minimize_btn.pack_forget_calls == 1
    assert app.root.config_calls[-1] == {"menu": app.menu_bar}
    assert app.root.geometry_calls[-1] == "290x290"

    assert app.timer_frame.pack_forget_calls == 1
    assert app.timer_frame.pack_calls[-1] == {"pady": 0}

    assert len(app.mode_frame.pack_calls) == 1
    assert len(app.mode_label.pack_calls) == 1
    assert len(app.start_btn.pack_calls) == 1
    assert app.maximize_btn.pack_calls[-1] == {"side": "left", "padx": (5, 0), "anchor": "center"}


def test_update_timer_auto_minimizes_when_done(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.timer_running = True
    app.current_mode = "Work"
    app.pomodoro_time = 0
    app.is_maximized = True
    monkeypatch.setattr(pomodoro.sys, "platform", "win32")

    minimizes = []
    monkeypatch.setattr(app, "minimize_timer", lambda: minimizes.append(True))
    monkeypatch.setattr(app, "set_mode", lambda mode: None)

    app.update_timer()

    assert app.timer_running is False
    assert minimizes == [True]


def test_reset_today_stats_removes_only_todays_entries(tmp_path):
    storage = StorageManager(history_file=tmp_path / "history.json")

    from datetime import date, timedelta
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()

    dummy_history = [
        {"date": today, "type": "Work", "duration_seconds": 1500},
        {"date": yesterday, "type": "Work", "duration_seconds": 1500},
        {"date": today, "type": "Stopwatch", "duration_seconds": 600},
        {"date": two_days_ago, "type": "Work", "duration_seconds": 1500},
    ]

    with open(storage.history_file, "w") as f:
        json.dump(dummy_history, f)

    success = storage.reset_today_stats()
    assert success is True

    history = storage.load_history()
    assert len(history) == 2
    dates_remaining = [s["date"] for s in history]
    assert today not in dates_remaining
    assert yesterday in dates_remaining
    assert two_days_ago in dates_remaining


def test_minimize_timer_restores_custom_geometry(tmp_path):
    app = get_test_app(tmp_path)
    app.settings["window_width"] = 400
    app.settings["window_height"] = 500

    app.minimize_timer()

    assert app.root.geometry_calls[-1] == "400x500"


def test_maximize_timer_uses_custom_geometry(tmp_path):
    app = get_test_app(tmp_path)
    app.settings["maximized_window_width"] = 300
    app.settings["maximized_window_height"] = 120

    app.maximize_timer()

    assert app.root.geometry_calls[-1] == "300x120"


def test_transition_saves_sizes_immediately(tmp_path):
    app = get_test_app(tmp_path)

    root = app.root
    root.current_geom = "350x350+120+120"
    app.is_maximized = False

    app.maximize_timer()

    assert app.settings["window_width"] == 350
    assert app.settings["window_height"] == 350

    root.current_geom = "260x95+120+120"
    app.is_maximized = True

    app.minimize_timer()

    assert app.settings["maximized_window_width"] == 260
    assert app.settings["maximized_window_height"] == 95


def test_add_todo_item(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    monkeypatch.setattr(app, "render_todos", lambda: None)

    fake_entry = FakeEntry("Buy groceries")
    app.todo_entry = fake_entry

    app.add_todo_item()

    assert len(app.storage.todos) == 1
    assert app.storage.todos[0]["text"] == "Buy groceries"
    assert app.storage.todos[0]["done"] is False
    assert fake_entry.get() == ""

    saved_todos = json.loads(app.storage.todos_file.read_text(encoding="utf-8"))
    assert len(saved_todos) == 1
    assert saved_todos[0]["text"] == "Buy groceries"


def test_toggle_todo_status(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    monkeypatch.setattr(app, "render_todos", lambda: None)

    todo = {"id": 12345, "text": "Wash dishes", "done": False}
    app.storage.todos = [todo]

    app.toggle_todo_status(todo, True)

    assert app.storage.todos[0]["done"] is True

    saved_todos = json.loads(app.storage.todos_file.read_text(encoding="utf-8"))
    assert saved_todos[0]["done"] is True


def test_delete_todo_item(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    monkeypatch.setattr(app, "render_todos", lambda: None)

    todo1 = {"id": 1, "text": "Task 1", "done": False}
    todo2 = {"id": 2, "text": "Task 2", "done": False}
    app.storage.todos = [todo1, todo2]

    app.delete_todo_item(todo1)

    assert len(app.storage.todos) == 1
    assert app.storage.todos[0]["id"] == 2

    saved_todos = json.loads(app.storage.todos_file.read_text(encoding="utf-8"))
    assert len(saved_todos) == 1
    assert saved_todos[0]["id"] == 2
