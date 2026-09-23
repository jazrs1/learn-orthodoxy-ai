"""Ingest-time saints index (INGEST_PLAN.md §7): one record per saint, English and Arabic.

Sources:
- English entries: the Encyclopedia's headings (saints_en_units).
- Arabic entries: the dictionary's ✞ entries (saints_ar_units), with the Latin name printed under
  many headings ("Hierax", "SS. Maximian and Bonosus").
- English <-> Arabic pairs: the Encyclopedia's alphabetical index (vol. 4 from p. 403), whose lines
  read "ENGLISH HEADING...الاسم العربي".
- Aliases: variant spellings in headings, joint-entry names, the v1 names (by page overlap, so old
  links keep resolving), and the reviewed seed / override tables.
- Commemorations: "[The Synaxarion: 4 Paona]" and "[Butler: March 3]" reference lines.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymupdf

from .sources import pdf_source
from .structure import Unit
from .textnorm import ARABIC_ANY, normalize_arabic, normalize_whitespace

V1_NAMES = Path("data/corpus/v1_saint_names.json")
COPTIC_MONTHS = ("Tout", "Thout", "Baba", "Babah", "Paopi", "Hator", "Hatour", "Hathor", "Kiahk", "Koiak", "Tobi", "Toba", "Touba",
                 "Tubah", "Amshir", "Meshir", "Baramhat", "Paremhat", "Baramouda", "Barmouda", "Paremoude", "Bashans", "Bashons", "Pashans", "Pashons",
                 "Paona", "Baounah", "Paoni", "Epip", "Abib", "Mesra", "Misra", "Mesori", "Nasie", "Nesi")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass
class SaintRecord:
    id: str
    name_en: str = ""
    name_ar: str = ""
    heading_en: str = ""
    heading_ar: str = ""
    descriptor: str = ""
    latin_name: str = ""
    aliases_en: List[str] = field(default_factory=list)
    aliases_ar: List[str] = field(default_factory=list)
    synaxarion_date: str = ""
    western_date: str = ""
    references: List[str] = field(default_factory=list)
    entries: List[Dict[str, object]] = field(default_factory=list)
    linked_by: str = ""  # how the Arabic entry was linked: index-arabic-name | latin-name | ""
    link_score: float = 0.0
    index_heading: str = ""  # the English line of the Encyclopedia's index that gave name_ar
    see: str = ""  # a cross-reference entry ("See the biography of St. Aphraates.")
    see_id: str = ""  # the record it points to; its name is an alias there

    def add_alias(self, name: str, language: str) -> None:
        name = re.sub(r"\s+", " ", (name or "")).strip()
        target = self.aliases_en if language == "en" else self.aliases_ar
        primary = self.name_en if language == "en" else self.name_ar
        if name and name != primary and name not in target:
            target.append(name)


# ---------------------------------------------------------------- keys

NAME_STOP = {"ST", "SS", "STS", "SAINT", "SAINTS", "THE", "FR", "ABBA", "ANBA", "AND", "OF", "A", "AN", "HIS", "HER"}
LINK_THRESHOLD = 0.7  # below this, a wrong Arabic name is likelier than a right one (checked by hand)


def name_tokens(value: str) -> List[str]:
    """ "ABE-FAM (Bifam) EL-TAHAWY (The martyr)" -> ["ABE", "FAM", "BIFAM", "ALTAHAWY"]."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).upper()
    value = re.sub(r"\((?:THE|A|AN)\s[^)]*\)|\[[^\]]*\]", " ", value)
    value = re.sub(r"\b(?:EL|AL)-", "AL", value).replace("FATHER", "FR")
    return [t for t in re.findall(r"[A-Z0-9]+", value) if t not in NAME_STOP]


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def name_similarity(a: List[str], b: List[str]) -> float:
    """Whole-name similarity, weighted towards the first name ("ABBAN (BENUS)" vs "ABBAN, ABBA")."""
    if not a or not b:
        return 0.0
    return 0.6 * _ratio(" ".join(a), " ".join(b)) + 0.4 * _ratio(a[0], b[0])


ROMAN_NUMERAL = re.compile(r"^(?=[IVXL]+$)L?X{0,3}(?:IX|IV|V?I{0,3})$")
ARABIC_ORDINALS = {"الاول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع", "الثامن", "التاسع", "العاشر",
                   "الحادي", "عشر"}


