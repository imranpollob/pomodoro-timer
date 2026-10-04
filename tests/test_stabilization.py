"""Regression cases for the seven research findings and their failure paths."""
import json
import pathlib
import subprocess
import sys
import threading

import pytest
import pomodoro
import storage
from instance import InstanceLock
from storage import StorageError, StorageManager
from sync import merge_todos, purge_old_tombstones, validate_todos, JsonBinClient
from timer import SessionTimer
from test_pomodoro import get_test_app, FakeClock, ImmediateThread, fake_json_bin_client

def store_at(folder):
    return StorageManager(folder / "settings.json", folder / "todos.json", folder / "history.json")

def task(text="Original", stamp="2026-10-04T10:00:00+00:00", **changes):
    return {"id": 1, "text": text, "done": False, "updated_at": stamp} | changes

def test_rapid_pause_resume_rejects_stale_callbacks(tmp_path):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    stale = app.root.after_calls[-1][1]
    for _ in range(10):
        app.clock.advance(0.2)
        app.pause_pomodoro()
        app.clock.advance(10)
        app.continue_pomodoro()
    assert len(app.root.active_after) == 1
    before = (app.pomodoro_time, len(app.root.after_calls))
    stale()
    assert (app.pomodoro_time, len(app.root.after_calls)) == before
    app.stop_pomodoro()
    stale()
    assert not app.root.active_after

def test_delayed_refresh_and_display_use_same_clock(tmp_path):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    app.clock.advance(65.4)
    app.update_timer()
    assert app.timer_label.cget("text") == "23:55"
    app.stop_pomodoro()
    assert app.storage.load_history()[0]["duration_seconds"] == 65

def test_stopwatch_preserves_fractional_segments():
    clock = FakeClock()
    timer = SessionTimer(clock)
    timer.prepare("Stopwatch", None, 4)
    timer.start()
    clock.advance(0.75)
    timer.pause()
    clock.advance(100)
    timer.start()
    clock.advance(0.75)
    assert timer.active_seconds == 1.5
    assert timer.display_seconds == 1

def test_completion_delayed_tick_clamps_duration_and_logs_once(tmp_path):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    stale = app.root.after_calls[-1][1]
    app.clock.advance(2000)
    app.update_timer()
    app.update_timer()
    stale()
    app.on_close()
    assert len(app.storage.load_history()) == 1
    assert app.storage.load_history()[0]["duration_seconds"] == 1500
    assert app.completed_pomodoros == 1

@pytest.mark.parametrize("action", ["stop_pomodoro", "on_close", "set_mode"])
def test_lifecycle_finishes_a_session_once_and_invalidates_callbacks(tmp_path, action):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    stale = app.root.after_calls[-1][1]
    app.clock.advance(65)
    if action == "set_mode":
        app.set_mode("Stopwatch")
    else:
        getattr(app, action)()
    stale()
    app.log_current_session()
    assert len(app.storage.load_history()) == 1
    assert not app.root.active_after

def test_settings_change_cannot_recalculate_active_session(tmp_path):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    app.clock.advance(60)
    assert app.apply_settings({"work_time": 30, "long_break_interval": 1})
    assert app._timer.config.duration_seconds == 1500
    assert app._timer.config.long_break_interval == 4
    app.stop_pomodoro()
    assert app.storage.load_history()[0]["duration_seconds"] == 60
    assert app.pomodoro_time == 1800

def test_cycle_interval_changes_apply_to_next_session(tmp_path):
    app = get_test_app(tmp_path)
    app.completed_pomodoros = 1
    app.start_pomodoro()
    app.settings["long_break_interval"] = 1
    app.clock.advance(1500)
    app.update_timer()
    assert app.current_mode == "Short Break"

@pytest.mark.parametrize("key,value", [
    ("work_time", 0), ("work_time", -1), ("work_time", "25"), ("work_time", True),
    ("short_break", 31), ("long_break", 61), ("long_break_interval", 0),
    ("long_break_interval", "four"), ("unfocus_transparency", float("nan")),
    ("unfocus_transparency", 0), ("sound_enabled", "yes"),
])
def test_invalid_settings_are_rejected_before_any_mutation(tmp_path, key, value):
    app = get_test_app(tmp_path)
    app.storage.save_settings()
    original = dict(app.settings)
    original_bytes = app.storage.settings_file.read_bytes()
    assert not app.apply_settings({"sound_enabled": False, key: value})
    assert app.settings == original
    assert app.storage.settings_file.read_bytes() == original_bytes
    assert app.last_error

