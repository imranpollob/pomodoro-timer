"""Exercise a NORMAL Windows binary through UI Automation, with isolated data.

Run with Python 3.12 and pywinauto==0.6.9. No embedded test driver is used.
"""
import ctypes
from contextlib import closing
from ctypes import wintypes
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

from pywinauto import Desktop
from pywinauto.keyboard import send_keys


def wait_for(predicate, description, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Timed out: {description}")


def button(window, name):
    control = window.child_window(title=name, control_type="Button", visible_only=False)
    control.wait("exists enabled", timeout=25)
    return control


def records(profile):
    with closing(sqlite3.connect(profile / "prototype.sqlite3")) as database:
        return database.execute("SELECT active_ms, outcome FROM sessions").fetchall()


def probe(executable, folder):
    profile = folder / "profile"
    environment = os.environ.copy()
    environment["POMODORO_BETA_DATA_DIR"] = str(profile)
    # A normal artifact must ignore the test-driver environment variable.
    environment["POMODORO_NATIVE_SMOKE_REPORT"] = str(folder / "unexpected-driver.json")
    process = subprocess.Popen([str(executable)], env=environment)
    checks = []
    main = None
    helper = None
    try:
        ui = Desktop(backend="uia")
        main = ui.window(process=process.pid, title="Pomodoro Beta")
        main.wait("visible", timeout=30)
        button(main, "Start focus").invoke()
        button(main, "Pause").invoke()
        button(main, "Resume").invoke()
        button(main, "Finish").invoke()
        button(main, "Keep focusing").invoke()
        button(main, "Finish").invoke()
        button(main, "Finish and save").invoke()
        button(main, "Start focus")
        wait_for(lambda: len(records(profile)) == 1, "one completed finish transaction")
        assert records(profile)[0][0] > 0
        checks.append("UIA start/pause/resume/confirmation and one SQLite record")

        button(main, "Compact mode").invoke()
        compact = ui.window(process=process.pid, title="Pomodoro compact timer")
        compact.wait("visible", timeout=20)
        handle = compact.wrapper_object().handle
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
        rectangle = wintypes.RECT()
        user32.GetClientRect(handle, ctypes.byref(rectangle))
        dpi = user32.GetDpiForWindow(handle) or 96
        width = (rectangle.right - rectangle.left) * 96 / dpi
        height = (rectangle.bottom - rectangle.top) * 96 / dpi
        assert abs(width - 200) <= 2 and abs(height - 44) <= 2, (width, height, dpi)
        checks.append(f"native compact client size {width:g} x {height:g} logical pixels")
        button(compact, "Start focus").invoke()
        button(compact, "Pause").invoke()
        main.minimize()
        # UIA Invoke on the time region is an assistive-technology action.
        compact.child_window(title_re="Focus, .*Open main window", control_type="Button").invoke()
        wait_for(lambda: not user32.IsIconic(main.wrapper_object().handle), "accessible reopen from compact")
        checks.append("compact controls and accessible reopen of minimized main")

        button(main, "Settings").invoke()
        checkbox = main.child_window(title="Enable global shortcuts", control_type="CheckBox")
        checkbox.wait("exists", timeout=20)
        checkbox.toggle()
        # pywinauto's `title` for Edit uses its VALUE, not its UIA accessible name.
        edits = main.descendants(control_type="Edit")
        timer_edit = next(edit for edit in edits if edit.element_info.name == "Global timer shortcut")
        open_edit = next(edit for edit in edits if edit.element_info.name == "Open main shortcut")
        timer_edit.set_edit_text("Control+Alt+Shift+F24")
        open_edit.set_edit_text("Control+Alt+Shift+F23")
        button(main, "Save desktop preferences").invoke()
        wait_for(lambda: main.child_window(title="Registered", control_type="Text", visible_only=False).exists(), "shortcut registration")

        # Own a harmless second window to prove the app does not need focus.
        import tkinter as tk
        helper = tk.Tk()
        helper.title("Pomodoro shortcut smoke")
        helper.geometry("260x70+50+50")
        tk.Label(helper, text="Testing background timer shortcuts").pack(pady=15)
        main.minimize()
        helper.update()
        helper.lift()
        helper.focus_force()
        helper.update()
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        def helper_has_focus():
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(owner))
            return owner.value == os.getpid()
        wait_for(helper_has_focus, "test helper has foreground focus", timeout=5)
        send_keys("^%+{F24}")
        button(compact, "Pause")
        send_keys("^%+{F24}")
        button(compact, "Resume")
        send_keys("^%+{F23}")
        wait_for(lambda: not user32.IsIconic(main.wrapper_object().handle), "global main-window reopen")
        checks.append("real global shortcut keys while another window has focus")
        helper.destroy()
        helper = None

        if os.environ.get("POMODORO_TEST_AUDIO") == "1":
            button(main, "Test sound").invoke()
            wait_for(lambda: main.child_window(title="Playback accepted by the output device.", control_type="Text", visible_only=False).exists(), "native audio device")
            checks.append("native audio output device accepted playback; hearing requires manual confirmation")
            button(main, "Stop preview").invoke()
        if os.environ.get("POMODORO_TEST_NOTIFICATION") == "1":
            button(main, "Test notification").invoke()
            time.sleep(0.5)
            assert not main.child_window(title="Needs attention", control_type="Text", visible_only=False).exists(), "Notification API reported an error"
            checks.append("notification test requested; delivery requires manual confirmation")

        # A second normal process must activate the first rather than write another profile.
        second = subprocess.Popen([str(executable)], env=environment)
        second.wait(timeout=20)
        assert process.poll() is None
        checks.append("second instance exits while original remains active")
        main.close()
        process.wait(timeout=20)
        assert process.returncode == 0
        assert not (folder / "unexpected-driver.json").exists(), "Normal artifact contained the smoke driver"
        with closing(sqlite3.connect(profile / "prototype.sqlite3")) as database:
            checkpoint = json.loads(database.execute("SELECT payload FROM app_state WHERE id=1").fetchone()[0])
            assert checkpoint["active"] is not None
            assert database.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
        checks.append("normal close checkpoints unfinished work; driver absent")
        saved_time = checkpoint["active"]["elapsed_ms"]
        process = subprocess.Popen([str(executable)], env=environment)
        main = ui.window(process=process.pid, title="Pomodoro Beta")
        main.wait("visible", timeout=30)
        button(main, "Resume")
        main.child_window(title_re="Your previous session was restored paused.*", control_type="Text").wait("exists", timeout=20)
        main.close()
        process.wait(timeout=20)
        with closing(sqlite3.connect(profile / "prototype.sqlite3")) as database:
            restored = json.loads(database.execute("SELECT payload FROM app_state WHERE id=1").fetchone()[0])
            assert restored["active"]["elapsed_ms"] == saved_time
        checks.append("normal restart restores paused without process-down duration")
        return {"passed": True, "checks": checks, "dpi": dpi}
    finally:
        if helper is not None:
            helper.destroy()
        if process.poll() is None:
            if main is not None:
                try:
                    main.close()
                    process.wait(timeout=10)
                except Exception:
                    pass
            if process.poll() is None:
                # Only the process created by this test is terminated.
                process.kill()
                process.wait(timeout=5)


def main():
    if os.name != "nt":
        raise RuntimeError("This harness requires a Windows desktop session.")
    executable = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="pomodoro-windows-uia-") as directory:
        result = probe(executable, Path(directory))
        print(json.dumps(result, indent=2))
        if len(sys.argv) > 2:
            Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