def ordinals_agree(a: List[str], b: List[str]) -> bool:
    """Namesakes differ by one regnal number: "CYRIL IV" is not "CYRIL V", "كيرلس الرابع" is not
    "كيرلس الخامس". When both names carry one, the first ones must be the same (in either script)."""
    def first(tokens: List[str]) -> str:
        for token in tokens:
            if token in ARABIC_ORDINALS:
                return token
            if re.fullmatch(r"\d+(?:ST|ND|RD|TH)?", token):
                return str(int(re.match(r"\d+", token).group()))
            if token and ROMAN_NUMERAL.match(token):
                return str(_roman_value(token))
        return ""
    x, y = first(a), first(b)
    return not x or not y or x == y


def _roman_value(token: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50}
    total = 0
    for index, ch in enumerate(token):
        value = values[ch]
        total += -value if index + 1 < len(token) and values[token[index + 1]] > value else value
    return total


def match_one_to_one(left: List[List[str]], right: List[List[str]], threshold: float = LINK_THRESHOLD) -> Dict[int, Tuple[int, float]]:
    """Best-first one-to-one matching of two name lists; only pairs whose first names agree (>= 0.75)
    and whose regnal numbers agree are scored. Returns {left index: (right index, score)}."""
    by_initial: Dict[str, List[int]] = {}
    for index, tokens in enumerate(right):
        if tokens:
            by_initial.setdefault(tokens[0][:1], []).append(index)
    scored = []
    for i, a in enumerate(left):
        if not a:
            continue
        for k in by_initial.get(a[0][:1], []):
            if _ratio(a[0], right[k][0]) >= 0.75 and ordinals_agree(a, right[k]):
                score = name_similarity(a, right[k])
                if score >= threshold:
                    scored.append((score, i, k))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_left, used_right, out = set(), set(), {}
    for score, i, k in scored:
        if i not in used_left and k not in used_right:
            used_left.add(i)
            used_right.add(k)
            out[i] = (k, score)
    return out


def ar_tokens(value: str) -> List[str]:
    value = normalize_arabic(value)
    value = re.sub("[" + chr(0x064B) + "-" + chr(0x065F) + chr(0x0670) + "]", "", value)
    value = value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
    stop = {"القديس", "القديسه", "القديسين", "القديسان", "الانبا", "انبا", "البابا", "ابا", "مار", "الاب", "و"}
    return [t for t in re.findall("[" + chr(0x0621) + "-" + chr(0x064A) + "]+", value) if t not in stop]


# ---------------------------------------------------------------- the alphabetical index

def index_pairs() -> Tuple[List[Tuple[str, str]], int]:
    """(English heading, Arabic name) from the Encyclopedia's alphabetical index (vol. 4, p. 403 on),
    and the number of English index lines with no Arabic name. Each text block holds one or more
    entries: "LATSON, ST...لاتصون القديس", or the Arabic wrapped onto the next line(s). PyMuPDF's
    plain-text output is used: its dict output drops the Arabic runs on these pages."""
    source = pdf_source("sts4")
    entries: List[List[str]] = []
    with pymupdf.open(source.path) as doc:
        start = next(i for i in range(doc.page_count) if "Alphabetical Index of Saints" in doc[i].get_text("text"))
        for number in range(start, doc.page_count):
            for block in doc[number].get_text("blocks"):
                for line in block[4].splitlines():
                    line = normalize_whitespace(line)
                    if not line or line.startswith(("Saints Names", "Alphabetical Index", "ENCYCLOPEDIA", "Volume ", "Letter ")):
                        continue
                    if re.match(r"^[A-ZÀ-ɏ][A-ZÀ-ɏ'’. -]*[A-ZÀ-ɏ]", line) and re.search(r"[A-Z]{3}", line):
                        match = ARABIC_ANY.search(line)
                        english = line[: match.start()] if match else line
                        entries.append([english.strip().rstrip(".").strip(), line[match.start():] if match else ""])
                    elif entries and ARABIC_ANY.search(line) and not re.search("[A-Za-z]", line):
                        entries[-1][1] = f"{entries[-1][1]} {line}".strip()
    pairs = [(english, normalize_arabic(arabic)) for english, arabic in entries if english and arabic]
    return pairs, sum(1 for _, arabic in entries if not arabic)


# ---------------------------------------------------------------- commemorations

