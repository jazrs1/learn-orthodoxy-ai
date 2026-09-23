"""Structure: turn cleaned pages into logical units (INGEST_PLAN.md §5).

A unit is one catechism question (or a chapter's introductory text), one saint's entry, or one
section of a web article. Each unit is a list of blocks (paragraphs) that keep their page range, so
a chunk cut anywhere inside a unit still knows which pages it came from.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pymupdf
from pypdf import PdfReader

from . import extract_ar, extract_en
from .sources import PdfSource, pdf_source
from .textnorm import ARABIC_ANY, normalize_arabic
from .web import WebPage

TERMINAL = tuple(".!?:;\"'”’)]؟")
BACK_MATTER = ("Bibliography", "Index of Bible Verses", "Index of Questions")


@dataclass
class Block:
    text: str
    page_start: int
    page_end: int
    kind: str = "body"  # body | subheading | references | notes
    subsection: str = ""
    page_breaks: List[Tuple[int, int]] = field(default_factory=list)  # (offset in text, page) where a later page starts

    def split(self, offset: int) -> Tuple["Block", "Block"]:
        """The block cut in two at `offset`, each part keeping its own pages."""
        page = self.page_at(offset)
        head = Block(self.text[:offset].rstrip(), self.page_start, self.page_at(max(0, offset - 1)), self.kind, self.subsection,
                     [(o, p) for o, p in self.page_breaks if o < offset])
        tail = Block(self.text[offset:], page, self.page_end, self.kind, self.subsection,
                     [(o - offset, p) for o, p in self.page_breaks if o > offset])
        return head, tail

    def page_at(self, offset: int) -> int:
        page = self.page_start
        for start, number in self.page_breaks:
            if offset >= start:
                page = number
        return page


@dataclass
class Unit:
    doc_id: str
    language: str
    content_type: str  # catechism | saints | web
    unit_type: str  # question | section_intro | saint_entry | web_section
    unit_id: str
    title: str
    section_path: str = ""
    blocks: List[Block] = field(default_factory=list)
    question_no: int = 0
    saint_heading: str = ""
    saint_name: str = ""
    descriptor: str = ""
    latin_name: str = ""
    references: List[str] = field(default_factory=list)
    url: str = ""

    @property
    def page_start(self) -> int:
        return min((b.page_start for b in self.blocks), default=0)

    @property
    def page_end(self) -> int:
        return max((b.page_end for b in self.blocks), default=0)

    @property
    def body_text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    def add(self, text: str, page: int, kind: str = "body", subsection: str = "", join_across_pages: bool = True) -> None:
        """Append a paragraph; a body paragraph that continues a sentence from the previous page is
        joined to it (so a sentence broken by a page break stays one sentence)."""
        text = text.strip()
        if not text:
            return
        last = self.blocks[-1] if self.blocks else None
        if (join_across_pages and last is not None and kind == "body" and last.kind == "body"
                and page > last.page_end and not last.text.endswith(TERMINAL)):
            offset = len(last.text) + 1
            last.text = f"{last.text} {text}"
            last.page_breaks.append((offset, page))
            last.page_end = page
            return
        self.blocks.append(Block(text, page, page, kind, subsection or (last.subsection if last else "")))


# ---------------------------------------------------------------- English catechism

QUESTION_HEAD = re.compile(r"^(\d{1,4})\.\s+(\S.*)$")
UNBOOKMARKED_HEAD = re.compile(r"^(\d{1,4})\.?\s+(\S.*)$")


def _catechism_outline(source: PdfSource) -> Tuple[List[Tuple[int, str, int]], List[Tuple[str, int, float]], int]:
    """Questions (number, title, page) and level-1 sections (title, page, y) from the bookmarks,
    plus the first back-matter page (bibliography and indexes carry numbered bookmarks too)."""
    with pymupdf.open(source.path) as doc:
        toc = doc.get_toc(simple=False)
        pages = doc.page_count
    back = min((page for level, title, page, _ in toc if level == 1 and title.strip() in BACK_MATTER), default=pages + 1)
    questions, sections = [], []
    for level, title, page, dest in toc:
        match = QUESTION_HEAD.match(title.strip())
        if level == 2 and match and page < back:
            questions.append((int(match.group(1)), title.strip(), page))
        elif level == 1 and page < back:
            sections.append((title.strip(), page, float((dest or {}).get("to", pymupdf.Point(0, 0)).y)))
    return questions, sections, back


def catechism_en_units(doc_id: str) -> Tuple[List[Unit], Dict[str, object]]:
    source = pdf_source(doc_id)
    questions, sections, back = _catechism_outline(source)
    expected = {number for number, _, _ in questions}
    # Content starts at "Book 1" (or "Book 4" in vol. 2); before it are the title, acknowledgments and TOC.
    book_pages = [page for title, page, _ in sections if re.match(r"^Book \d+$", title)]
    first_page = min(book_pages) if book_pages else min((page for _, _, page in questions), default=1)
    pages = extract_en.extract_pages(doc_id, list(range(first_page, back)))
    book_titles: Dict[str, str] = {}
    for page in pages:  # "Book 4" -> "Book 4: Church Worship as a Journey to Heaven" from the running header
        for header in page.removed.get("header", []):
            match = re.match(r"^(Book \d+):", header)
            if match:
                book_titles.setdefault(match.group(1), header)
    footnotes: Dict[int, Dict[int, str]] = {p.page: {n.number: n.text for n in p.footnotes} for p in pages}

    units: List[Unit] = []
    found: List[int] = []
    book, chapter = "", ""
    current: Optional[Unit] = None
    markers: Dict[str, List[int]] = {}
    intro_count = 0
    pending_heading: List[str] = []
    recovered: List[int] = []

    def close() -> None:
        nonlocal current
        if current is not None and current.blocks:
            notes = _collect_notes(markers.get(current.unit_id, []), current, footnotes)
            if notes:
                current.blocks.append(Block("Notes: " + " ".join(notes), current.page_end, current.page_end, "notes", ""))
            if current.unit_type == "question" or len(current.body_text) >= 40:
                units.append(current)
        current = None

    def path() -> str:
        return " › ".join(part for part in (book_titles.get(book, book), chapter) if part)

    for page in pages:
        for group in extract_en.paragraph_groups(page.lines):
            text = extract_en.join_lines(group)
            first = group[0]
            head = QUESTION_HEAD.match(text) if first.bold else None
            unmarked = UNBOOKMARKED_HEAD.match(text)  # "88 Have the rites taken anything from holy tradition?"
            if (not head and unmarked and found and int(unmarked.group(1)) == found[-1] + 1
                    and int(unmarked.group(1)) not in expected and text.endswith("?") and len(text) < 300):
                head = unmarked
                recovered.append(int(unmarked.group(1)))
            if head and (int(head.group(1)) in expected or int(head.group(1)) in recovered) and int(head.group(1)) not in found:
                close()
                number = int(head.group(1))
                found.append(number)
                current = Unit(doc_id, "en", "catechism", "question", f"q{number}", text, path(), question_no=number)
                continue
            if first.size >= 15:  # book / chapter titles ("Book 4", "2", "The Life of Prayer")
                if re.match(r"^Book \d+$", text):
                    close()
                    book, chapter = text, ""
                    pending_heading = []
                    continue
                if text.isdigit():
                    continue
                close()
                pending_heading.append(text)
                # A footnote marker on a title is set in body size, so it stays in the text: "Divine Grace 552".
                chapter = re.sub(r"(?<=[A-Za-z)’”])\s?\d{1,4}$", "", re.sub(r"^\d+\s+", "", " ".join(pending_heading)))
                intro_count += 1
                current = Unit(doc_id, "en", "catechism", "section_intro", f"intro{intro_count}", chapter, path())
                continue
            pending_heading = []
            if current is None:
                continue
            markers.setdefault(current.unit_id, []).extend(m for line in group for m in line.markers)
            current.add(text, page.page)
    close()
    stats = {
        "questions_expected": len(expected),
        "questions_found": len(found),
        "questions_missing": sorted(expected - set(found))[:20],
        "questions_without_bookmark_recovered": recovered,
        "section_intros": sum(1 for u in units if u.unit_type == "section_intro"),
        "printed_pages": {p.page: p.printed_page for p in pages},
    }
    return units, stats


def _collect_notes(numbers: List[int], unit: Unit, footnotes: Dict[int, Dict[int, str]]) -> List[str]:
    """Each marker's note, looked up on the unit's pages and the page after (notes can spill over)."""
    notes = []
    for number in dict.fromkeys(numbers):
        for page in range(unit.page_start, unit.page_end + 2):
            text = footnotes.get(page, {}).get(number)
            if text:
                notes.append(f"[{number}] {text}")
                break
    return notes


# ---------------------------------------------------------------- English saints

REFERENCE_START = re.compile(r"^\[")


DESCRIPTOR = re.compile(r"^(?:the|a|an)(?:\s|$)", re.IGNORECASE)  # "(The martyr)", "(The martyrs)"; "(Macrawy)" is a variant name


def saint_display_name(heading: str) -> Tuple[str, str]:
    """"ABANOUB EL-NEHISSY (The martyr)" -> ("St. Abanoub El-Nehissy", "The martyr");
    "MACARIUS, BISHOP OF JERUSALEM, ST." -> ("St. Macarius, Bishop of Jerusalem", "")."""
    descriptor = ""
    for inner in re.findall(r"\(([^()]*)\)", heading):
        if DESCRIPTOR.match(inner.strip()) and not descriptor:
            descriptor = inner.strip()
    # Parentheses hold the descriptor or a variant spelling ("(Macrawy)"), which the saints index
    # keeps as an alias: neither belongs in the display name.
    base = re.sub(r"\s+([,.])", r"", re.sub(r"\s*\([^()]*\)", "", heading)).strip()
    prefix = "St."
    tail = re.search(r"[,.]\s*(ST|SS|FR|ABBA|POPE|ANBA)\.?\s*$", base)
    if tail:
        prefix = {"ST": "St.", "SS": "Sts.", "FR": "Fr.", "ABBA": "Abba", "POPE": "Pope", "ANBA": "Anba"}[tail.group(1)]
        base = base[: tail.start()].strip()
    small = {"of", "the", "and", "in", "at", "on", "to", "a", "an", "from", "with", "his", "her", "their"}
    words = []
    for index, word in enumerate(re.split(r"(\s+)", base)):
        if word.isspace() or not word:
            words.append(word)
            continue
        lower = word.lower()
        if index and lower in small:
            words.append(lower)
        else:
            words.append("-".join(part[:1].upper() + part[1:].lower() for part in word.split("-")))
    name = "".join(words).strip()
    return (f"{prefix} {name}" if not re.match(r"^(St|Sts|Fr|Abba|Anba|Pope)\b", name) else name), descriptor


def _is_saint_heading(group: List[extract_en.Line]) -> bool:
    return all(line.bold and 13.5 <= line.size <= 14.5 for line in group)


def _is_subheading(group: List[extract_en.Line], text: str) -> bool:
    return all(line.bold and 11.5 <= line.size <= 12.5 for line in group) and text.endswith(":") and len(text.split()) <= 15


def _is_reference(group: List[extract_en.Line], text: str) -> bool:
    return all(line.size <= 11 for line in group) and (REFERENCE_START.match(text) is not None)


def saints_en_units(doc_id: str) -> Tuple[List[Unit], Dict[str, object]]:
    source = pdf_source(doc_id)
    with pymupdf.open(source.path) as doc:
        count = doc.page_count
    pages = extract_en.extract_pages(doc_id)
    stop = next((p.page for p in pages if "Alphabetical Index of Saints" in p.text or p.text.startswith(("NTENTS", "CONTENTS"))), count + 1)
    pages = [p for p in pages if 1 < p.page < stop]
    footnotes = {p.page: {n.number: n.text for n in p.footnotes} for p in pages}
    units: List[Unit] = []
    current: Optional[Unit] = None
    markers: Dict[str, List[int]] = {}
    slugs: Dict[str, int] = {}
    subsection = ""
    heading_open = False  # still reading the lines of the current heading
    references = 0

    def close() -> None:
        nonlocal current
        if current is not None:
            notes = _collect_notes(markers.get(current.unit_id, []), current, footnotes)
            if notes:
                current.blocks.append(Block("Notes: " + " ".join(notes), current.page_end, current.page_end, "notes", ""))
            if current.blocks:
                units.append(current)
        current = None

    for page in pages:
        for group in extract_en.paragraph_groups(page.lines):
            text = extract_en.join_lines(group)
            if _is_saint_heading(group):
                if current is not None and heading_open:  # "(The martyr)" or a wrapped heading line
                    current.saint_heading = f"{current.saint_heading} {text}"
                    current.title = current.saint_heading
                    current.saint_name, current.descriptor = saint_display_name(current.saint_heading)
                    continue
                close()
                name, descriptor = saint_display_name(text)
                ascii_name = "".join(ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch))
                slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower().removeprefix("st. ").removeprefix("sts. ")).strip("-")
                slugs[slug] = slugs.get(slug, 0) + 1
                unit_id = f"saint:{slug}" + (f"-{slugs[slug]}" if slugs[slug] > 1 else "")
                current = Unit(doc_id, "en", "saints", "saint_entry", unit_id, text, "", saint_heading=text,
                               saint_name=name, descriptor=descriptor)
                heading_open, subsection = True, ""
                continue
            heading_open = False
            if current is None:
                continue  # foreword and front matter before the first entry
            markers.setdefault(current.unit_id, []).extend(m for line in group for m in line.markers)
            if _is_subheading(group, text):
                subsection = text.rstrip(":").strip()
                current.add(text, page.page, "subheading", subsection)
            elif _is_reference(group, text) or (current.blocks and current.blocks[-1].kind == "references"
                                                  and not current.blocks[-1].text.rstrip().endswith("]") and all(l.size <= 11 for l in group)):
                if current.blocks and current.blocks[-1].kind == "references" and not current.blocks[-1].text.rstrip().endswith("]"):
                    current.blocks[-1].text = f"{current.blocks[-1].text} {text}"
                    current.references[-1] = current.blocks[-1].text
                else:
                    current.add(text, page.page, "references", subsection)
                    current.references.append(text)
                references += 1
            else:
                current.add(text, page.page, "body", subsection)
    close()
    stats = {"entries": len(units), "pages_used": f"2-{stop - 1}", "reference_lines": references,
             "entries_with_references": sum(1 for u in units if u.references),
             "printed_pages": {p.page: p.printed_page for p in pages}}
    return units, stats


# ---------------------------------------------------------------- Arabic catechism

CONTENTS_ENTRY = re.compile(r"[؟?]\s*(?:-\s*)?\d{1,4}\s?\.?\s")
CONTENTS_MIN_ENTRIES = 15


def catechism_ar_units(doc_id: str) -> Tuple[List[Unit], Dict[str, object]]:
    source = pdf_source(doc_id)
    with pymupdf.open(source.path) as doc:
        toc = doc.get_toc()
    # A footnote marker can be glued to a bookmark title ("998. ما هي أنواع الخوف؟249").
    questions = [(int(QUESTION_HEAD.match(t.strip()).group(1)), re.sub(r"(?<=[؟?])\s*\d+$", "", normalize_arabic(t)), p)
                 for level, t, p in toc if level == 2 and QUESTION_HEAD.match(t.strip())]
    # Bookmark titles sometimes carry a glued footnote marker ("ليس للشيطان سلطان علينا521").
    level1 = [(re.sub(r"(?<=\D)\d+$", "", normalize_arabic(t)).strip(), p) for level, t, p in toc if level == 1 and normalize_arabic(t)]
    first_page = min(p for _, _, p in questions)
    last_page = _arabic_last_content_page(source, level1)
    pages = {p.page: p for p in extract_ar.extract_pages(doc_id, list(range(first_page, last_page + 1)))}
    # This PDF is vol. 2, then vol. 1's table of contents (with two stray question bookmarks), then
    # vol. 1 from Book 3. Contents pages list "question؟ page" 21+ times; body pages at most 10.
    contents = {n for n, p in pages.items() if len(CONTENTS_ENTRY.findall(p.text)) >= CONTENTS_MIN_ENTRIES}
    stray = [(q, t, p) for q, t, p in questions if p in contents]
    questions = [(q, t, p) for q, t, p in questions if p not in contents]
    by_page: Dict[int, List[Tuple[int, str]]] = {}
    for number, title, page in questions:
        by_page.setdefault(page, []).append((number, title))

    units: List[Unit] = []
    found, missing = [], []
    current: Optional[Unit] = None
    book = chapter = ""

    def close() -> None:
        nonlocal current
        if current is not None and current.blocks:
            units.append(current)
        current = None

    for number in sorted(pages):
        if number in contents:
            close()
            continue
        page = pages[number]
        text = page.text
        for title, section_page in level1:  # book and chapter titles on this page: path, not body
            if section_page == number:
                if "الكتاب" in title.split(" ")[0:2]:
                    book, chapter = title, ""
                else:
                    chapter = re.sub(r"^\d+\.\s*", "", title)
                text = text.replace(title, " ", 1)
        cuts: List[Tuple[int, int, str]] = []
        for q_number, title in by_page.get(number, []):
            position = text.find(title)
            if position < 0:
                match = re.search(rf"(?<![\d.]){q_number}\s*\.\s", text)
                position = match.start() if match else -1
            if position < 0:
                missing.append(q_number)
                continue
            cuts.append((position, q_number, title))
        cuts.sort()
        spans = [(0, cuts[0][0] if cuts else len(text), None)] + [
            (start, cuts[i + 1][0] if i + 1 < len(cuts) else len(text), (q, title)) for i, (start, q, title) in enumerate(cuts)
        ]
        for start, end, question in spans:
            segment = text[start:end]
            if question is not None:
                close()
                q_number, title = question
                found.append(q_number)
                path = " › ".join(p for p in (book, chapter) if p)
                current = Unit(doc_id, "ar", "catechism", "question", f"q{q_number}", title, path, question_no=q_number)
                segment = _strip_prefix(segment, title).lstrip(" ؟?:")
                current.references = []
            if current is None:
                continue
            notes = [f"[{n}] {t}" for o, n in page.marker_offsets if start <= o < end
                     for t in [next((f.text for f in page.footnotes if f.number == n), "")] if t]
            current.add(segment, number)
            if notes:
                current.references.extend(notes)
    close()
    recovered = _recover_unbookmarked(units, set(found))
    found.extend(recovered)
    for unit in units:  # footnotes (Latin patristic references) follow their question, as in English
        if unit.references:
            unit.blocks.append(Block("Notes: " + " ".join(unit.references), unit.page_end, unit.page_end, "notes"))
            unit.references = []
    stats = {"questions_expected": len({q for q, _, _ in questions}), "bookmarks": len(questions) + len(stray),
             "bookmarks_on_contents_pages": [q for q, _, _ in stray], "contents_pages": f"{min(contents)}-{max(contents)}" if contents else "",
             "questions_found": len(set(found)),
             "question_numbers_absent": sorted(set(range(1, max(found, default=0) + 1)) - set(found)),
             "questions_missing": sorted(set(missing) - set(found))[:20],
             "questions_without_bookmark_recovered": recovered,
             "printed_pages": {n: p.printed_page for n, p in pages.items()}}
    return units, stats


def _recover_unbookmarked(units: List[Unit], found: set) -> List[int]:
    """Questions the PDF forgot to bookmark ("264. ما هي علاقة العناية الإلهية بالنعمة الإلهية؟")
    sit inside the previous question's text: split them out as their own units."""
    recovered = []
    index = 0
    while index < len(units):
        unit = units[index]
        number = unit.question_no + 1
        if unit.unit_type != "question" or number in found:
            index += 1
            continue
        split = None
        for block_index, block in enumerate(unit.blocks):
            if block.kind != "body":
                continue
            match = re.search(rf"(?<![\d.]){number}\s?\.\s(?=[^\d\s])", block.text)
            if match:
                question_end = block.text.find("؟", match.end())
                if 0 < question_end - match.end() < 250:
                    split = (block_index, match.start(), block.text[match.start(): question_end + 1])
                    break
        if split is None:
            index += 1
            continue
        block_index, offset, title = split
        block = unit.blocks[block_index]
        head, tail = block.split(offset)
        new = Unit(unit.doc_id, unit.language, unit.content_type, "question", f"q{number}", title, unit.section_path,
                   question_no=number)
        before = len(tail.text)
        tail.text = tail.text[len(title):].lstrip(" ؟?:")
        shift = before - len(tail.text)
        tail.page_breaks = [(o - shift, p) for o, p in tail.page_breaks if o - shift > 0]
        new.blocks = [tail] + unit.blocks[block_index + 1:]
        unit.blocks = unit.blocks[:block_index] + ([head] if head.text.strip() else [])
        units.insert(index + 1, new)
        found.add(number)
        recovered.append(number)
        index += 1
    return recovered


