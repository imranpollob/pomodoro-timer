"""Add varied synthetic UI/report sample data to a SQLite profile."""

from __future__ import annotations

import argparse
import calendar
import os
import sqlite3
import sys
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=Path,
        help="profile directory (defaults to POMODORO_DATA_DIR or the OS app-data path)",
    )
    args = parser.parse_args()
    profile = args.profile or default_profile()
    profile = profile.expanduser().resolve()
    profile.mkdir(parents=True, exist_ok=True)
    database = profile / "pomodoro.sqlite3"
    tasks = [
        ("demo-writing", "Draft the project proposal", False),
        ("demo-review", "Review pull requests", False),
        ("demo-study", "Study Rust and Tauri", False),
        ("demo-finished", "Organize the workspace", True),
    ]
    now = datetime.now().astimezone()
    today = now.date()
    month_index = today.year * 12 + today.month - 1 - 2
    start_year, start_month = divmod(month_index, 12)
    start_month += 1
    range_start = today.replace(year=start_year, month=start_month, day=min(today.day, calendar.monthrange(start_year, start_month)[1])) + timedelta(days=1)
    day_count = (today - range_start).days + 1
    records: list[tuple[str, str, int, int, str, str | None, str | None]] = []
    for days_ago in range(day_count - 1, -1, -1):
        day = today - timedelta(days=days_ago)
        morning = datetime.combine(day, time(9, 15)).astimezone()
        count = 2 if day.weekday() < 5 and days_ago % 3 == 0 else 1
        for index in range(count):
            task = tasks[(days_ago + index) % len(tasks)]
            start = morning + timedelta(minutes=75 * index)
            outcome = "interrupted" if days_ago % 9 == 0 and index == 0 else "completed"
            duration = 14 * 60_000 if outcome == "interrupted" else 25 * 60_000
            records.append((
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"demo:{day}:focus:{index}")),
                '"focus"', int(start.timestamp() * 1000), duration, outcome, task[0], task[1],
            ))
        if day.weekday() < 5 and days_ago % 2 == 0:
            start = morning + timedelta(minutes=30)
            break_outcome = "skipped" if days_ago % 10 == 0 else "completed"
            records.append((
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"demo:{day}:break")),
                '"short_break"', int(start.timestamp() * 1000), 5 * 60_000, break_outcome, None, None,
            ))
        if day.weekday() < 5 and days_ago % 7 == 0:
            start = morning + timedelta(hours=2)
            records.append((
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"demo:{day}:long-break")),
                '"long_break"', int(start.timestamp() * 1000), 15 * 60_000, "completed", None, None,
            ))
        if days_ago % 4 == 0:
            start = morning + timedelta(hours=4)
            records.append((
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"demo:{day}:stopwatch")),
                '"stopwatch"', int(start.timestamp() * 1000), 42 * 60_000, "finished", tasks[1][0], tasks[1][1],
            ))
    with sqlite3.connect(database, timeout=10) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 3:
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
        try:
            now_ms = int(now.timestamp() * 1000)
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO tasks (id, title, completed, created_unix_ms, updated_unix_ms) VALUES (?, ?, ?, ?, ?)",
                [(task_id, title, completed, now_ms, now_ms) for task_id, title, completed in tasks],
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
    print(f"Added {added} demo rows (up to {len(tasks)} tasks and {len(records)} sessions, spanning {range_start} through {today}, the last two months). Existing records and settings were kept.")
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