def commemoration_dates(references: List[str]) -> Tuple[str, str]:
    """("4 Paona", "March 3") from reference lines such as "[The Synaxarion: 4 Paona]",
    "[Butler: March 3]", "[Butler's Lives of Saints; May 2]", "[Rev. Baring-Gould: The Lives of the
    Saints, 1877, Dec. 13]". A line may hold several [...] groups; each is read on its own."""
    synaxarion = western = ""
    coptic = "|".join(COPTIC_MONTHS)
    month = r"(?<![A-Za-z])(?:%s)[a-z]*" % "|".join(MONTHS)
    western_date = re.compile(rf"({month})\.?\s+(\d{{1,2}})(?!\d)|(?<!\d)(\d{{1,2}})\s+({month})")
    groups = [g for ref in references for g in (re.findall(r"\[([^\[\]]+)\]?", ref) or [ref])]
    for group in groups:
        group = group.strip()
        if not synaxarion and re.search(r"Synax", group):
            match = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({coptic})\b", group)
            reverse = re.search(rf"(?<![A-Za-z])({coptic})\s+(\d{{1,2}})(?!\d)", group)
            if match:
                synaxarion = f"{match.group(1)} {match.group(2)}"
            elif reverse:
                synaxarion = f"{reverse.group(2)} {reverse.group(1)}"
        if not western and re.search(r"Butler|Baring", group):
            match = western_date.search(group)
            if match:
                western = f"{match.group(1)} {match.group(2)}" if match.group(1) else f"{match.group(4)} {match.group(3)}"
    return synaxarion, western


# ---------------------------------------------------------------- build

def _variants(heading: str) -> List[str]:
    """Spellings in parentheses that are not descriptors: "MACROBIUS (Macrawy)" -> ["Macrawy"]."""
    return [v.strip() for v in re.findall(r"\(([^()]+)\)", heading) if not re.match(r"(?i)^(the|a|an)\s", v.strip())]


def _joint_names(name: str) -> List[str]:
    """"Sts. Aaron and Julius" -> ["St. Aaron", "St. Julius"] (only for plain two-name joint entries)."""
    match = re.match(r"^Sts\.\s+([A-Z][\w'’-]+)\s+and\s+([A-Z][\w'’-]+)$", name)
    return [f"St. {match.group(1)}", f"St. {match.group(2)}"] if match else []


CROSS_REFERENCE = re.compile(r"^(?:see|refer to|cf\.?|راجع|انظر|أنظر)\s", re.IGNORECASE)
AR_LINK_THRESHOLD = 0.8  # Arabic names differ by one ordinal word between popes of the same name

CURATION = Path("data/corpus/saints_curation.json")  # hand-reviewed links and seed targets, each with a reason


def _curation() -> Tuple[Dict[str, str], Dict[str, Optional[str]]]:
    """(English record id -> Arabic dictionary heading, v1 seed English name -> v2 target). A target
    is an English record id, "ar:<Arabic heading>" for a saint only the dictionary has, or null for a
    saint neither book has."""
    data = json.loads(CURATION.read_text(encoding="utf-8"))
    return ({item["en"]: item["ar_heading"] for item in data["links"]},
            {item["name_en"]: item["target"] for item in data["seeds"]})


def is_cross_reference(unit: Unit) -> bool:
    """"AFRAHAT, ST." -> "See the biography of St. Aphraates.", "دونيثوس الغنوصي" -> "راجع دوسيثوس
    الهرطوقي.": a pointer, not a biography."""
    return len(unit.body_text) < 300 and bool(CROSS_REFERENCE.match(unit.body_text.strip()))


def _ar_similarity_ok(unit: Unit, record: "SaintRecord") -> bool:
    """A printed Latin name that clearly names someone else vetoes an Arabic-name match."""
    if not unit.latin_name or not record.heading_en:
        return True
    latin, english = name_tokens(unit.latin_name), name_tokens(record.heading_en)
    return not latin or not english or any(_ratio(a, b) >= 0.75 for a in latin for b in english)


