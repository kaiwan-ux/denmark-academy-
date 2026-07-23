from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


class InMemoryAICache:
    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def make_key(self, payload: dict[str, Any]) -> str:
        return sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if not entry:
            return None
        expires_at = entry.get("expires_at")
        if expires_at and expires_at < datetime.now(timezone.utc):
            self._entries.pop(key, None)
            return None
        return entry["value"]

    def set(self, key: str, value: dict[str, Any], expires_at=None) -> None:
        self._entries[key] = {"value": value, "expires_at": expires_at}