def _strip_prefix(segment: str, title: str) -> str:
    """Remove the question title from the start of its text, ignoring spacing differences between
    the bookmark and pypdf ("الكنسية ؟" vs "الكنسية؟")."""
    wanted = len(re.sub(r"\s+", "", title))
    seen = 0
    for index, ch in enumerate(segment):
        if not ch.isspace():
            seen += 1
        if seen == wanted:
            if re.sub(r"\s+", "", segment[: index + 1]) == re.sub(r"\s+", "", title):
                return segment[index + 1:]
            break
    return segment


def _arabic_last_content_page(source: PdfSource, level1: List[Tuple[str, int]]) -> int:
    with pymupdf.open(source.path) as doc:
        count = doc.page_count
    back = [p for title, p in level1 if any(word in title for word in ("المراجع", "فهرس", "الفهرس"))]
    return (min(back) - 1) if back else count


# ---------------------------------------------------------------- Arabic saints

ENTRY_MARK = chr(0x271E)  # ✞


def _heading_candidates(lines: List["extract_ar.RunLine"], top_of_page: bool = False) -> List[Tuple[str, str, bool]]:
    """(heading, Latin name, set in heading type) for every line that follows a ✞ - or, for an entry
    whose ✞ ended the previous page, the first lines of this page."""
    starts = [i + 1 for i, line in enumerate(lines) if ENTRY_MARK in line.text]
    if top_of_page:
        starts.append(0)
    out = []
    for start in starts:
        rest = [l for l in lines[start: start + 4] if ARABIC_ANY.search(l.text) or re.search(r"[A-Za-z]", l.text)]
        if not rest or not ARABIC_ANY.search(rest[0].text) or len(rest[0].text.split()) > 10:
            continue
        latin = ""
        if len(rest) > 1 and not ARABIC_ANY.search(rest[1].text) and re.search(r"[A-Za-z]", rest[1].text):
            latin = re.sub(r"\s+([.)])", r"\1", rest[1].text).strip(" .")
        out.append((rest[0].text, latin, rest[0].is_heading_style))
    return out