def build(en_units: List[Unit], ar_units: List[Unit]) -> Tuple[List[SaintRecord], Dict[str, str], Dict[str, object]]:
    """Records, a map "doc_id/unit_id" -> saint id, and stats."""
    records: List[SaintRecord] = []
    unit_saint: Dict[str, str] = {}
    seen: Dict[str, int] = {}

    for unit in en_units:
        base = unit.unit_id.removeprefix("saint:")
        seen[base] = seen.get(base, 0) + 1
        record_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
        synaxarion, western = commemoration_dates(unit.references)
        record = SaintRecord(record_id, name_en=unit.saint_name, heading_en=unit.saint_heading, descriptor=unit.descriptor,
                             synaxarion_date=synaxarion, western_date=western, references=list(unit.references))
        if is_cross_reference(unit):
            record.see = unit.body_text.strip()
        for variant in _variants(unit.saint_heading):
            record.add_alias(variant if variant.startswith(("St", "Sts")) else f"St. {variant}", "en")
        for alias in _joint_names(unit.saint_name):
            record.add_alias(alias, "en")
        record.entries.append({"lang": "en", "doc_id": unit.doc_id, "unit_id": unit.unit_id,
                               "page_start": unit.page_start, "page_end": unit.page_end})
        records.append(record)
        unit_saint[f"{unit.doc_id}/{unit.unit_id}"] = record_id

    # 1. English entry <-> the Encyclopedia's own index line, which carries the Arabic name.
    pairs, english_only = index_pairs()
    en_matches = match_one_to_one([name_tokens(r.heading_en) for r in records], [name_tokens(e) for e, _ in pairs])
    for index, (pair_index, score) in en_matches.items():
        records[index].name_ar = pairs[pair_index][1]
        records[index].index_heading = pairs[pair_index][0]

    # 2. Arabic dictionary entry <-> English record: by the Arabic name from the index ...
    english_records = list(records)
    by_id = {r.id: r for r in english_records}
    linked: Dict[int, Tuple[SaintRecord, str, float]] = {}
    reviewed_links, _ = _curation()
    for record_id, heading in reviewed_links.items():
        matches = [i for i, u in enumerate(ar_units) if u.saint_heading == heading]
        if record_id in by_id and len(matches) == 1:
            linked[matches[0]] = (by_id[record_id], "reviewed", 1.0)
    reviewed_records = {id(record) for record, _, _ in linked.values()}
    ar_matches = match_one_to_one([ar_tokens(u.saint_heading) for u in ar_units],
                                  [ar_tokens(r.name_ar) for r in english_records], AR_LINK_THRESHOLD)
    vetoed = 0
    for index, (record_index, score) in ar_matches.items():
        if index in linked or id(english_records[record_index]) in reviewed_records:
            continue
        if _ar_similarity_ok(ar_units[index], english_records[record_index]):
            linked[index] = (english_records[record_index], "index-arabic-name", score)
        else:
            vetoed += 1
    # ... then by the Latin name printed under the Arabic heading.
    taken = {id(record) for record, _, _ in linked.values()}
    open_units = [i for i, u in enumerate(ar_units) if i not in linked and u.latin_name]
    open_records = [r for r in english_records if id(r) not in taken]
    latin_matches = match_one_to_one([name_tokens(ar_units[i].latin_name) for i in open_units],
                                     [name_tokens(r.heading_en) for r in open_records])
    for position, (record_index, score) in latin_matches.items():
        linked[open_units[position]] = (open_records[record_index], "latin-name", score)
    # ... then popes and namesakes: the dictionary heads "مرقس الثاني" where the index has
    # "مرقس الثاني البابا التاسع والأربعون" - a heading of 2+ words that starts exactly one open record's name.
    taken = {id(record) for record, _, _ in linked.values()}
    open_records = [r for r in english_records if id(r) not in taken and r.name_ar]
    for index, unit in enumerate(ar_units):
        tokens = ar_tokens(unit.saint_heading)
        if index in linked or len(tokens) < 2:
            continue
        starts = [r for r in open_records if ar_tokens(r.name_ar)[: len(tokens)] == tokens]
        starts = [r for r in starts if not r.see]
        if len(starts) == 1:
            linked[index] = (starts[0], "index-arabic-prefix", 1.0)
            open_records.remove(starts[0])

    counts = {"reviewed": 0, "index-arabic-name": 0, "latin-name": 0, "index-arabic-prefix": 0, "arabic-only": 0}
    for index, unit in enumerate(ar_units):
        if index in linked:
            record, how, score = linked[index]
            record.linked_by, record.link_score = how, round(score, 3)
        else:
            record, how = SaintRecord(f"ar-{unit.unit_id}", name_ar=unit.saint_heading), "arabic-only"
            records.append(record)
        counts[how] += 1
        record.heading_ar = unit.saint_heading
        record.name_ar = record.name_ar or unit.saint_heading
        if unit.latin_name:
            record.latin_name = unit.latin_name
            record.add_alias(unit.latin_name, "en")
        record.add_alias(unit.saint_heading, "ar")
        if how == "arabic-only" and is_cross_reference(unit):
            record.see = unit.body_text.strip()
        record.entries.append({"lang": "ar", "doc_id": unit.doc_id, "unit_id": unit.unit_id,
                               "page_start": unit.page_start, "page_end": unit.page_end})
        unit_saint[f"{unit.doc_id}/{unit.unit_id}"] = record.id

    resolved = _resolve_cross_references(records)
    v1_stats = _add_v1_aliases(records)
    english = records[: len(en_units)]
    stats = {
        "english_entries": len(en_units),
        "english_cross_references": sum(1 for r in english if r.see),
        "arabic_only_cross_references": sum(1 for r in records if r.see and not r.name_en),
        "cross_references_resolved": resolved,
        "arabic_entries": len(ar_units),
        "records": len(records),
        "index_pairs": len(pairs),
        "index_lines_without_arabic": english_only,
        "english_entries_with_index_arabic_name": len(en_matches),
        "arabic_entries_linked": counts,
        "arabic_matches_vetoed_by_latin_name": vetoed,
        "records_with_both_languages": sum(1 for r in records if r.name_en and any(e["lang"] == "ar" for e in r.entries)),
        "english_entries_with_references": sum(1 for r in english if r.references),
        "with_synaxarion_date": sum(1 for r in records if r.synaxarion_date),
        "with_western_date": sum(1 for r in records if r.western_date),
        **v1_stats,
    }
    return records, unit_saint, stats


