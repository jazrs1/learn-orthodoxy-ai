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
from .textnorm import (ARABIC_ANY, ARABIC_LETTER, fix_displaced_punctuation, is_page_number, normalize_arabic,
                       normalize_whitespace, orient_page_brackets)

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
    marker_offsets: List[Tuple[int, int]] = field(default_factory=list)  # (offset in text, note number)


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
    body_size = max((size for _, text, size in lines if ARABIC_LETTER.search(text)), default=12.0)
    notes: List[Footnote] = []
    for y0, text, size in lines:
        if y0 < FOOTNOTE_ZONE_START or ARABIC_LETTER.search(text) or size >= body_size - 1:
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


MARKER_BEFORE = "[" + ARABIC_ANY.pattern[1:-1] + ".!\"”)\]]"


def _remove_markers(text: str, numbers: List[int]) -> Tuple[str, List[Tuple[int, int]]]:
    """Drop the footnote markers pypdf left in the body as bare numbers, once each, and return
    (text, [(offset in the returned text, note number)]) so notes can follow their question.

    A marker is one of this page's footnote numbers standing right after Arabic text (vowel marks
    included): "إليك 175 [.", "أغسطينوس 176 وجود", "شيءٍ 593 ]". A number with "." straight after
    it is a question number ("944. لماذا") and is never removed."""
    found = []
    for number in dict.fromkeys(numbers):  # once per note number
        matches = list(re.finditer("(?<=" + MARKER_BEFORE + ")" + rf" {number}(?![\d.])", text))
        # The marker usually closes a quotation ("... الفضيلة. 891 ]"): prefer that one over a
        # verse number that happens to be equal ("(مت 5 : 8 )").
        match = next((m for m in matches if re.match(r"\s*[\[\]]", text[m.end():])), matches[0] if matches else None)
        if match and not any(start < match.end() and match.start() < end for start, end, _ in found):
            found.append((match.start(), match.end(), number))
    for start, end, _ in sorted(found, reverse=True):
        text = text[:start] + text[end:]
    positions = []
    for start, end, number in sorted(found):
        shift = sum(e - s for s, e, _ in found if s < start)
        positions.append((start - shift, number))
    return text, positions


def extract_page(source: PdfSource, reader: PdfReader, doc: "pymupdf.Document", page_number: int) -> ArabicPage:
    raw = reader.pages[page_number - 1].extract_text() or ""
    text = normalize_arabic(raw, balance=False)
    printed, notes = _zones(doc[page_number - 1])
    removed: Dict[str, List[str]] = {"page_number": [], "footnote": []}
    block, block_notes = footnote_block(reader, page_number)
    if block:  # all notes, Arabic and Latin, cut in one piece; the Latin matching below is the fallback
        text, ok = _remove_phrase(text, block)
        if ok:
            removed["footnote_block"] = [block]
            latin = {note.number: note for note in notes}
            notes = [latin.get(note.number, note) for note in block_notes]  # PyMuPDF reads Latin notes better
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
    text = fix_displaced_punctuation(orient_page_brackets(text))
    text, offsets = _remove_markers(text, [note.number for note in notes])
    collapsed = re.sub(" {2,}", " ", text)
    if collapsed != text:  # keep offsets valid when a removal left a double space
        text, offsets = _collapse_spaces(text, offsets)
    return ArabicPage(source.doc_id, page_number, printed, text.strip(), notes, removed, [n for _, n in offsets], offsets)


def _collapse_spaces(text: str, offsets: List[Tuple[int, int]]) -> Tuple[str, List[Tuple[int, int]]]:
    out, mapping = [], []
    for index, ch in enumerate(text):
        mapping.append(len(out))
        if ch == " " and out and out[-1] == " ":
            continue
        out.append(ch)
    new_text = "".join(out)
    return new_text, [(mapping[min(offset, len(mapping) - 1)] if mapping else 0, number) for offset, number in offsets]


def _runs(reader: PdfReader, page_number: int) -> List[Tuple[float, float, bool, str]]:
    """pypdf's text runs: (baseline y from the bottom, size, bold, text)."""
    runs: List[Tuple[float, float, bool, str]] = []

    def visit(text, cm, tm, font, size):
        if not text or not text.strip():
            return
        scale = abs(tm[3] * cm[3]) or 1.0
        name = str((font or {}).get("/BaseFont", ""))
        runs.append((round(tm[5] * cm[3] + cm[5], 1), round(size * scale, 1), "Bold" in name, text))

    reader.pages[page_number - 1].extract_text(visitor_text=visit)
    return runs


