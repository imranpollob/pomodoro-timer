"""Run a smoke-test-feature executable with isolated data; never a release binary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

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
        try:
            code = process.wait(timeout=45)
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

if __name__ == "__main__":
    main()