def _starts_with(body: str, phrase: str) -> Optional[int]:
    """End offset of `phrase` at the start of `body`, ignoring how pypdf spaced it."""
    compact = re.sub(r"\s+", "", phrase)
    if not compact:
        return None
    match = re.match(r"\s*" + r"\s*".join(re.escape(c) for c in compact), body)
    return match.end() if match else None


def _take_heading(body: str, candidates: List[Tuple[str, str, bool]]) -> Tuple[str, str, str, str]:
    """(heading, Latin name, rest of body, how) for an entry body. The heading is the candidate the
    body starts with (the longest if several); failing that, the words before the first Latin word
    when there are at most seven, else the first four words."""
    best = None
    for heading, latin, styled in candidates:
        end = _starts_with(body, heading)
        if end is not None and (best is None or end > best[3]):
            best = (heading, latin, styled, end)
    if best is not None:
        heading, latin, styled, end = best
        rest = body[end:].strip()
        if latin:
            latin_end = _starts_with(rest, latin)
            if latin_end is not None:
                rest = rest[latin_end:].lstrip(" .").strip()
        return heading, latin, rest, "font" if styled else "first-line"
    words = body.split(" ")
    latin_at = next((i for i, w in enumerate(words[:8]) if re.match(r"^[A-Za-z]", w)), None)
    if latin_at:
        heading = " ".join(words[:latin_at])
        tail = words[latin_at:]
        latin_words = []
        while tail and re.match(r"^[A-Za-z.()]+[.,]?$", tail[0]):
            latin_words.append(tail.pop(0))
        return heading, " ".join(latin_words).strip(" .,"), " ".join(tail), "before-latin"
    return " ".join(words[:4]), "", " ".join(words[4:]), "first-words"


