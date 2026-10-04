from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import requests

# Kept for source compatibility; age alone can never establish safe deletion.
TOMBSTONE_RETENTION_DAYS = 7

def parse_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Task timestamp must be ISO-formatted text.")
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
        # Legacy zones cannot be recovered. All clients use the same ordering.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        if parsed.year == 9999:
            raise ValueError("Timestamp is outside the editable range.")
        return parsed
    except (ValueError, OverflowError) as exc:
        raise ValueError("Task timestamp is not a supported ISO date/time.") from exc

def next_timestamp(*previous):
    now = datetime.now(timezone.utc)
    for value in previous:
        older = parse_timestamp(value)
        if older >= now:
            if older.year == 9999:
                raise ValueError("Task timestamp is outside the editable range.")
            now = older + timedelta(microseconds=1)
    return now.isoformat()

def validate_todos(items):
    if not isinstance(items, list):
        raise ValueError("Tasks must be a JSON list.")
    seen = set()
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each task must be an object.")
        key = item.get("id")
        if ((type(key) is not int or key < 0) and
                (not isinstance(key, str) or not key.strip() or len(key) > 128)):
            raise ValueError("Each task needs a valid integer or text ID.")
        if key in seen:
            raise ValueError("Task IDs must be unique.")
        seen.add(key)
        if not isinstance(item.get("text"), str) or type(item.get("done")) is not bool:
            raise ValueError("Each task needs text and a boolean completion state.")
        if "deleted" in item and type(item["deleted"]) is not bool:
            raise ValueError("Task deletion state must be true or false.")
        parse_timestamp(item.get("updated_at", ""))
        result.append(dict(item))
    return result

class JsonBinClient:
    BASE_URL = "https://api.jsonbin.io/v3"

    def __init__(self, bin_id: str, access_key: str, timeout: int = 15) -> None:
        self.bin_id = bin_id
        self.access_key = access_key
        self.timeout = timeout

    @property
    def bin_url(self) -> str:
        return f"{self.BASE_URL}/b/{self.bin_id}"

    def load(self) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.bin_url}/latest",
            headers={"X-Access-Key": self.access_key},
            params={"meta": "false"}, timeout=self.timeout,
        )
        response.raise_for_status()
        return validate_todos(response.json())

    def save(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items = validate_todos(items)
        response = requests.put(
            self.bin_url,
            headers={"X-Access-Key": self.access_key, "Content-Type": "application/json"},
            json=items, timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Invalid sync response.")
        return validate_todos(result.get("record", items))

def merge_todos(local, remote):
    """Legacy last-write-wins bridge; whole-bin PUT is not a concurrency protocol."""
    local, remote = validate_todos(local), validate_todos(remote)
    merged = {todo["id"]: todo for todo in remote}
    for todo in local:
        existing = merged.get(todo["id"])
        if existing is None:
            merged[todo["id"]] = todo
            continue
        local_time = parse_timestamp(todo.get("updated_at", ""))
        remote_time = parse_timestamp(existing.get("updated_at", ""))
        if local_time > remote_time or (
            local_time == remote_time and
            (todo.get("deleted", False) or not existing.get("deleted", False))
        ):
            merged[todo["id"]] = todo
    return list(merged.values())

def reconcile_todos(snapshot, current, received):
    """Replay edits made after download started, including edits with clock skew."""
    result = {t["id"]: t for t in merge_todos(current, received)}
    before = {t["id"]: t for t in validate_todos(snapshot)}
    received_by_id = {t["id"]: t for t in validate_todos(received)}
    changed = False
    for item in validate_todos(current):
        if item != before.get(item["id"]):
            item = dict(item)
            other = received_by_id.get(item["id"], {})
            item["updated_at"] = next_timestamp(
                item.get("updated_at", ""), other.get("updated_at", "")
            )
            result[item["id"]] = item
            changed = True
    return list(result.values()), changed

def purge_old_tombstones(todos, days=TOMBSTONE_RETENTION_DAYS):
    """Retain deletion knowledge until a future acknowledged sync protocol exists."""
    return validate_todos(todos)