def footnote_block(reader: PdfReader, page_number: int) -> Tuple[str, List[Footnote]]:
    """The page's footnotes read from pypdf's runs: text set 2+ pt smaller than the body, below the
    lowest body line, each note introduced by a tiny raised number ("9" at 5.4 pt, then "تفسير
    المزمور 28 ( 29 .)"). Returns the whole block as pypdf emits it - always the last runs of the
    page, so it can be cut from the page text in one piece - and the notes parsed from it."""
    runs = _runs(reader, page_number)
    sizes: Dict[float, int] = {}
    for _, size, _, text in runs:
        sizes[size] = sizes.get(size, 0) + len(text)
    if not sizes:
        return "", []
    body_size = max(sizes, key=sizes.get)
    body_ys = [y for y, size, _, text in runs if size >= body_size - 0.5 and not is_page_number(text.strip())]
    if not body_ys:
        return "", []
    floor = min(body_ys)
    in_zone = [y < floor and size <= body_size - 2 for y, size, _, _ in runs]
    if not any(in_zone):
        return "", []
    first = in_zone.index(True)
    block_runs = [run for run, zone in zip(runs[first:], in_zone[first:]) if zone]
    block = normalize_arabic(" ".join(text for _, _, _, text in block_runs), balance=False)

    def is_number(size: float, text: str) -> bool:
        return size <= body_size * 0.6 and text.strip().isdigit()

    numbers = [(y, int(text.strip())) for y, size, _, text in block_runs if is_number(size, text)]
    by_line: Dict[float, List[str]] = {}
    for y, size, _, text in block_runs:
        if not is_number(size, text):
            key = next((k for k in by_line if abs(k - y) <= 1.5), y)
            by_line.setdefault(key, []).append(text)
    notes: List[Footnote] = []
    for y in sorted(by_line, reverse=True):  # top to bottom
        text = normalize_arabic(" ".join(by_line[y]))
        number = next((n for ny, n in numbers if 0 < ny - y <= 6), None)
        if number is not None and all(note.number != number for note in notes):
            notes.append(Footnote(number, text))
        elif notes:
            notes[-1].text = f"{notes[-1].text} {text}"
    return block, notes


@dataclass
class RunLine:
    """One visual line of pypdf text runs, with the font facts the Arabic segmenters need."""

    y: float
    size: float  # largest run size on the line
    bold: bool  # every Arabic run is bold
    text: str  # normalised, runs joined in pypdf order

    @property
    def is_heading_style(self) -> bool:
        return self.bold or self.size >= 15


def page_lines(reader: PdfReader, page_number: int) -> List[RunLine]:
    """pypdf's text runs grouped into lines by baseline (headings: bold or >= 15 pt; ✞ is 17 pt)."""
    runs: List[Tuple[float, float, bool, str]] = []

    def visit(text, cm, tm, font, size):
        if not text or not text.strip():
            return
        scale = abs(tm[3] * cm[3]) or 1.0
        name = str((font or {}).get("/BaseFont", ""))
        runs.append((round(tm[5] * cm[3] + cm[5], 1), round(size * scale, 1), "Bold" in name, text))

    reader.pages[page_number - 1].extract_text(visitor_text=visit)
    lines: List[RunLine] = []
    for y, size, bold, text in runs:
        # Same baseline, or a large heading whose bracketed word is set slightly raised.
        same_line = lines and (abs(lines[-1].y - y) <= 2.0 or (size >= 15 and lines[-1].size >= 15 and abs(lines[-1].y - y) <= 16))
        if same_line:
            line = lines[-1]
            line.size = max(line.size, size)
            line.bold = line.bold and (bold or not ARABIC_ANY.search(text))
            line.text = f"{line.text} {text}"
        else:
            lines.append(RunLine(y, size, bold or not ARABIC_ANY.search(text), text))
    for line in lines:
        line.text = normalize_arabic(line.text)
    return lines


def extract_pages(key: str, pages: Optional[List[int]] = None) -> List[ArabicPage]:
    source = pdf_source(key)
    reader = PdfReader(str(source.path))
    with pymupdf.open(source.path) as doc:
        numbers = pages or list(range(1, doc.page_count + 1))
        return [extract_page(source, reader, doc, number) for number in numbers]