def _resolve_cross_references(records: List[SaintRecord]) -> int:
    """"AGREGORIUS OF NYSSA, ST." -> "Cf. Gregory of Nyssa, St.": the pointer's name becomes an alias of
    the entry it points to, and the pointer records which one (`see_id`)."""
    targets = [r for r in records if r.name_en and not r.see]
    target_tokens = [name_tokens(r.heading_en) for r in targets]
    ar_targets = [r for r in records if r.name_ar and not r.see]
    ar_target_tokens = [ar_tokens(r.heading_ar or r.name_ar) for r in ar_targets]
    resolved = 0
    for record in records:
        if not record.see:
            continue
        if not record.name_en:  # an Arabic pointer: "راجع دوسيثوس الهرطوقي."
            wanted = ar_tokens(re.sub(r"^(?:راجع|انظر|أنظر)\s+", "", record.see).split(".")[0])
            scored = sorted(((name_similarity(wanted, tokens), index) for index, tokens in enumerate(ar_target_tokens)
                             if tokens), reverse=True)
            if wanted and scored and scored[0][0] >= 0.8:
                target = ar_targets[scored[0][1]]
                record.see_id = target.id
                target.add_alias(record.name_ar, "ar")
                resolved += 1
            continue
        phrase = re.sub(r"(?i)^(?:see|refer to|cf\.?)\s+(?:the\s+)?(?:biography|life|story)?\s*(?:of\s+)?(?:the\s+martyr\s+)?", "", record.see)
        wanted = name_tokens(phrase.split(".")[0] if not phrase.startswith(("St.", "Sts.")) else phrase.rstrip("."))
        if not wanted:
            continue
        scored = sorted(((name_similarity(wanted, tokens), index) for index, tokens in enumerate(target_tokens)), reverse=True)
        if scored and scored[0][0] >= 0.8 and ordinals_agree(wanted, target_tokens[scored[0][1]]):
            target = targets[scored[0][1]]
            record.see_id = target.id
            target.add_alias(record.name_en, "en")
            resolved += 1
    return resolved


def _covering(records: List[SaintRecord], lang: str, doc_file: str, page: int) -> List[SaintRecord]:
    doc_ids = {s.doc_id for s in [pdf_source(doc_file)]} if doc_file else set()
    out = []
    for record in records:
        for entry in record.entries:
            if entry["lang"] == lang and (not doc_ids or entry["doc_id"] in doc_ids) and entry["page_start"] <= page <= entry["page_end"]:
                out.append(record)
                break
    return out


