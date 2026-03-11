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


class FakeChild:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs)


class FakeFrame:
    def __init__(self, child_count=2):
        self.children = [FakeChild() for _ in range(child_count)]

    def winfo_children(self):
        return self.children


class FakeRoot:
    def __init__(self):
        self.after_calls = []
        self.bell_calls = 0
        self.attribute_calls = []
        self.wm_attribute_calls = []

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))

    def bell(self):
        self.bell_calls += 1

    def attributes(self, *args):
        self.attribute_calls.append(args)

    def wm_attributes(self, *args):
        self.wm_attribute_calls.append(args)


def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(pomodoro, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(pomodoro, "settings", DEFAULT_SETTINGS.copy())
    monkeypatch.setattr(pomodoro, "current_mode", "Work")
    monkeypatch.setattr(pomodoro, "completed_pomodoros", 0)
    monkeypatch.setattr(pomodoro, "timer_running", False)
    monkeypatch.setattr(pomodoro, "pomodoro_time", 0)


def attach_fake_ui(monkeypatch):
    root = FakeRoot()
    monkeypatch.setattr(pomodoro, "root", root, raising=False)
    monkeypatch.setattr(pomodoro, "mode_label", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "timer_label", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "start_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "continue_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "restart_btn", FakeWidget(), raising=False)
    monkeypatch.setattr(pomodoro, "skip_btn", FakeWidget(), raising=False)
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


def test_restart_pomodoro_resets_stopwatch_mode(tmp_path, monkeypatch):
    reset_state(tmp_path, monkeypatch)
    attach_fake_ui(monkeypatch)
    monkeypatch.setattr(pomodoro, "timer_running", True)
    pomodoro.settings["timer_mode"] = "Stopwatch"
    modes = []
    monkeypatch.setattr(pomodoro, "set_mode", lambda mode: modes.append(mode))

    pomodoro.restart_pomodoro()

    assert pomodoro.timer_running is False
    assert modes == ["Stopwatch"]
    assert pomodoro.continue_btn.pack_forget_calls == 1
    assert pomodoro.restart_btn.pack_forget_calls == 1
    assert pomodoro.start_btn.config_calls[-1] == {
        "text": "Start",
        "command": pomodoro.start_pomodoro,
        "bootstyle": "primary",
    }


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
    assert pomodoro.restart_btn.pack_forget_calls == 1
    assert pomodoro.skip_btn.pack_forget_calls == 1
    assert modes == ["Work"]