def saints_ar_units(doc_id: str) -> Tuple[List[Unit], Dict[str, object]]:
    source = pdf_source(doc_id)
    reader = PdfReader(str(source.path))
    with pymupdf.open(source.path) as doc:
        index_start = min((p for _, t, p in doc.get_toc() if t.strip().startswith("فهرس")), default=doc.page_count + 1)
    # The alphabetical index ("فهرس حرف ...") and the appendices after it hold no entries.
    pages = extract_ar.extract_pages(doc_id, list(range(1, index_start)))
    units: List[Unit] = []
    current: Optional[Unit] = None
    heading_sources: Dict[str, int] = {}

    def start_entry(body: str, page_number: int, candidates) -> Unit:
        heading, latin, rest, how = _take_heading(body, candidates)
        heading_sources[how] = heading_sources.get(how, 0) + 1
        unit = Unit(doc_id, "ar", "saints", "saint_entry", f"e{len(units) + 1:04d}", heading, "",
                    saint_heading=heading, saint_name=heading, latin_name=latin)
        unit.add(rest, page_number, join_across_pages=False)
        return unit

    pending = False  # a ✞ ended the previous page: the entry's heading opens this page
    for page in pages:
        text = page.text
        if ENTRY_MARK not in text and current is None and not pending:
            continue
        lines = extract_ar.page_lines(reader, page.page) if (ENTRY_MARK in text or pending) else []
        candidates = _heading_candidates(lines, top_of_page=pending)
        pieces = text.split(ENTRY_MARK)
        if pending and pieces[0].strip():
            current = start_entry(pieces[0].strip(), page.page, candidates)
            pending = False
        elif current is not None and pieces[0].strip():
            current.add(pieces[0], page.page)
        for piece in pieces[1:]:
            if current is not None and not pending:
                units.append(current)
            body = piece.strip()
            if not body:
                pending, current = True, None
                continue
            pending = False
            current = start_entry(body, page.page, candidates)
    if current is not None:
        units.append(current)
    stats = {"entries": len(units), "pages_used": f"1-{index_start - 1}", "headings_by": heading_sources,
             "entry_marks": sum(p.text.count(ENTRY_MARK) for p in pages),
             "entries_with_latin_name": sum(1 for u in units if u.latin_name),
             "printed_pages": {p.page: p.printed_page for p in pages}}
    return units, stats


