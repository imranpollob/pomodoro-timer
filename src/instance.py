"""OS-held single-instance lock; process death releases it without stale PID files."""
import os
from pathlib import Path

class AlreadyRunning(Exception):
    pass

class InstanceLock:
    def __init__(self, path):
        self.path = Path(path)
        self._file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = open(self.path, "a+b")
        try:
            if self.path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise AlreadyRunning("The data directory is already in use.") from exc
        self._file = stream
        return self

    def __exit__(self, *args):
        # Unlinking could create two independently locked inodes.
        if self._file is not None:
            self._file.close()
            self._file = None
