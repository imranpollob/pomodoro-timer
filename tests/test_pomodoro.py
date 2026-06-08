import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pomodoro


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
}


class FakeWidget:
    def __init__(self):
        self.config_calls = []
        self.pack_calls = []
        self.pack_forget_calls = 0

    def config(self, **kwargs):
        self.config_calls.append(kwargs)

    configure = config

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def pack_forget(self):
        self.pack_forget_calls += 1

    def bind(self, event, callback):
        pass


class FakeChild:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs)


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


def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(pomodoro, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(pomodoro, "settings", DEFAULT_SETTINGS.copy())
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    monkeypatch.setattr(pomodoro, "completed_pomodoros", 0)
    monkeypatch.setattr(pomodoro, "timer_running", False)
    monkeypatch.setattr(pomodoro, "pomodoro_time", 0)
    monkeypatch.setattr(pomodoro, "is_maximized", False)
    monkeypatch.setattr(pomodoro, "stopwatch_start_time", None)
    monkeypatch.setattr(pomodoro, "stopwatch_accumulated_seconds", 0)


def attach_fake_ui(monkeypatch):
    root = FakeRoot()
    monkeypatch.setattr(pomodoro, "root", root, raising=False)
    monkeypatch.setattr(pomodoro, "mode_label", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "timer_label", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "timer_frame", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "start_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "continue_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "stop_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "skip_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "maximize_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "minimize_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "menu_bar", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "mode_frame", FakeFrame(), raising=False)
    return root


def test_load_settings_updates_known_values(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"work_time": 30, "timer_mode": "Stopwatch"}), encoding="utf-8"
    )

    pomodoro.load_settings()

    assert pomodoro.settings["work_time"] == 30
    assert pomodoro.settings["timer_mode"] == "Stopwatch"
    assert pomodoro.settings["short_break"] == DEFAULT_SETTINGS["short_break"]


