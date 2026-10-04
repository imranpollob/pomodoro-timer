"""Coarse packaged-launch check; detailed widget behavior is smoke_app.py's job."""
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile

def main():
    executable = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="pomodoro-package-smoke-") as folder:
        environment = os.environ.copy()
        environment["POMODORO_DATA_DIR"] = folder
        options = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options["startupinfo"] = startup
        else:
            options["start_new_session"] = True
        process = subprocess.Popen([str(executable)], env=environment, **options)
        try:
            try:
                code = process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                print("Packaged application remained running for 8 seconds.")
            else:
                raise RuntimeError(f"Packaged application exited early: {code}")
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    # One-file bundles have a bootloader parent and app child.
                    # Only terminate the tree of the process this check launched.
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                    )
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=5)

if __name__ == "__main__":
    main()
