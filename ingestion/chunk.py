"""Chunking (INGEST_PLAN.md §5.4): sentence-boundary chunks inside a unit, with overlap.

Sizes: English 300-600 cl100k tokens (aim ~450). Arabic uses the same *word* budget, 230-460 words
(D3), because cl100k spends ~2.9x more tokens per Arabic character. A chunk never crosses a unit
(question, entry, section); overlap (one or two sentences, <= 15 % of the maximum) repeats the end of
a chunk at the start of the next chunk of the same unit, and so crosses page breaks naturally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .embed import count_tokens
from .structure import Block, Unit

LIMITS = {"en": (300, 450, 600), "ar": (230, 345, 460)}  # min, target, max (tokens for en, words for ar)
OVERLAP_SHARE = 0.15
MIN_TAIL_SHARE = 0.5  # a last chunk under half the minimum is merged into the previous one

_ABBREVIATIONS = {
    "st", "sts", "fr", "frs", "mr", "mrs", "dr", "vol", "vols", "p", "pp", "cf", "ch", "chap", "no", "nos",
    "ed", "eds", "rev", "trans", "ibid", "viz", "ss", "abba", "anba", "hh", "h.h", "e.g", "i.e", "etc", "al",
    "gen", "ex", "exod", "lev", "num", "deut", "josh", "judg", "sam", "kgs", "chr", "neh", "esth", "ps", "pss",
    "prov", "eccl", "isa", "jer", "lam", "ezek", "dan", "hos", "mic", "hab", "zech", "mal", "matt", "mt",
    "mk", "lk", "jn", "rom", "cor", "gal", "eph", "phil", "col", "thess", "tim", "tit", "philem", "heb",
    "jas", "pet", "jud", "apoc", "sir", "wis", "tob", "macc", "bar", "hom", "ep", "epist", "comm", "lib",
}
_EN_BOUNDARY = re.compile(r"[.!?][\"”’')\]]*\s+(?=[\"“‘(\[]?[A-Z0-9])")
_AR_BOUNDARY = re.compile(r"[.!?؟][\"”’')\]]*\s+(?=\S)")


def split_sentences(text: str, language: str) -> List[Tuple[int, int]]:
    """(start, end) character spans of the sentences in `text`."""
    spans: List[Tuple[int, int]] = []
    start = 0
    pattern = _EN_BOUNDARY if language == "en" else _AR_BOUNDARY
    for match in pattern.finditer(text):
        if language == "en":
            before = text[start:match.start() + 1]
            word = re.search(r"([A-Za-z.]+)[.!?]$", before)
            token = (word.group(1) if word else "").rstrip(".").lower()
            if token in _ABBREVIATIONS or (len(token) == 1 and token.isalpha()) or re.fullmatch(r"(?:[a-z]\.)+[a-z]", token):
                continue  # "St. Mark", "Fr. Tadros", "A.D. 451", "p. 12", "J. Smith"
        end = match.end()
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


@dataclass
class Piece:
    """A sentence (or a short block kept whole) with the facts the chunker needs."""

    text: str
    size: int
    page_start: int
    page_end: int
    subsection: str
    kind: str  # body | subheading | references | notes
    block_start: bool  # first piece of its paragraph (a good place to break)


def measure(text: str, language: str) -> int:
    return count_tokens(text) if language == "en" else len(text.split())


def _split_long(text: str, language: str, limit: int) -> List[str]:
    """A sentence longer than the maximum: split at ';' or ',' and, failing that, between words."""
    parts, current = [], ""
    for piece in re.split(r"(?<=[;،,؛])\s+", text):
        candidate = f"{current} {piece}".strip()
        if current and measure(candidate, language) > limit:
            parts.append(current)
            current = piece
        else:
            current = candidate
    if current:
        parts.append(current)
    out = []
    for part in parts:
        if measure(part, language) <= limit:
            out.append(part)
            continue
        words, buffer = part.split(" "), []
        for word in words:
            if buffer and measure(" ".join(buffer + [word]), language) > limit:
                out.append(" ".join(buffer))
                buffer = []
            buffer.append(word)
        if buffer:
            out.append(" ".join(buffer))
    return out


def pieces_of(unit: Unit) -> List[Piece]:
    language = unit.language
    _, _, maximum = LIMITS[language]
    pieces: List[Piece] = []
    for block in unit.blocks:
        if block.kind in ("subheading", "references", "notes") and measure(block.text, language) <= maximum:
            pieces.append(Piece(block.text, measure(block.text, language), block.page_start, block.page_end,
                                block.subsection, block.kind, True))
            continue
        first = True
        for start, end in split_sentences(block.text, language):
            sentence = block.text[start:end].strip()
            page_start, page_end = block.page_at(start), block.page_at(max(start, end - 1))
            for part in (_split_long(sentence, language, maximum) if measure(sentence, language) > maximum else [sentence]):
                pieces.append(Piece(part, measure(part, language), page_start, page_end, block.subsection, block.kind, first))
                first = False
    return pieces


@dataclass
class RawChunk:
    pieces: List[Piece]
    overlap: int  # how many leading pieces repeat the previous chunk

    @property
    def size(self) -> int:
        return sum(p.size for p in self.pieces)


def pack(pieces: List[Piece], language: str) -> List[RawChunk]:
    minimum, target, maximum = LIMITS[language]
    overlap_budget = int(maximum * OVERLAP_SHARE)
    chunks: List[RawChunk] = []
    current: List[Piece] = []
    carried = 0

    def emit(with_overlap: bool) -> None:
        nonlocal current, carried
        chunks.append(RawChunk(current, carried))
        tail: List[Piece] = []
        if with_overlap:
            for piece in reversed(current):
                if piece.kind != "body" or len(tail) == 2 or sum(p.size for p in tail) + piece.size > overlap_budget:
                    break
                tail.insert(0, piece)
            if len(tail) == len(current):
                tail = []  # never repeat a whole chunk
        current, carried = list(tail), len(tail)

    remaining = [0] * (len(pieces) + 1)  # size of pieces[i:], to avoid leaving a thin last chunk
    for index in range(len(pieces) - 1, -1, -1):
        remaining[index] = remaining[index + 1] + pieces[index].size
    for index, piece in enumerate(pieces):
        size = sum(p.size for p in current)
        new_subsection = current and piece.subsection != current[-1].subsection and piece.kind == "subheading"
        fits_with_rest = size + remaining[index] <= maximum
        if current and len(current) > carried:
            if size + piece.size > maximum:
                emit(with_overlap=True)
            elif new_subsection and size >= minimum and not fits_with_rest:
                emit(with_overlap=False)  # a new sub-section starts a new chunk, without overlap
            elif piece.block_start and size >= target and not fits_with_rest:
                emit(with_overlap=True)
        if carried and sum(p.size for p in current) + piece.size > maximum:
            current, carried = [], 0  # the overlap would push this chunk over the maximum: drop it
        current.append(piece)
    if current and len(current) > carried:
        chunks.append(RawChunk(current, carried))
    if len(chunks) > 1 and chunks[-1].size < minimum * MIN_TAIL_SHARE:
        last = chunks.pop()
        new = last.pieces[last.overlap:]
        previous = chunks[-1]
        if previous.size + sum(p.size for p in new) <= maximum:
            previous.pieces.extend(new)  # a thin tail joins the previous chunk
        else:  # too big to join: move sentences from the previous chunk to the tail instead
            while (sum(p.size for p in new) < minimum and len(previous.pieces) > previous.overlap + 1
                   and previous.size - previous.pieces[-1].size >= minimum):
                new.insert(0, previous.pieces.pop())
            chunks.append(RawChunk(new, 0))
    return chunks


def chunk_text(raw: RawChunk) -> str:
    """Pieces joined: a new paragraph starts on a new line; sentences of a paragraph share one."""
    out = ""
    for index, piece in enumerate(raw.pieces):
        if index == 0:
            out = piece.text
        elif piece.block_start or piece.kind != "body" or raw.pieces[index - 1].kind != "body":
            out = f"{out}\n\n{piece.text}"
        else:
            out = f"{out} {piece.text}"
    return out


def chunk_unit(unit: Unit) -> List[RawChunk]:
    return pack(pieces_of(unit), unit.language)
