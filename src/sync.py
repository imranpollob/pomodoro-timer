from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

TOMBSTONE_RETENTION_DAYS = 7


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
        """Download the latest JSON list from JSONBin."""
        response = requests.get(
            f"{self.bin_url}/latest",
            headers={"X-Access-Key": self.access_key},
            params={"meta": "false"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            raise ValueError("Expected the JSONBin record to contain a JSON list.")

        return data

    def save(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace the JSONBin contents with the supplied list."""
        response = requests.put(
            self.bin_url,
            headers={
                "X-Access-Key": self.access_key,
                "Content-Type": "application/json",
            },
            json=items,
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("record", items)


def merge_todos(
    local: list[dict[str, Any]],
    remote: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge local and remote todo lists by id, newest updated_at wins.

    Deletions are tombstones (a todo with "deleted": True) rather than
    outright removals, so a deletion is just another field change and
    propagates like any other edit: items present on both sides are
    resolved by comparing "updated_at" (missing timestamps sort as
    oldest), and whichever side deleted (or un-deleted) most recently
    wins. Items present on only one side are kept as-is.
    """
    merged: dict[Any, dict[str, Any]] = {todo["id"]: dict(todo) for todo in remote}

    for todo in local:
        todo_id = todo["id"]
        existing = merged.get(todo_id)
        if existing is None or todo.get("updated_at", "") >= existing.get("updated_at", ""):
            merged[todo_id] = dict(todo)

    return list(merged.values())


def purge_old_tombstones(
    todos: list[dict[str, Any]],
    days: int = TOMBSTONE_RETENTION_DAYS,
) -> list[dict[str, Any]]:
    """Drop tombstones (deleted todos) whose "updated_at" is older than `days`.

    Run this on the merged list right before pushing it back, so every
    device converges on the same purge rather than each device deciding
    independently. A tombstone with a missing or unparsable "updated_at"
    is kept, since its age can't be determined.
    """
    cutoff = datetime.now() - timedelta(days=days)
    kept = []

    for todo in todos:
        if todo.get("deleted"):
            updated_at = todo.get("updated_at", "")
            try:
                is_old = datetime.fromisoformat(updated_at) < cutoff
            except ValueError:
                is_old = False
            if is_old:
                continue
        kept.append(todo)

    return kept
