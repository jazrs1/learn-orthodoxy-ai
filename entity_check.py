"""Does the retrieved text mention the specific thing the user asked about? (DECISIONS.md GEN-006)

A vector distance says "this is about a similar topic"; it cannot tell St. Anthony of Padua
from St. Anthony the Great, or purgatory from prayers for the departed (RET-004). This check
looks for the *named subjects* the request analysis extracted (RET-006) in the passages that
will be shown to the model.

Matching is deliberately forgiving about form and strict about identity:
- titles and filler words are ignored ("St.", "Saint", "Abba", "Pope", "the", "of", ...);
- text is compared with all spaces and punctuation removed, so pypdf artefacts such as
  "sufferin g" or "Bish oy" still match, and "St Bishoy" matches "BISHOY, ST. ABBA";
- each word is compared by a stem (a few trailing letters dropped), so "Egyptian" matches
  "Egypt" and "martyrs" matches "martyr";
- Arabic letter variants are folded (alef/hamza forms, ta marbuta, alef maqsura, tatweel,
  diacritics) and the definite article is ignored;
- a subject is present when ONE passage contains all of its core words (all but one when it
  has three or more), so "Anthony" in one passage and "Padua" in another does not count.
Formats, tasks and broad categories never reach this check: the analysis prompt excludes them
from `named_subjects`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List

TITLE_WORDS = {
    "st", "saint", "saints", "ss", "abba", "anba", "abuna", "pope", "patriarch", "bishop", "father",
    "fr", "the", "of", "and", "a", "an", "in", "on", "el", "al", "de", "his", "her", "church", "coptic",
    "orthodox", "doctrine", "teaching", "teachings", "clause", "concept",
    # Arabic titles and particles (after folding)
    "القديس", "القديسه", "قديس", "الانبا", "انبا", "البابا", "بابا", "مار", "الشهيد", "الشهيده", "ابونا",
    "في", "من", "عن", "و", "الكنيسه", "القبطيه",
}
ROMAN_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ی": "ي", "ک": "ك", "ھ": "ه"})


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("ـ", "").translate(_ARABIC_FOLD)
    text = re.sub(r"[ً-ٰٟ]", "", text)
    return text


def _squash(text: str) -> str:
    return re.sub(r"[^0-9a-z؀-ۿ]+", "", _fold(text))


def _stem(word: str) -> str:
    if re.search(r"[؀-ۿ]", word):
        if word.startswith("ال") and len(word) > 4:
            word = word[2:]
        return word
    if len(word) >= 7:
        return word[: len(word) - 3]
    if len(word) >= 5:
        return word[: len(word) - 1]
    return word


def core_words(subject: str) -> List[str]:
    words = re.findall(r"[0-9a-z؀-ۿ]+", _fold(subject))
    out = []
    for word in words:
        if word in TITLE_WORDS or word in ROMAN_NUMERALS or len(word) < 3:
            continue
        stem = _stem(word)
        if stem not in out:
            out.append(stem)
    return out


def subject_present(subject: str, squashed_passages: List[str]) -> bool:
    words = core_words(subject)
    if not words:
        return True  # nothing checkable (e.g. only a title); never block on it
    needed = len(words) - 1 if len(words) >= 3 else len(words)
    return any(sum(1 for word in words if word in text) >= needed for text in squashed_passages)


def check_subjects(subjects: List[str], passages: List[str]) -> Dict[str, List[str]]:
    """{"present": [...], "absent": [...]} for the named subjects against the passage texts."""
    squashed = [_squash(text) for text in passages]
    result: Dict[str, List[str]] = {"present": [], "absent": []}
    for subject in subjects:
        result["present" if subject_present(subject, squashed) else "absent"].append(subject)
    return result
