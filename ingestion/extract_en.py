"""English PDF extraction with PyMuPDF (INGEST_PLAN.md §2.1, §3).

Each page becomes a `Page`: the body as layout lines (text, size, bold, position) plus assembled
paragraphs, with running headers, the printed page number, footnotes and superscript footnote
markers moved out of the body into their own fields. Structure (questions, saint entries) is
applied later on top of the lines; this module only decides what is body text.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import pymupdf

from .sources import PdfSource, pdf_source
from .textnorm import digits_key, is_page_number, normalize_whitespace

EXTRACTOR = f"pymupdf-{pymupdf.VersionBind}"

SUPERSCRIPT_FLAG = 1
BOLD_FLAG = 16
HEADER_BAND = 0.075  # top of page (fraction of height) where running headers sit
HEADER_MIN_REPEATS = 3  # a top-band line repeated on this many pages is a running header
FOOTNOTE_START = re.compile(r"^(\d{1,4})\s+(\S.*)$")


@dataclass
class Line:
    text: str
    size: float  # dominant font size (by characters)
    bold: bool
    y0: float  # fractions of the page height
    y1: float
    x0: float
    block: int
    markers: List[int] = field(default_factory=list)  # footnote numbers removed from this line

    @property
    def is_heading_style(self) -> bool:
        return self.bold


@dataclass
class Footnote:
    number: int
    text: str


@dataclass
class Page:
    doc_id: str
    page: int  # PDF page index, 1-based (what the eval and citations use)
    printed_page: Optional[str]
    lines: List[Line]  # body lines, reading order
    footnotes: List[Footnote]
    removed: Dict[str, List[str]]  # what cleaning took out, for tests and debugging
    body_size: float

    @property
    def text(self) -> str:
        return "\n\n".join(paragraphs(self.lines, self.body_size))

    @property
    def markers(self) -> List[int]:
        return [marker for line in self.lines for marker in line.markers]


def _span_is_bold(span: dict) -> bool:
    return bool(span["flags"] & BOLD_FLAG) or "Bold" in span["font"]


def _raw_lines(page: "pymupdf.Page") -> List[Tuple[dict, dict, int]]:
    height = page.rect.height or 1.0
    out = []
    for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        for line in block.get("lines", []):
            out.append((line, block, height))
    return out


def _make_line(line: dict, block: dict, height: float, body_size: float) -> Optional[Line]:
    spans = [s for s in line["spans"] if s["text"]]
    visible = [s for s in spans if s["text"].strip()]
    if not visible:
        return None
    parts: List[str] = []
    markers: List[int] = []
    for span in spans:
        text = span["text"]
        # Footnote markers are raised, smaller digits; other superscripts ("17th") are kept.
        if span["flags"] & SUPERSCRIPT_FLAG and text.strip().isdigit() and span["size"] < body_size - 1:
            markers.append(int(text.strip()))
            continue
        parts.append(text)
    weights = Counter()
    for span in visible:
        weights[round(span["size"], 1)] += len(span["text"].strip())
    text = normalize_whitespace("".join(parts))
    if not text:
        return None
    x0, y0, x1, y1 = line["bbox"]
    return Line(
        text=text,
        size=weights.most_common(1)[0][0],
        bold=all(_span_is_bold(s) for s in visible),
        y0=round(y0 / height, 4),
        y1=round(y1 / height, 4),
        x0=round(x0, 1),
        block=block["number"],
        markers=markers,
    )


@lru_cache(maxsize=16)
def document_profile(file: str) -> Tuple[float, Dict[str, int]]:
    """Body font size (most characters) and how often each top-band line repeats in the PDF."""
    source = pdf_source(file)
    sizes: Counter = Counter()
    top_keys: Counter = Counter()
    with pymupdf.open(source.path) as doc:
        for index, page in enumerate(doc):
            height = page.rect.height or 1.0
            clip = None if index % 7 == 0 else pymupdf.Rect(0, 0, page.rect.width, height * HEADER_BAND)
            for block in page.get_text("dict", clip=clip, flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    if not text:
                        continue
                    if clip is None:
                        for span in line["spans"]:
                            sizes[round(span["size"])] += len(span["text"].strip())
                    if line["bbox"][1] / height < HEADER_BAND:
                        top_keys[digits_key(text)] += 1
    body_size = float(sizes.most_common(1)[0][0]) if sizes else 12.0
    return body_size, dict(top_keys)


def _footnote_region(lines: List[Line], body_size: float) -> int:
    """Index where the footnote block starts (len(lines) when there is none).

    A footnote block is the run of small lines at the bottom of the page whose first line starts
    with a note number. Lines are in reading order, so it is a suffix of the list."""
    start = len(lines)
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].size <= body_size - 1:
            start = index
        else:
            break
    while start < len(lines) and not FOOTNOTE_START.match(lines[start].text):
        start += 1
    return start


def _parse_footnotes(lines: List[Line]) -> List[Footnote]:
    """A line starting with a number opens a new note only when the number follows the previous
    note (+1 to +3); otherwise it continues the note ("30 on Jesus' promise," is a wrapped line)."""
    notes: List[Footnote] = []
    for line in lines:
        match = FOOTNOTE_START.match(line.text)
        number = int(match.group(1)) if match else None
        if match and (not notes or notes[-1].number < number <= notes[-1].number + 3):
            notes.append(Footnote(number, match.group(2)))
        elif notes:
            notes[-1].text = f"{notes[-1].text} {line.text}"
    return notes


def extract_page(source: PdfSource, doc: "pymupdf.Document", page_number: int) -> Page:
    body_size, top_keys = document_profile(source.file)
    page = doc[page_number - 1]
    lines = [ln for ln in (_make_line(l, b, h, body_size) for l, b, h in _raw_lines(page)) if ln]
    lines.sort(key=lambda ln: (ln.y0, ln.x0))
    removed: Dict[str, List[str]] = {"header": [], "page_number": [], "footnote": []}

    printed: Optional[str] = None
    for candidate in (lines[:1] + lines[-1:]) if lines else []:
        if is_page_number(candidate.text) and candidate in lines:
            printed = candidate.text
            removed["page_number"].append(candidate.text)
            lines.remove(candidate)
            break

    kept: List[Line] = []
    removed["divider"] = []
    for line in lines:
        # The Encyclopedia opens each letter with a large single capital ("G"): decoration, not text.
        if len(line.text) == 1 and line.text.isalpha() and line.size >= body_size + 6:
            removed["divider"].append(line.text)
            continue
        # Running headers repeat across pages. A single small line at the top is usually the tail
        # of the previous entry's references ("[The Synaxarion: 4 Paona]"), which must stay.
        repeated = top_keys.get(digits_key(line.text), 0) >= HEADER_MIN_REPEATS
        if line.y0 < HEADER_BAND and repeated:
            removed["header"].append(line.text)
            continue
        kept.append(line)

    cut = _footnote_region(kept, body_size)
    footnotes = _parse_footnotes(kept[cut:])
    removed["footnote"] = [line.text for line in kept[cut:]]
    body = kept[:cut]
    return Page(source.doc_id, page_number, printed, body, footnotes, removed, body_size)


def extract_pages(key: str, pages: Optional[List[int]] = None) -> List[Page]:
    source = pdf_source(key)
    with pymupdf.open(source.path) as doc:
        numbers = pages or list(range(1, doc.page_count + 1))
        return [extract_page(source, doc, number) for number in numbers]


def paragraphs(lines: List[Line], body_size: float) -> List[str]:
    """Join layout lines into paragraphs: a new paragraph at a new block or a change of style
    (heading vs body); a hyphen at a line end joins the word when the next line starts lower-case."""
    result: List[str] = []
    current = ""
    previous: Optional[Line] = None
    for line in lines:
        style_changed = previous is not None and (
            line.bold != previous.bold or abs(line.size - previous.size) >= 1
        )
        if previous is None or line.block != previous.block or style_changed:
            if current:
                result.append(current)
            current = line.text
        elif current.endswith("-") and not current.endswith("--") and line.text[:1].islower():
            current = current[:-1] + line.text
        else:
            current = f"{current} {line.text}"
        previous = line
    if current:
        result.append(current)
    return result
