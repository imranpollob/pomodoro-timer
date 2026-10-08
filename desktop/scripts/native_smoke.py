"""Run a smoke-test-feature executable with isolated data; never a release binary."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

def sample_compact_linux():
    """Return (mapped, width, height) for the compact strip via xwininfo."""
    tree = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True, check=False)
    window_id = None
    for line in tree.stdout.splitlines():
        match = re.search(r'(0x[0-9a-fA-F]+)\s+"Pomodoro compact timer"', line)
        if match:
            window_id = match.group(1)
            break
    if window_id is None:
        return (False, 0, 0)
    info = subprocess.run(["xwininfo", "-id", window_id], capture_output=True, text=True, check=False)
    width = height = 0
    for line in info.stdout.splitlines():
        match = re.match(r"\s*Width:\s*(\d+)", line)
        if match:
            width = int(match.group(1))
        match = re.match(r"\s*Height:\s*(\d+)", line)
        if match:
            height = int(match.group(1))
    return ("IsViewable" in info.stdout, width, height)

def main():
    executable = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="pomodoro-tauri-smoke-") as folder:
        report = Path(folder) / "report.json"
        environment = os.environ.copy()
        environment["POMODORO_BETA_DATA_DIR"] = str(Path(folder) / "profile")
        environment["POMODORO_NATIVE_SMOKE_REPORT"] = str(report)
        options = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options["startupinfo"] = startup
        process = subprocess.Popen([str(executable)], env=environment, **options)
        samples = 0
        settled_geometry = None
        geometry_warned = False
        code = None
        try:
            deadline = time.monotonic() + 90
            while True:
                code = process.poll()
                if sys.platform == "linux" and code is None:
                    if shutil.which("xwininfo") is None:
                        if not geometry_warned:
                            print("WARNING: xwininfo (x11-utils) not found; compact geometry unchecked.", flush=True)
                            geometry_warned = True
                    else:
                        mapped, width, height = sample_compact_linux()
                        if mapped:
                            samples += 1
                            settled_geometry = (width, height)
                if code is not None:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Native smoke timed out after 90s.")
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        if not report.exists():
            raise RuntimeError(f"Native renderer/IPC smoke produced no report (exit {code}).")
        result = json.loads(report.read_text(encoding="utf-8"))
        print(json.dumps(result, indent=2))
        if code != 0 or result.get("passed") is not True:
            raise RuntimeError("Native smoke failed")
        if sys.platform == "linux" and shutil.which("xwininfo") is not None:
            if samples == 0:
                raise RuntimeError("Compact window never mapped during native smoke.")
            print(f"Compact settled at {settled_geometry[0]}x{settled_geometry[1]} over {samples} samples.", flush=True)
            if settled_geometry != (200, 44):
                raise RuntimeError(f"Compact strip settled at {settled_geometry[0]}x{settled_geometry[1]}; want 200x44.")

if __name__ == "__main__":
    main()