def _token_overlap(a: List[str], b: List[str]) -> float:
    return len(set(a) & set(b)) / max(1, len(set(a) | set(b)))


def _add_v1_aliases(records: List[SaintRecord]) -> Dict[str, object]:
    """Every v1 display name becomes an alias of the v2 entry on the page v1 found it (best name
    overlap when several entries share the page), so existing links and chips keep resolving."""
    if not V1_NAMES.exists():
        return {"v1_names": "snapshot missing"}
    data = json.loads(V1_NAMES.read_text(encoding="utf-8"))
    mapped_en = unmapped_en = 0
    unmapped_en_names = []
    for item in data["en"]:
        candidates = _covering(records, "en", item["pdf"], item["page"])
        if candidates:
            best = max(candidates, key=lambda r: name_similarity(name_tokens(item["name"]), name_tokens(r.heading_en)))
            best.add_alias(item["name"], "en")
            for alias in item.get("aliases", []):
                best.add_alias(alias, "en")
            mapped_en += 1
        else:
            unmapped_en += 1
            unmapped_en_names.append(item["name"])
    mapped_ar = unmapped_ar = 0
    unmapped_ar_names = []
    seed_only = []
    _, seed_targets = _curation()
    for item in data["ar"]:
        tokens = ar_tokens(item["name"])
        if item.get("source") == "seed" and item.get("name_en") in seed_targets:
            target = seed_targets[item["name_en"]]
            if target is None:  # neither book has an entry: keep the name so it is still recognised
                record = SaintRecord("seed-" + re.sub(r"[^a-z]+", "-", item["name_en"].lower().removeprefix("st. ")).strip("-"),
                                     name_en=item["name_en"], name_ar=item["name"])
                records.append(record)
                seed_only.append(record.id)
            elif target.startswith("ar:"):
                record = next(r for r in records if r.heading_ar == target[3:])
            else:
                record = next(r for r in records if r.id == target)
            for alias in [item["name"], *item.get("aliases", [])]:
                record.add_alias(alias, "ar")
            record.add_alias(item["name_en"], "en")
            exclusive_ar = {item["name"], *item.get("aliases", [])}
            for other in records:  # a reviewed name means one saint ("St. George", "جرجس": the Great Martyr)
                if other is not record:
                    if item["name_en"] in other.aliases_en:
                        other.aliases_en.remove(item["name_en"])
                    other.aliases_ar = [alias for alias in other.aliases_ar if alias not in exclusive_ar]
            mapped_ar += 1
            continue
        candidates = _covering(records, "ar", "full saints arabic.pdf", item["page_start"]) if item.get("page_start") else []
        if not candidates:  # seeds and heading-only names: match by name
            candidates = [r for r in records if r.name_ar and _token_overlap(ar_tokens(r.name_ar), tokens) >= 0.5]
        if not candidates and item.get("name_en"):  # reviewed seeds carry their English name
            wanted = name_tokens(item["name_en"])
            scored = [(name_similarity(wanted, name_tokens(r.name_en)), r) for r in records if r.name_en and not r.see]
            best_score = max((score for score, _ in scored), default=0.0)
            candidates = [r for score, r in scored if score == best_score and score >= 0.85]
        if candidates:
            best = max(candidates, key=lambda r: _token_overlap(ar_tokens(r.name_ar or r.heading_ar), tokens))
            best.add_alias(item["name"], "ar")
            for alias in item.get("aliases", []):
                best.add_alias(alias, "ar")
            if item.get("name_en"):
                best.add_alias(item["name_en"], "en")
            mapped_ar += 1
        else:
            unmapped_ar += 1
            unmapped_ar_names.append(item["name"])
    return {"v1_en_names_mapped": mapped_en, "v1_en_names_unmapped": unmapped_en, "v1_en_unmapped_sample": unmapped_en_names[:15],
            "v1_ar_names_mapped": mapped_ar, "v1_ar_names_unmapped": unmapped_ar, "v1_ar_unmapped_sample": unmapped_ar_names[:15],
            "seed_only_records": seed_only}


def to_json(records: List[SaintRecord], stats: Dict[str, object]) -> Dict[str, object]:
    return {
        "version": "v2",
        "built_by": "python -m ingestion build --corpus v2",
        "stats": stats,
        "saints": [{k: v for k, v in record.__dict__.items() if v not in ("", [], None)} for record in records],
    }
