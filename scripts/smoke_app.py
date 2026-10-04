"""Exercise real Tk widgets with temporary data and no sync credentials."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pomodoro import PomodoroApp
from storage import StorageManager

class Clock:
    value = 100.0
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds

def main():
    with tempfile.TemporaryDirectory(prefix="pomodoro-gui-smoke-") as folder:
        path = Path(folder)
        manager = StorageManager(path / "settings.json", path / "todos.json", path / "history.json")
        clock = Clock()
        app = PomodoroApp(manager, clock=clock)
        app.root.withdraw()
        try:
            app.start_pomodoro()
            clock.advance(12)
            app.update_timer()
            assert app.timer_label.cget("text") == "24:48"
            app.pause_pomodoro()
            clock.advance(200)
            app.continue_pomodoro()
            clock.advance(18)
            app.stop_pomodoro()
            assert manager.load_history()[0]["duration_seconds"] == 30
            app.set_mode("Stopwatch")
            app.start_pomodoro()
            clock.advance(30)
            app.pause_pomodoro()
            clock.advance(200)
            app.continue_pomodoro()
            clock.advance(15)
            app.stop_pomodoro()
            assert manager.load_history()[1]["duration_seconds"] == 45
            app.open_todos_dialog()
            app._todos_win.withdraw()
            app.todo_entry.insert(0, "Draft retained — 测试")
            app.add_todo_item()
            assert manager.todos[0]["text"] == "Draft retained — 测试"
            app.start_edit(manager.todos[0]["id"])
            draft = app._todo_edit_vars[manager.todos[0]["id"]]
            draft.set("Unsaved draft")
            app.render_todos()
            assert app._todo_edit_vars[manager.todos[0]["id"]].get() == "Unsaved draft"
            app.open_settings_dialog()
            app._settings_win.withdraw()
            app.open_report_dialog()
            app._report_win.withdraw()
            app.maximize_timer()
            app.minimize_timer()
            app.root.update()
            app.on_close()
            assert app._closed
        finally:
            app._sync_stop_event.set()
            if not app._closed:
                app.root.destroy()
    print("Native Tk smoke passed: timer, stopwatch, drafts, tasks, settings, report, geometry and close.")

if __name__ == "__main__":
    main()