def test_zero_interval_on_disk_does_not_crash_launch_or_overwrite_source(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"long_break_interval": 0}', encoding="utf-8")
    manager = store_at(tmp_path)
    assert manager.settings["long_break_interval"] == 4
    with pytest.raises(StorageError):
        manager.save_settings()
    assert path.read_text(encoding="utf-8") == '{"long_break_interval": 0}'
    assert manager.preserved_files["settings"].read_bytes() == path.read_bytes()

def test_invalid_runtime_interval_prevents_start(tmp_path):
    app = get_test_app(tmp_path)
    app.settings["long_break_interval"] = 0
    app.start_pomodoro()
    assert not app.timer_running
    assert not app.root.active_after
    assert "long_break_interval" in app.last_error

@pytest.mark.parametrize("kind,payload", [
    ("settings", b"["), ("todos", b'[{"id":'), ("history", b'[{"date": "incomplete"'),
])
def test_malformed_original_is_preserved_and_never_silently_overwritten(tmp_path, kind, payload):
    manager = store_at(tmp_path)
    path = getattr(manager, kind + "_file")
    path.write_bytes(payload)
    with pytest.raises(StorageError):
        if kind == "settings":
            manager.save_settings()
        elif kind == "todos":
            manager.save_todos([task()])
        else:
            manager.log_session("Work", 60)
    assert path.read_bytes() == payload
    assert manager.preserved_files[kind].read_bytes() == payload

@pytest.mark.parametrize("kind", ["settings", "todos", "history"])
def test_backup_restore_is_validated_for_each_file(tmp_path, kind):
    manager = store_at(tmp_path)
    if kind == "settings":
        manager.save_settings()
        manager.save_settings(manager.settings | {"work_time": 30})
    elif kind == "todos":
        manager.save_todos([task("旧任务 🌱")])
        manager.save_todos([task("New")])
    else:
        manager.log_session("Work", 60)
        manager.log_session("Stopwatch", 30)
    path = getattr(manager, kind + "_file")
    backup = path.with_name(path.name + ".bak")
    original_backup = backup.read_bytes()
    path.write_bytes(b"{incomplete")
    manager.restore_backup(kind)
    assert path.read_bytes() == original_backup
    assert manager.preserved_files[kind].read_bytes() == b"{incomplete"

def test_failed_replace_keeps_original_and_can_retry(tmp_path, monkeypatch):
    manager = store_at(tmp_path)
    manager.log_session("Work", 60)
    original = manager.history_file.read_bytes()
    original_replace = storage.os.replace
    def fail(source, destination):
        if pathlib.Path(destination) == manager.history_file:
            raise OSError("disk full")
        return original_replace(source, destination)
    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(StorageError):
        manager.log_session("Stopwatch", 30)
    assert manager.history_file.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))
    monkeypatch.undo()
    manager.log_session("Stopwatch", 30)
    assert len(manager.load_history()) == 2

