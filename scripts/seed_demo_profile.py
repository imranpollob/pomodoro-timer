"""Add randomized synthetic UI/report sample data to a SQLite profile."""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path


TASK_TITLES = [
    "Draft the project proposal",
    "Review pull requests",
    "Study Rust and Tauri",
    "Organize the workspace",
    "Plan the sprint",
    "Write release notes",
    "Fix flaky tests",
    "Prepare the demo",
    "Read the design spec",
    "Clean up the backlog",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=Path,
        help="profile directory (defaults to POMODORO_DATA_DIR or the OS app-data path)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="random seed; the same seed on the same day reproduces the same rows",
    )
    args = parser.parse_args()
    profile = args.profile or default_profile()
    profile = profile.expanduser().resolve()
    profile.mkdir(parents=True, exist_ok=True)
    database = profile / "pomodoro.sqlite3"
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)
    now = datetime.now().astimezone()
    today = now.date()
    month_index = today.year * 12 + today.month - 1 - 11
    start_year, start_month = divmod(month_index, 12)
    range_start = datetime(start_year, start_month + 1, 1).date()
    day_count = (today - range_start).days + 1

    def new_id() -> str:
        return str(uuid.UUID(int=rng.getrandbits(128), version=4))

    def to_ms(moment: datetime) -> int:
        return int(moment.timestamp() * 1000)

    task_titles = rng.sample(TASK_TITLES, rng.randint(3, 8))
    tasks = [(new_id(), title, rng.choice(["todo", "in_progress", "done"])) for title in task_titles]

    records: list[tuple[str, str, int, int, str, str | None, str | None]] = []
    completions: list[tuple[str, str, int]] = []
    for days_ago in range(day_count - 1, -1, -1):
        day = today - timedelta(days=days_ago)
        weekday = day.weekday() < 5
        if rng.random() < (0.12 if weekday else 0.35):
            continue
        focus_count = rng.randint(1, 4) if weekday else rng.randint(0, 2)
        cursor = datetime.combine(day, time(rng.randint(7, 10), rng.choice([0, 15, 30, 45]))).astimezone()
        for index in range(focus_count):
            task = rng.choice(tasks)
            interrupted = rng.random() < 0.12
            duration = rng.randint(6, 24) * 60_000 if interrupted else 25 * 60_000
            records.append((
                new_id(), '"focus"', to_ms(cursor), duration,
                "interrupted" if interrupted else "completed", task[0], task[1],
            ))
            cursor += timedelta(milliseconds=duration) + timedelta(minutes=rng.randint(3, 12))
            if rng.random() < 0.8:
                if index % 4 == 3:
                    records.append((new_id(), '"long_break"', to_ms(cursor), 15 * 60_000, "completed", None, None))
                    cursor += timedelta(minutes=15)
                else:
                    outcome = "skipped" if rng.random() < 0.1 else "completed"
                    records.append((new_id(), '"short_break"', to_ms(cursor), 5 * 60_000, outcome, None, None))
                    cursor += timedelta(minutes=5)
                cursor += timedelta(minutes=rng.randint(1, 5))
        if rng.random() < 0.25:
            start = datetime.combine(day, time(rng.randint(13, 19), rng.choice([0, 30]))).astimezone()
            task = rng.choice(tasks) if rng.random() < 0.7 else None
            records.append((
                new_id(), '"stopwatch"', to_ms(start), rng.randint(10, 95) * 60_000, "finished",
                task[0] if task else None, task[1] if task else None,
            ))
        for _ in range(rng.randint(0, 20)):
            completed_at = datetime.combine(day, time(rng.randint(8, 22), rng.randint(0, 59))).astimezone()
            completions.append((new_id(), rng.choice(tasks)[0], to_ms(completed_at)))
    with sqlite3.connect(database, timeout=10) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 4:
            raise SystemExit("This profile uses a newer database schema; no sample data was added.")
        if version == 0:
            connection.executescript(
                "CREATE TABLE sessions (id TEXT PRIMARY KEY, phase TEXT NOT NULL, started_unix_ms INTEGER NOT NULL, active_ms INTEGER NOT NULL CHECK(active_ms >= 0), outcome TEXT NOT NULL);"
                "CREATE TABLE app_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);"
                "PRAGMA user_version=1;"
            )
            version = 1
        if version < 2:
            connection.executescript(
                "CREATE TABLE preferences (key TEXT PRIMARY KEY, payload TEXT NOT NULL);"
                "PRAGMA user_version=2;"
            )
            version = 2
        if version < 3:
            connection.executescript(
                "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)), deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0, 1)), created_unix_ms INTEGER NOT NULL, updated_unix_ms INTEGER NOT NULL);"
                "ALTER TABLE sessions ADD COLUMN task_id TEXT;"
                "ALTER TABLE sessions ADD COLUMN task_title TEXT;"
                "CREATE INDEX sessions_started_idx ON sessions(started_unix_ms DESC);"
                "PRAGMA user_version=3;"
            )
        if version < 4:
            connection.executescript(
                "ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done'));"
                "DELETE FROM tasks;"
                "CREATE TABLE task_completion_events (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, completed_unix_ms INTEGER NOT NULL);"
                "CREATE INDEX task_completion_events_completed_idx ON task_completion_events(completed_unix_ms);"
                "PRAGMA user_version=4;"
            )
        try:
            now_ms = to_ms(now)
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO tasks (id, title, status, created_unix_ms, updated_unix_ms) VALUES (?, ?, ?, ?, ?)",
                [(task_id, title, status, now_ms, now_ms) for task_id, title, status in tasks],
            )
            connection.executemany(
                "INSERT OR IGNORE INTO task_completion_events (id, task_id, completed_unix_ms) VALUES (?, ?, ?)",
                completions,
            )
            connection.executemany(
                "INSERT OR IGNORE INTO sessions (id, phase, started_unix_ms, active_ms, outcome, task_id, task_title) VALUES (?, ?, ?, ?, ?, ?, ?)",
                records,
            )
            connection.commit()
            added = connection.total_changes - before
        except Exception:
            connection.rollback()
            raise
    print(f"Updated profile: {profile}")
    print(f"Random seed {seed} (pass --seed {seed} to reproduce this batch on the same day).")
    print(f"Added {added} demo rows (up to {len(tasks)} tasks, {len(completions)} task completions, and {len(records)} sessions, spanning {range_start} through {today}, the last twelve months). Existing sessions, settings, and checkpoints were kept; a pre-v4 profile's one-time task reset was applied.")
    print("Restart the desktop app to refresh tasks and reports.")


def default_profile() -> Path:
    override = os.environ.get("POMODORO_DATA_DIR")
    if override:
        return Path(override)
    app_id = "com.imranpollob.pomodoro-timer"
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / app_id
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_id
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / app_id


if __name__ == "__main__":
    main()
