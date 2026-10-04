"""Reproduce review findings using temporary files and the existing fake UI.

Run from the repository root: .venv/Scripts/python docs/research/review_probes.py
These probes describe the reviewed implementation; they are not regression tests.
"""

import copy
import json
import pathlib
import platform
import runpy
import statistics
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
helpers = runpy.run_path(str(ROOT / "tests/test_pomodoro.py"))
from storage import StorageManager
from sync import merge_todos, purge_old_tombstones


def storage_at(path):
    return StorageManager(path / "settings.json", path / "todos.json", path / "history.json")


def main():
    results = {"python": platform.python_version(), "platform": platform.platform(), "probes": {}}
    probes = results["probes"]
    with tempfile.TemporaryDirectory(prefix="pomodoro-review-") as folder:
        path = pathlib.Path(folder)
        app = helpers["get_test_app"](path)
        app.set_mode("Work")
        app.start_pomodoro()
        old_callback = app.root.after_calls[0][1]
        app.pause_pomodoro()
        app.continue_pomodoro()
        callbacks_after_resume = len(app.root.after_calls)
        before_old_callback = app.pomodoro_time
        old_callback()
        probes["rapid_pause_resume"] = {
            "scheduled_callbacks_after_resume": callbacks_after_resume,
            "cancelled_callbacks": len(app.root.after_cancel_calls),
            "stale_callback_changes_remaining_time": app.pomodoro_time != before_old_callback,
            "remaining_before_stale_callback": before_old_callback,
            "remaining_after_stale_callback": app.pomodoro_time,
        }
        assert probes["rapid_pause_resume"]["stale_callback_changes_remaining_time"]

        app = helpers["get_test_app"](path)
        app.todo_list_frame = None
        snapshot = [{"id": 1, "text": "Old title", "done": False, "updated_at": "2026-10-04T10:00:00"}]
        app.storage.todos = copy.deepcopy(snapshot)
        app.storage.todos[0].update(text="New title while sync is running", updated_at="2026-10-04T10:01:00")
        app._on_sync_done(snapshot, None)
        probes["sync_inflight_edit"] = {"title_after_sync": app.storage.todos[0]["text"], "new_edit_lost": app.storage.todos[0]["text"] == "Old title"}
        assert probes["sync_inflight_edit"]["new_edit_lost"]

        live = {"id": 2, "text": "Deleted task", "done": False, "updated_at": "2020-01-01T00:00:00"}
        tombstone = dict(live, deleted=True, updated_at=(datetime.now() - timedelta(days=8)).isoformat())
        remote_after_purge = purge_old_tombstones([tombstone])
        resurrected = merge_todos([live], remote_after_purge)
        probes["offline_device_after_tombstone_purge"] = {"remote_count_after_purge": len(remote_after_purge), "resurrected_count": len(resurrected)}
        assert len(resurrected) == 1

        try:
            purge_old_tombstones([dict(tombstone, updated_at=datetime.now(timezone.utc).isoformat())])
        except Exception as exc:
            probes["aware_tombstone_timestamp"] = {"exception": type(exc).__name__, "message": str(exc)}
        else:
            probes["aware_tombstone_timestamp"] = {"exception": None}
        assert probes["aware_tombstone_timestamp"]["exception"] == "TypeError"

        store = storage_at(path)
        store.history_file.write_text('[{"date": "incomplete"', encoding="utf-8")
        original = store.history_file.read_text(encoding="utf-8")
        store.log_session("Work", 60)
        probes["corrupt_history"] = {"invalid_file_overwritten": store.history_file.read_text(encoding="utf-8") != original, "rows_after_logging": len(store.load_history())}
        assert probes["corrupt_history"]["invalid_file_overwritten"]

        app = helpers["get_test_app"](path)
        app.current_mode = "Work"
        app.pomodoro_time = 24 * 60
        app.settings["work_time"] = 30
        recorded = []
        app.storage.log_session = lambda kind, duration: recorded.append({"type": kind, "seconds": duration})
        app.log_current_session()
        probes["settings_change_during_session"] = {"actual_elapsed_seconds_before_change": 60, "recorded_seconds": recorded[0]["seconds"]}
        assert recorded[0]["seconds"] == 360

        app = helpers["get_test_app"](path)
        app.settings["long_break_interval"] = 0
        app.settings["sound_enabled"] = False
        app.timer_running = True
        app.current_mode = "Work"
        app.pomodoro_time = 0
        app.storage.log_session = lambda *args: None
        try:
            app.update_timer()
        except Exception as exc:
            probes["zero_long_break_interval"] = {"exception": type(exc).__name__}
        else:
            probes["zero_long_break_interval"] = {"exception": None}
        assert probes["zero_long_break_interval"]["exception"] == "ZeroDivisionError"

        benchmark = []
        sample = {"date": "2026-10-04", "type": "Work", "duration_seconds": 1500, "timestamp": "2026-10-04T10:00:00"}
        for count in (100, 10000, 100000):
            store = storage_at(path)
            store.history_file.write_text(json.dumps([sample] * count, indent=4), encoding="utf-8")
            elapsed = []
            for _ in range(5):
                started = time.perf_counter()
                store.log_session("Work", 1500)
                elapsed.append((time.perf_counter() - started) * 1000)
            benchmark.append({"initial_rows": count, "median_log_session_ms": round(statistics.median(elapsed), 3), "file_bytes_after_five_appends": store.history_file.stat().st_size})
        results["history_append_benchmark"] = benchmark
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