def test_first_write_failure_can_retry_without_a_recovery_file(tmp_path, monkeypatch):
    manager = store_at(tmp_path)
    original_replace = storage.os.replace
    monkeypatch.setattr(storage.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(StorageError):
        manager.log_session("Work", 60)
    assert not manager.history_file.exists()
    monkeypatch.setattr(storage.os, "replace", original_replace)
    manager.log_session("Work", 60)
    assert len(manager.load_history()) == 1

def test_backup_failure_prevents_reset(tmp_path, monkeypatch):
    manager = store_at(tmp_path)
    manager.log_session("Work", 60)
    original = manager.history_file.read_bytes()
    replacement = storage.os.replace
    def fail(source, destination):
        if str(destination).endswith(".bak"):
            raise OSError("backup unavailable")
        return replacement(source, destination)
    monkeypatch.setattr(storage.os, "replace", fail)
    assert not manager.reset_today_stats()
    assert manager.history_file.read_bytes() == original

def test_failed_session_save_blocks_close_and_retries_without_duplication(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    app.clock.advance(65)
    original = app.storage.log_session
    monkeypatch.setattr(app.storage, "log_session", lambda *args: (_ for _ in ()).throw(StorageError("disk full")))
    app.on_close()
    assert app.root.destroy_calls == 0
    assert app._timer.active_seconds == 65
    assert app.start_btn.cget("text") == "Retry save"
    app.clock.advance(100)
    monkeypatch.setattr(app.storage, "log_session", original)
    app.retry_session_save()
    app.on_close()
    assert app.storage.load_history()[0]["duration_seconds"] == 65
    assert len(app.storage.load_history()) == 1
    assert app.root.destroy_calls == 1

def test_failed_task_save_preserves_input_and_local_data(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.todo_entry.text = "Keep my draft"
    monkeypatch.setattr(app.storage, "save_todos", lambda *args: (_ for _ in ()).throw(StorageError("disk full")))
    app.add_todo_item()
    assert app.todo_entry.get() == "Keep my draft"
    assert app.storage.todos == []
    assert not app.root.active_after

def test_sync_inflight_edit_is_replayed_even_with_remote_clock_skew(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.todo_list_frame = None
    snapshot = [task()]
    app.storage.todos = [task("Typed during request")]
    remote = [task("Remote", "2030-10-04T10:00:00+00:00")]
    resyncs = []
    monkeypatch.setattr(app, "sync_todos", lambda: resyncs.append(True))
    app._on_sync_done(remote, None, snapshot)
    assert app.storage.todos[0]["text"] == "Typed during request"
    assert resyncs == [True]
    assert merge_todos(app.storage.todos, remote)[0]["text"] == "Typed during request"

def test_direct_sync_completion_keeps_newer_local_edit(tmp_path):
    app = get_test_app(tmp_path)
    app.todo_list_frame = None
    app.storage.todos = [task("New", "2026-10-04T10:01:00")]
    app._on_sync_done([task("Old", "2026-10-04T10:00:00")], None)
    assert app.storage.todos[0]["text"] == "New"

def test_sync_completion_keeps_draft_widgets(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.editing_todo_ids.add(1)
    monkeypatch.setattr(app, "render_todos", lambda: pytest.fail("Draft widgets were recreated"))
    app._on_sync_done([task()], None)

def test_stale_offline_client_does_not_resurrect_expired_tombstone():
    live = task(stamp="2020-01-01T00:00:00")
    deletion = task(stamp="2020-01-02T00:00:00", deleted=True)
    assert purge_old_tombstones([deletion]) == [deletion]
    assert merge_todos([live], purge_old_tombstones([deletion]))[0]["deleted"]

def test_aware_timestamps_are_compared_as_instants_and_deletion_wins_ties():
    a = task("Later", "2026-10-04T11:00:00+00:00")
    b = task("Earlier", "2026-10-04T15:00:00+05:00")
    assert merge_todos([a], [b])[0]["text"] == "Later"
    assert purge_old_tombstones([a | {"deleted": True}])
    same = task("Same", "2026-10-04T16:00:00+05:00", deleted=True)
    assert merge_todos([a], [same])[0]["deleted"]
    assert merge_todos([same], [a])[0]["deleted"]

@pytest.mark.parametrize("value", [
    {}, [None], [{"text": "No id", "done": False}], [task(id=[])],
    [task(done="false")], [task(updated_at=None)], [task(updated_at="invalid")],
    [task(), task()], [task(updated_at="0001-01-01T00:00:00+10:00")],
])
def test_malformed_remote_tasks_are_rejected(value):
    with pytest.raises(ValueError):
        validate_todos(value)

def test_malformed_remote_data_aborts_upload_and_clears_progress(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.settings.update(jsonbin_bin_id="fake", jsonbin_access_key="fake")
    saved = []
    monkeypatch.setattr(pomodoro.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(pomodoro, "JsonBinClient", fake_json_bin_client(remote_todos=[None], saved_holder=saved))
    app.sync_todos()
    app._poll_sync_results()
    assert not app._sync_in_progress
    assert not saved
    assert not app.storage.todos

def test_worker_uses_queue_and_does_not_call_tk(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.todo_list_frame = None
    app.settings.update(jsonbin_bin_id="fake", jsonbin_access_key="fake")
    owner = threading.get_ident()
    original_after = app.root.after
    def main_only(*args):
        assert threading.get_ident() == owner, "Worker accessed Tk"
        return original_after(*args)
    app.root.after = main_only
    completed = threading.Event()
    class Client:
        def __init__(self, *args):
            pass
        def load(self):
            return [task()]
        def save(self, items):
            completed.set()
            return items
    monkeypatch.setattr(pomodoro, "JsonBinClient", Client)
    app.sync_todos()
    assert completed.wait(3)
    # Join the result, without relying on thread scheduling after save returned.
    result = app._sync_results.get(timeout=3)
    app._sync_results.put(result)
    app._poll_sync_results()
    assert app.storage.todos[0]["text"] == "Original"

def test_close_during_request_prevents_upload_and_late_widget_access(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.settings.update(jsonbin_bin_id="fake", jsonbin_access_key="fake")
    targets, uploads = [], []
    class DeferredThread:
        def __init__(self, target, daemon):
            targets.append(target)
        def start(self):
            pass
    monkeypatch.setattr(pomodoro.threading, "Thread", DeferredThread)
    monkeypatch.setattr(pomodoro, "JsonBinClient", fake_json_bin_client(remote_todos=[task()], saved_holder=uploads))
    app.sync_todos()
    callback = app.root.after_calls[-1][1]
    app.on_close()
    targets[0]()
    callback()
    app._on_sync_done([task()], None)
    assert not uploads
    assert app.storage.todos == []
    assert app.root.destroy_calls == 1
    assert not app.root.active_after

def test_single_instance_lock_excludes_another_process_and_releases(tmp_path):
    source = pathlib.Path(__file__).resolve().parents[1] / "src"
    path = tmp_path / "instance.lock"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from instance import InstanceLock, AlreadyRunning;\n"
        "try:\n with InstanceLock(sys.argv[2]): pass\n"
        "except AlreadyRunning: sys.exit(2)\n"
    )
    command = [sys.executable, "-c", code, str(source), str(path)]
    with InstanceLock(path):
        assert subprocess.run(command, timeout=5).returncode == 2
    assert subprocess.run(command, timeout=5).returncode == 0

def test_jsonbin_http_requests_validate_responses_and_do_not_share_credentials(monkeypatch):
    calls = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return [task()]
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr("sync.requests.get", get)
    client = JsonBinClient("sample", "not-a-real-key")
    assert client.load() == [task()]
    assert calls[0][1]["timeout"] == 15
    assert calls[0][1]["headers"] == {"X-Access-Key": "not-a-real-key"}
    Response.json = lambda self: {"not": "a list"}
    with pytest.raises(ValueError):
        client.load()
def test_failed_completion_retry_keeps_duration_and_cycle_exactly_once(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    app.clock.advance(1500)
    save = app.storage.log_session
    monkeypatch.setattr(app.storage, "log_session", lambda *args: (_ for _ in ()).throw(StorageError("disk full")))
    app.update_timer()
    assert app.completed_pomodoros == 0
    assert app._pending_session_save
    app.clock.advance(100)
    app.continue_pomodoro()
    assert not app.timer_running
    monkeypatch.setattr(app.storage, "log_session", save)
    app.retry_session_save()
    app.retry_session_save()
    assert app.completed_pomodoros == 1
    assert app.current_mode == "Short Break"
    assert app.storage.load_history()[0]["duration_seconds"] == 1500
    assert len(app.storage.load_history()) == 1

def test_failure_in_compact_mode_restores_main_without_recursive_saving(tmp_path, monkeypatch):
    app = get_test_app(tmp_path)
    app.start_pomodoro()
    app.clock.advance(65)
    app.maximize_timer()
    monkeypatch.setattr(app.storage, "save_settings", lambda *args: (_ for _ in ()).throw(StorageError("read only")))
    monkeypatch.setattr(app.storage, "log_session", lambda *args: (_ for _ in ()).throw(StorageError("read only")))
    app.stop_pomodoro()
    assert not app.is_maximized
    assert app.last_error
    assert app._timer.active_seconds == 65

def test_flush_failure_cannot_replace_previous_data(tmp_path, monkeypatch):
    manager = store_at(tmp_path)
    manager.log_session("Work", 60)
    original = manager.history_file.read_bytes()
    monkeypatch.setattr(storage.os, "fsync", lambda *args: (_ for _ in ()).throw(OSError("flush failed")))
    with pytest.raises(StorageError):
        manager.log_session("Stopwatch", 30)
    assert manager.history_file.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))

def test_invalid_backup_does_not_change_original_or_good_backup(tmp_path):
    manager = store_at(tmp_path)
    manager.log_session("Work", 60)
    manager.log_session("Stopwatch", 30)
    original = manager.history_file.read_bytes()
    backup = manager.history_file.with_name("history.json.bak").read_bytes()
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    with pytest.raises(StorageError):
        manager.restore_backup("history", invalid)
    assert manager.history_file.read_bytes() == original
    assert manager.history_file.with_name("history.json.bak").read_bytes() == backup

def test_each_changed_corrupt_original_is_preserved_before_restore(tmp_path):
    manager = store_at(tmp_path)
    manager.log_session("Work", 60)
    manager.log_session("Stopwatch", 30)
    manager.history_file.write_bytes(b"{first")
    with pytest.raises(StorageError):
        manager.load_history()
    manager.history_file.write_bytes(b"{second")
    manager.restore_backup("history")
    contents = {path.read_bytes() for path in tmp_path.glob("history.json.corrupt-*")}
    assert contents == {b"{first", b"{second"}

def test_window_sizes_are_preserved_with_negative_monitor_coordinates(tmp_path):
    app = get_test_app(tmp_path)
    app.root.current_geom = "350x360-1500-200"
    app.maximize_timer()
    assert app.settings["window_width"] == 350
    assert app.settings["window_height"] == 360
    app.root.current_geom = "250x90-1500+50"
    app.minimize_timer()
    assert app.settings["maximized_window_width"] == 250
    app.root.current_geom = "350x360-1500-200"
    app.on_close()
    assert app.root.destroy_calls == 1