def test_save_settings_writes_json_file(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    pomodoro.settings["long_break_interval"] = 6

    pomodoro.save_settings()

    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["long_break_interval"] == 6
    assert saved["timer_mode"] == "Pomodoro"


def test_get_resource_path_uses_meipass_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(pomodoro.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pomodoro.sys, "_MEIPASS", str(tmp_path), raising=False)

    icon_path = pomodoro.get_resource_path("stopwatch.ico")

    assert icon_path == str(tmp_path / "stopwatch.ico")


def test_set_mode_work_updates_labels_and_remaining_time(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "completed_pomodoros", 1)

    pomodoro.set_mode("Work")

    assert pomodoro.current_mode == "Work"
    assert pomodoro.pomodoro_time == 25 * 60
    assert pomodoro.mode_label.config_calls[-1] == {
        "text": "Work 2/4",
        "bootstyle": "primary",
    }
    assert pomodoro.timer_label.config_calls[-1] == {"text": "25:00"}


def test_set_mode_stopwatch_resets_to_zero(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "pomodoro_time", 99)

    pomodoro.set_mode("Stopwatch")

    assert pomodoro.current_mode == "Stopwatch"
    assert pomodoro.pomodoro_time == 0
    assert pomodoro.mode_label.config_calls[-1] == {
        "text": "Stopwatch",
        "bootstyle": "secondary",
    }
    assert pomodoro.timer_label.config_calls[-1] == {"text": "00:00"}


def test_update_timer_countdown_schedules_next_tick(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    monkeypatch.setattr(pomodoro, "pomodoro_time", 120)

    pomodoro.update_timer()

    assert pomodoro.timer_label.config_calls[-1] == {"text": "02:00"}
    assert pomodoro.pomodoro_time == 119
    assert root.after_calls == [(1000, pomodoro.update_timer)]


def test_update_timer_stopwatch_increments_and_schedules_next_tick(
    tmp_path, monkeypatch
):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Stopwatch")
    monkeypatch.setattr(pomodoro, "pomodoro_time", 5)

    pomodoro.update_timer()

    assert pomodoro.timer_label.config_calls[-1] == {"text": "00:05"}
    assert pomodoro.pomodoro_time == 6
    assert root.after_calls == [(1000, pomodoro.update_timer)]


def test_update_timer_work_completion_moves_to_short_break(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    monkeypatch.setattr(pomodoro, "pomodoro_time", 0)
    monkeypatch.setattr(pomodoro.sys, "platform", "win32")
    modes = []
    monkeypatch.setattr(pomodoro, "set_mode", lambda mode: modes.append(mode))

    pomodoro.update_timer()

    assert pomodoro.timer_running is False
    assert pomodoro.completed_pomodoros == 1
    assert modes == ["Short Break"]
    assert root.bell_calls == 1
    assert pomodoro.start_btn.config_calls[-1] == {
        "text": "Start",
        "command": pomodoro.start_pomodoro,
        "bootstyle": "primary",
    }
    assert all(
        child.states[-1] == {"state": "normal"}
        for child in pomodoro.mode_frame.children
    )


def test_update_timer_work_completion_moves_to_long_break(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    monkeypatch.setattr(pomodoro, "pomodoro_time", 0)
    monkeypatch.setattr(pomodoro, "completed_pomodoros", 3)
    modes = []
    monkeypatch.setattr(pomodoro, "set_mode", lambda mode: modes.append(mode))

    pomodoro.update_timer()

    assert pomodoro.completed_pomodoros == 4
    assert modes == ["Long Break"]


def test_update_timer_long_break_completion_resets_cycle(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Long Break")
    monkeypatch.setattr(pomodoro, "pomodoro_time", 0)
    monkeypatch.setattr(pomodoro, "completed_pomodoros", 4)
    modes = []
    monkeypatch.setattr(pomodoro, "set_mode", lambda mode: modes.append(mode))

    pomodoro.update_timer()

    assert pomodoro.completed_pomodoros == 0
    assert modes == ["Work"]


def test_stop_pomodoro_logs_work_session(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    pomodoro.settings["work_time"] = 25
    monkeypatch.setattr(pomodoro, "pomodoro_time", 15 * 60)  # 10 mins spent

    pomodoro.stop_pomodoro()

    assert pomodoro.timer_running is False
    history = pomodoro.load_history()
    assert len(history) == 1
    assert history[0]["type"] == "Work"
    assert history[0]["duration_seconds"] == 10 * 60


def test_stop_pomodoro_logs_stopwatch_session(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Stopwatch")
    
    # Mock datetime to control elapsed time
    from datetime import datetime, timedelta
    start_time = datetime.now()
    monkeypatch.setattr(pomodoro, "stopwatch_start_time", start_time)
    
    # Force datetime.now() to be 30s later
    class MockDateTime:
        @classmethod
        def now(cls):
            return start_time + timedelta(seconds=30)
    monkeypatch.setattr(pomodoro, "datetime", MockDateTime)

    pomodoro.stop_pomodoro()

    assert pomodoro.timer_running is False
    history = pomodoro.load_history()
    assert len(history) == 1
    assert history[0]["type"] == "Stopwatch"
    assert history[0]["duration_seconds"] == 30


def test_stop_pomodoro_logs_stopwatch_session_with_pauses(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Stopwatch")
    
    from datetime import datetime, timedelta
    start_time = datetime.now()
    monkeypatch.setattr(pomodoro, "stopwatch_start_time", start_time)
    
    # 1. Simulate running for 20 seconds, then pausing
    current_time = start_time + timedelta(seconds=20)
    
    class MockDateTime1:
        @classmethod
        def now(cls):
            return current_time
            
    monkeypatch.setattr(pomodoro, "datetime", MockDateTime1)
    pomodoro.pause_pomodoro()
    
    assert pomodoro.stopwatch_accumulated_seconds == 20
    assert pomodoro.stopwatch_start_time is None
    
    # 2. Simulate resuming (continuing) after 10 seconds of pause
    pomodoro.continue_pomodoro()
    assert pomodoro.stopwatch_start_time == current_time
    
    # 3. Simulate running for another 15 seconds, then stopping
    current_time = current_time + timedelta(seconds=15)
    
    class MockDateTime2:
        @classmethod
        def now(cls):
            return current_time
            
    monkeypatch.setattr(pomodoro, "datetime", MockDateTime2)
    pomodoro.stop_pomodoro()
    
    assert pomodoro.timer_running is False
    history = pomodoro.load_history()
    assert len(history) == 1
    assert history[0]["type"] == "Stopwatch"
    assert history[0]["duration_seconds"] == 35  # 20s active + 15s active


def test_skip_break_moves_to_work_mode(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "current_mode", "Short Break")
    monkeypatch.setattr(pomodoro, "timer_running", True)
    modes = []
    monkeypatch.setattr(pomodoro, "set_mode", lambda mode: modes.append(mode))

    pomodoro.skip_break()

    assert pomodoro.timer_running is False
    assert pomodoro.continue_btn.pack_forget_calls == 1
    assert pomodoro.stop_btn.pack_forget_calls == 1
    assert pomodoro.skip_btn.pack_forget_calls == 1
    assert modes == ["Work"]


def test_log_session_ignores_short_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(pomodoro, "HISTORY_FILE", tmp_path / "history.json")
    
    pomodoro.log_session("Work", 5)
    
    assert not (tmp_path / "history.json").exists()


def test_log_session_appends_to_history(tmp_path, monkeypatch):
    monkeypatch.setattr(pomodoro, "HISTORY_FILE", tmp_path / "history.json")
    
    pomodoro.log_session("Work", 15 * 60)
    pomodoro.log_session("Stopwatch", 30)
    
    history = pomodoro.load_history()
    assert len(history) == 2
    assert history[0]["type"] == "Work"
    assert history[1]["type"] == "Stopwatch"


def test_maximize_timer_hides_controls(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    
    pomodoro.maximize_timer()
    
    assert pomodoro.is_maximized is True
    # Hides mode_frame, mode_label, start_btn, maximize_btn
    assert pomodoro.mode_frame.pack_forget_calls == 1
    assert pomodoro.mode_label.pack_forget_calls == 1
    assert pomodoro.start_btn.pack_forget_calls == 1
    assert pomodoro.maximize_btn.pack_forget_calls == 1
    
    # Check menu bar hidden
    assert root.config_calls[-1] == {"menu": ""}
    # Check geometry changed to compact
    assert root.geometry_calls[-1] == "240x80"
    
    # Check timer_frame repacked with top padding
    assert pomodoro.timer_frame.pack_forget_calls == 1
    assert pomodoro.timer_frame.pack_calls[-1] == {"pady": (15, 5)}
    
    # Check minimize button shown next to the timer
    assert pomodoro.minimize_btn.pack_calls[-1] == {"side": "left", "padx": (5, 0), "anchor": "center"}


def test_minimize_timer_restores_controls_when_running(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    
    pomodoro.minimize_timer()
    
    assert pomodoro.is_maximized is False
    assert pomodoro.minimize_btn.pack_forget_calls == 1
    # Restored menu bar
    assert root.config_calls[-1] == {"menu": pomodoro.menu_bar}
    # Restored default window geometry
    assert root.geometry_calls[-1] == "290x290"
    
    # Restored standard timer_frame packing
    assert pomodoro.timer_frame.pack_forget_calls == 1
    assert pomodoro.timer_frame.pack_calls[-1] == {"pady": 0}
    
    # Repacked main layouts
    assert len(pomodoro.mode_frame.pack_calls) == 1
    assert len(pomodoro.mode_label.pack_calls) == 1
    # Repacked start_btn (Pause) and maximize_btn next to the timer
    assert len(pomodoro.start_btn.pack_calls) == 1
    assert pomodoro.maximize_btn.pack_calls[-1] == {"side": "left", "padx": (5, 0), "anchor": "center"}


def test_minimize_timer_restores_controls_when_completed(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", False)
    
    pomodoro.minimize_timer()
    
    assert pomodoro.is_maximized is False
    assert pomodoro.minimize_btn.pack_forget_calls == 1
    # Restored menu bar and geometry
    assert root.config_calls[-1] == {"menu": pomodoro.menu_bar}
    assert root.geometry_calls[-1] == "290x290"
    
    # Restored standard timer_frame packing
    assert pomodoro.timer_frame.pack_forget_calls == 1
    assert pomodoro.timer_frame.pack_calls[-1] == {"pady": 0}
    
    # Repacked main layouts
    assert len(pomodoro.mode_frame.pack_calls) == 1
    assert len(pomodoro.mode_label.pack_calls) == 1
    # Repacked start_btn (Start), did not pack maximize_btn
    assert len(pomodoro.start_btn.pack_calls) == 1
    assert len(pomodoro.maximize_btn.pack_calls) == 0


def test_update_timer_auto_minimizes_when_done(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    monkeypatch.setattr(pomodoro, "pomodoro_time", 0)
    monkeypatch.setattr(pomodoro, "is_maximized", True)
    monkeypatch.setattr(pomodoro.sys, "platform", "win32")
    
    minimizes = []
    monkeypatch.setattr(pomodoro, "minimize_timer", lambda: minimizes.append(True))
    monkeypatch.setattr(pomodoro, "set_mode", lambda mode: None)
    
    pomodoro.update_timer()
    
    assert pomodoro.timer_running is False
    assert minimizes == [True]


def test_reset_today_stats_removes_only_todays_entries(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    history_file = tmp_path / "history.json"
    monkeypatch.setattr(pomodoro, "HISTORY_FILE", history_file)
    
    # 1. Create a dummy history with different dates
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
    
    with open(history_file, "w") as f:
        json.dump(dummy_history, f)
        
    # 2. Trigger the reset today stats function
    success = pomodoro.reset_today_stats()
    
    assert success is True
    
    # 3. Reload history and check stats are filtered correctly
    history = pomodoro.load_history()
    assert len(history) == 2
    # Verify only past dates remain
    dates_remaining = [s["date"] for s in history]
    assert today not in dates_remaining
    assert yesterday in dates_remaining
    assert two_days_ago in dates_remaining


def test_minimize_timer_restores_custom_geometry(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    pomodoro.settings["window_width"] = 400
    pomodoro.settings["window_height"] = 500
    
    pomodoro.minimize_timer()
    
    assert root.geometry_calls[-1] == "400x500"


def test_maximize_timer_uses_custom_geometry(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    pomodoro.settings["maximized_window_width"] = 300
    pomodoro.settings["maximized_window_height"] = 120
    
    pomodoro.maximize_timer()
    
    assert root.geometry_calls[-1] == "300x120"


def test_transition_saves_sizes_immediately(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    root = attach_fake_ui(monkeypatch)
    
    # 1. Standard mode: set custom geometry mock
    root.current_geom = "350x350+120+120"
    monkeypatch.setattr(pomodoro, "is_maximized", False)
    
    # Maximize (Standard -> Compact transition)
    pomodoro.maximize_timer()
    
    assert pomodoro.settings["window_width"] == 350
    assert pomodoro.settings["window_height"] == 350
    
    # 2. Compact mode: set custom maximized geometry mock
    root.current_geom = "260x95+120+120"
    monkeypatch.setattr(pomodoro, "is_maximized", True)
    
    # Minimize (Compact -> Standard transition)
    pomodoro.minimize_timer()
    
    assert pomodoro.settings["maximized_window_width"] == 260
    assert pomodoro.settings["maximized_window_height"] == 95





