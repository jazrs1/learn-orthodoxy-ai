"""Arabic PDF extraction (INGEST_PLAN.md §2.2, §3, §4).

The text comes from pypdf + NFKC + letter folding: it is complete and in logical order, while
PyMuPDF reverses lam-alef ligatures and drops letters in some spans (ING-001). PyMuPDF is used
only to *locate* what is not body text: the printed page number and the Latin footnote lines of
the catechism, both of which it extracts reliably because they are digits and Latin script.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pymupdf
from pypdf import PdfReader

from .sources import PdfSource, pdf_source
from .textnorm import ARABIC_ANY, is_page_number, normalize_arabic, normalize_whitespace

EXTRACTOR = f"pypdf-text+pymupdf-zones-{pymupdf.VersionBind}"
FOOTNOTE_ZONE_START = 0.60  # Latin footnotes sit in the lower part of the page
LATIN_FOOTNOTE = re.compile(r"^(\d{1,4})\s+([A-Za-z].*)$")


@dataclass
class Footnote:
    number: int
    text: str


@dataclass
class ArabicPage:
    doc_id: str
    page: int
    printed_page: Optional[str]
    text: str  # normalised body text, one paragraph per page (pypdf has no layout)
    footnotes: List[Footnote]
    removed: Dict[str, List[str]] = field(default_factory=dict)
    markers: List[int] = field(default_factory=list)


def _zones(page: "pymupdf.Page") -> Tuple[Optional[str], List[Footnote]]:
    """Printed page number and Latin footnotes, located with PyMuPDF."""
    height = page.rect.height or 1.0
    lines: List[Tuple[float, str, float]] = []
    for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        for line in block.get("lines", []):
            text = normalize_whitespace("".join(s["text"] for s in line["spans"]))
            if text:
                size = max(s["size"] for s in line["spans"])
                lines.append((line["bbox"][1] / height, text, size))
    lines.sort()
    printed = None
    if lines:
        for candidate in (lines[-1], lines[0]):
            if is_page_number(candidate[1]):
                printed = candidate[1]
                break
    body_size = max((size for _, text, size in lines if ARABIC_ANY.search(text)), default=12.0)
    notes: List[Footnote] = []
    for y0, text, size in lines:
        if y0 < FOOTNOTE_ZONE_START or ARABIC_ANY.search(text) or size >= body_size - 1:
            continue
        match = LATIN_FOOTNOTE.match(text)
        if match:
            notes.append(Footnote(int(match.group(1)), match.group(2)))
        elif notes and re.search(r"[A-Za-z]", text):
            notes[-1].text = f"{notes[-1].text} {text}"
    return printed, notes


def _remove_phrase(text: str, phrase: str) -> Tuple[str, bool]:
    """Remove `phrase` from `text` ignoring how pypdf spaced it (it may split or join words)."""
    compact = re.sub(r"\s+", "", phrase)
    if not compact:
        return text, False
    pattern = r"\s*".join(re.escape(ch) for ch in compact)
    match = None
    for match in re.finditer(pattern, text):
        pass  # footnotes are at the end of the page text: take the last occurrence
    if not match:
        return text, False
    return (text[: match.start()] + " " + text[match.end():]).strip(), True


def _remove_last_token(text: str, token: str) -> Tuple[str, bool]:
    tokens = text.split(" ")
    for index in range(len(tokens) - 1, max(-1, len(tokens) - 6), -1):
        if tokens[index] == token:
            del tokens[index]
            return " ".join(tokens), True
    for index in range(min(5, len(tokens))):
        if tokens[index] == token:
            del tokens[index]
            return " ".join(tokens), True
    return text, False


def _strip_latin_tail(text: str) -> Tuple[str, str]:
    """Fallback for the ~2 % of Latin footnotes the phrase match misses (PyMuPDF sometimes puts two
    notes on one line, or pypdf spaces them differently). pypdf emits footnotes after the body, so a
    trailing run of tokens with no Arabic letters that contains Latin letters is footnote residue."""
    tokens = text.split(" ")
    cut = len(tokens)
    while cut > 0 and not ARABIC_ANY.search(tokens[cut - 1]):
        cut -= 1
    tail = " ".join(tokens[cut:])
    if not re.search(r"[A-Za-z]{2,}", tail):
        return text, ""
    # keep sentence punctuation that belongs to the last Arabic word
    while tail and tail[0] in ".،؛:!؟\"')]":
        tail = tail[1:].lstrip()
    return text[: len(text) - len(tail)].rstrip(), tail


def _remove_markers(text: str, numbers: List[int]) -> Tuple[str, List[int]]:
    """Drop the footnote markers pypdf left in the body as bare numbers, once each.

    A marker is one of this page's footnote numbers standing right after Arabic text (vowel marks
    included): "إليك 175 [.", "أغسطينوس 176 وجود", "شيءٍ 593 ]". A number with "." straight after
    it is a question number ("944. لماذا") and is never removed."""
    removed = []
    for number in numbers:
        pattern = "(?<=" + ARABIC_ANY.pattern + ")" + rf" {number}(?![\d.])"
        new_text, count = re.subn(pattern, "", text, count=1)
        if count:
            text = new_text
            removed.append(number)
    return re.sub(r" {2,}", " ", text).strip(), removed


def extract_page(source: PdfSource, reader: PdfReader, doc: "pymupdf.Document", page_number: int) -> ArabicPage:
    raw = reader.pages[page_number - 1].extract_text() or ""
    text = normalize_arabic(raw)
    printed, notes = _zones(doc[page_number - 1])
    removed: Dict[str, List[str]] = {"page_number": [], "footnote": []}
    for note in notes:
        text, ok = _remove_phrase(text, f"{note.number} {note.text}")
        if ok:
            removed["footnote"].append(f"{note.number} {note.text}")
    if printed:
        text, ok = _remove_last_token(text, printed)
        if ok:
            removed["page_number"].append(printed)
    text, tail = _strip_latin_tail(text)
    if tail:
        removed["footnote_tail"] = [tail]
    text, markers = _remove_markers(text, [note.number for note in notes])
    return ArabicPage(source.doc_id, page_number, printed, text, notes, removed, markers)


def extract_pages(key: str, pages: Optional[List[int]] = None) -> List[ArabicPage]:
    source = pdf_source(key)
    reader = PdfReader(str(source.path))
    with pymupdf.open(source.path) as doc:
        numbers = pages or list(range(1, doc.page_count + 1))
        return [extract_page(source, reader, doc, number) for number in numbers]
