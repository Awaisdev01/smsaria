"""Per-sender conversation state with TTL.

Each phone number gets a rolling conversation history (bounded), a
language preference, and usage counters for the cost guardrails. State
is an in-memory dict by default; swap in any dict-like store (e.g. a
sqlite-backed one) for multi-process deployments.
"""

from __future__ import annotations


import time
from typing import Any


class SessionStore:
    """In-memory session store with TTL expiry."""

    def __init__(self, ttl_seconds: int = 600, max_turns: int = 6):
        self.ttl = ttl_seconds
        self.max_turns = max_turns
        self._data: dict[str, dict[str, Any]] = {}

    def get(self, sender: str) -> dict[str, Any] | None:
        sess = self._data.get(sender)
        if sess and time.time() - sess["updated_at"] > self.ttl:
            self._data.pop(sender, None)
            return None
        return sess

    def start(self, sender: str) -> dict[str, Any]:
        sess = {
            "sender": sender,
            "history": [],  # list of {"role": "user"|"assistant", "text": str}
            "language": None,
            "started_at": time.time(),
            "updated_at": time.time(),
            "messages_today": 0,
        }
        self._data[sender] = sess
        return sess

    def touch(self, sender: str, sess: dict[str, Any]) -> None:
        sess["updated_at"] = time.time()
        self._data[sender] = sess

    def append_history(
        self, sender: str, sess: dict[str, Any], role: str, text: str
    ) -> None:
        sess["history"].append({"role": role, "text": text})
        if len(sess["history"]) > self.max_turns * 2:
            sess["history"] = sess["history"][-(self.max_turns * 2):]
        self.touch(sender, sess)

    def end(self, sender: str) -> None:
        self._data.pop(sender, None)

    def active_count(self) -> int:
        now = time.time()
        return sum(
            1 for s in self._data.values() if now - s["updated_at"] <= self.ttl
        )
