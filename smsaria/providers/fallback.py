"""Offline fallback cache — never dead air.

Records successful AI answers, keyed by normalized question tokens.
When the provider is unreachable or the daily budget is spent, the
gateway serves the closest cached answer (marked as offline) instead of
an error message. Backed by sqlite3 (stdlib).
"""

import json
import os
import re
import sqlite3
import time
from typing import Optional

_WORD = re.compile(r"[a-z0-9\u0600-\u06ff\u0900-\u097f]+")
_STOP = {
    "the", "a", "an", "is", "are", "of", "to", "for", "and", "or", "in",
    "on", "what", "how", "my", "i", "it", "do", "does", "can", "you",
}


def _tokens(text: str) -> set:
    words = _WORD.findall(text.lower())
    return {w for w in words if w not in _STOP} or set(words)


class AnswerCache:
    def __init__(self, db_path: Optional[str] = None, min_overlap: float = 0.5):
        self.db_path = db_path or os.environ.get(
            "SMSARIA_CACHE_DB", "smsaria_cache.db"
        )
        self.min_overlap = min_overlap
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS answers (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   question TEXT NOT NULL,
                   tokens TEXT NOT NULL,
                   answer TEXT NOT NULL,
                   hits INTEGER DEFAULT 0,
                   created INTEGER NOT NULL
               )"""
        )
        self._conn.commit()

    def record(self, question: str, answer: str) -> None:
        toks = _tokens(question)
        if not toks or not answer:
            return
        self._conn.execute(
            "INSERT INTO answers (question, tokens, answer, created) VALUES (?,?,?,?)",
            (question[:500], json.dumps(sorted(toks)), answer[:600], int(time.time())),
        )
        self._conn.commit()

    def find(self, question: str) -> Optional[str]:
        q = _tokens(question)
        if not q:
            return None
        best, best_score = None, 0.0
        for tok_json, answer in self._conn.execute(
            "SELECT tokens, answer FROM answers"
        ):
            toks = set(json.loads(tok_json))
            if not toks:
                continue
            score = len(q & toks) / len(q | toks)  # Jaccard
            if score > best_score:
                best, best_score = answer, score
        if best is not None and best_score >= self.min_overlap:
            self._conn.execute(
                "UPDATE answers SET hits = hits + 1 WHERE answer = ?", (best,)
            )
            self._conn.commit()
            return best
        return None

    def size(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