# ---------------------------------------------------------------- Web

WEB_NOTE = re.compile(r"^\[\d+\]\s")


def _endnote_runs(paragraphs: List[str]) -> List[bool]:
    """Which paragraphs belong to an endnote list: 3+ consecutive short "[139] J. Danielou: ..." lines.
    A body paragraph that merely opens with a marker ("[610] In fact, Dioscorus ...") stays."""
    flags = [bool(WEB_NOTE.match(p)) and len(p) < 300 for p in paragraphs]
    out = [False] * len(paragraphs)
    start = 0
    while start < len(flags):
        end = start
        while end < len(flags) and flags[end]:
            end += 1
        if end - start >= 3:
            out[start:end] = [True] * (end - start)
        start = end + 1 if end == start else end
    return out


def web_units(page: WebPage) -> List[Unit]:
    """One unit per h2/h3 section; the article's endnote lists become one "Notes" unit, so they do
    not fill the last sections' chunks with bare citations."""
    units = []
    notes = Unit(f"web-{page.url_hash}", "en", "web", "web_notes", "notes", "Notes", page.title, url=page.url)
    for index, section in enumerate(page.sections):
        unit = Unit(f"web-{page.url_hash}", "en", "web", "web_section", f"s{index}",
                    section.heading or page.title, page.title, url=page.url)
        for paragraph, is_note in zip(section.paragraphs, _endnote_runs(section.paragraphs)):
            (notes if is_note else unit).blocks.append(Block(paragraph, 0, 0, "body"))
        if unit.blocks:
            units.append(unit)
    if notes.blocks:
        units.append(notes)
    return units


def document_units(doc_id: str) -> Tuple[List[Unit], Dict[str, object]]:
    source = pdf_source(doc_id)
    if source.content_type == "catechism":
        return catechism_en_units(doc_id) if source.language == "en" else catechism_ar_units(doc_id)
    return saints_en_units(doc_id) if source.language == "en" else saints_ar_units(doc_id)
