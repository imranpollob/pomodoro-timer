"""A UI-independent session clock; refresh callbacks only render its state."""
from dataclasses import dataclass
import math
import time
from typing import Callable

@dataclass(frozen=True)
class SessionConfig:
    mode: str
    duration_seconds: int | None
    long_break_interval: int

class SessionTimer:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.config = SessionConfig("Work", 1500, 4)
        self._elapsed = 0.0
        self._started_at = None
        self.has_started = False

    def prepare(self, mode, duration_seconds, long_break_interval):
        if mode not in ("Work", "Short Break", "Long Break", "Stopwatch"):
            raise ValueError("Unknown timer mode.")
        if mode == "Stopwatch":
            duration_seconds = None
        elif type(duration_seconds) is not int or duration_seconds <= 0:
            raise ValueError("Countdown duration must be a positive integer.")
        if type(long_break_interval) is not int or long_break_interval <= 0:
            raise ValueError("Long-break interval must be a positive integer.")
        self.config = SessionConfig(mode, duration_seconds, long_break_interval)
        self._elapsed = 0.0
        self._started_at = None
        self.has_started = False

    @property
    def running(self):
        return self._started_at is not None

    @property
    def active_seconds(self):
        elapsed = self._elapsed
        if self.running:
            elapsed += max(0.0, self.clock() - self._started_at)
        if self.config.duration_seconds is not None:
            elapsed = min(elapsed, self.config.duration_seconds)
        return elapsed

    @property
    def display_seconds(self):
        if self.config.duration_seconds is None:
            return int(self.active_seconds)
        return max(0, math.ceil(self.config.duration_seconds - self.active_seconds))

    @property
    def completed(self):
        return (self.has_started and self.config.duration_seconds is not None
                and self.active_seconds >= self.config.duration_seconds)

    def start(self):
        if not self.running:
            self.has_started = True
            self._started_at = self.clock()

    def pause(self):
        if self.running:
            self._elapsed = self.active_seconds
            self._started_at = None
