"""Cached answers for the home page's example questions (RET-017).

The four example questions per language are asked far more often than any other text, always as the
first message of a chat. Their first-turn answer is kept in memory and served again, replayed as a
quick stream so the page looks the same.

A cached answer is tied to a fingerprint of everything that shapes it (corpus version and manifest,
prompt version and text, models, retrieval settings). When any of those changes, the old answers no
longer match and are regenerated on the next ask. A restart or redeploy starts empty.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

QUESTIONS_PATH = Path(__file__).resolve().parent / "data" / "cached_answer_questions.json"


def load_questions(path: Path = QUESTIONS_PATH) -> Dict[str, List[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {language: list(data.get(language, [])) for language in ("en", "ar")}


def fingerprint(parts: Iterable[Any]) -> str:
    """A short hash of the settings and texts an answer depends on."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:16]


def replay_pieces(answer: str, words_per_piece: int = 3) -> List[str]:
    """The answer cut into small pieces of whole words, which join back to exactly the answer."""
    tokens = re.findall(r"\S+\s*|\s+", answer)
    return ["".join(tokens[i:i + words_per_piece]) for i in range(0, len(tokens), words_per_piece)]


class AnswerCache:
    def __init__(self, questions: Dict[str, List[str]]):
        self.questions = {language: set(items) for language, items in questions.items()}
        self._entries: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def key(self, question: str, language: str, current_fingerprint: str) -> Optional[Tuple[str, str, str]]:
        """The cache key for an example question, or None for any other question."""
        text = (question or "").strip()
        if text not in self.questions.get(language, set()):
            return None
        return (language, text, current_fingerprint)

    def get(self, key: Tuple[str, str, str]) -> Optional[Dict[str, Any]]:
        with self._lock:
            found = self._entries.get(key)
        return copy.deepcopy(found) if found is not None else None

    def put(self, key: Tuple[str, str, str], payload: Dict[str, Any]) -> None:
        with self._lock:
            # Answers made under an older fingerprint can't be asked for again: drop them.
            for old in [k for k in self._entries if k[:2] == key[:2] and k != key]:
                del self._entries[old]
            self._entries[key] = copy.deepcopy(payload)
