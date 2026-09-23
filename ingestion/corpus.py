"""The v2 corpus (INGEST_PLAN.md §5, §6): units -> chunks with headers and flat metadata.

    python -m ingestion build --corpus v2 --dry-run

writes, with no OpenAI calls:
- build/corpus/v2/chunks.jsonl          every chunk: id, document (header + body), metadata (gitignored)
- data/corpus/v2/saints_index.json      the ingest-time saints index (§7)
- data/corpus/v2/manifest.json          counts, per-document text hashes, chunk-ID list hash, versions
- data/corpus/v2/stats.json             sizes, coverage against the books' own indexes, gaps
- data/corpus/v2/SAMPLES.md             ten chunks of each type, for review
"""

from __future__ import annotations

import hashlib
import json
import platform
import random
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from corpus_runtime import ids_sha1, verify_store

from . import extract_ar, extract_en, saints_index
from .chunk import LIMITS, chunk_text, chunk_unit
from .embed import count_tokens
from .sources import PDF_SOURCES, WEBSITE_SOURCE_URLS, pdf_source
from .structure import Unit, document_units, web_units
from .web import extract_page as extract_web_page

CORPUS_VERSION = "v2"
BUILD_DIR = Path("build/corpus/v2")
DATA_DIR = Path("data/corpus/v2")
WEB_WORK = "Mind of Christ Light"
NORMALIZER = {"en": "nfc-whitespace-v1", "ar": "nfkc+fold-v1"}
WEB_EXTRACTOR = "requests+bs4"
SAMPLE_TYPES = ("catechism-en", "catechism-ar", "saints-en", "saints-ar", "web")
COLLECTIONS = {"en": "orthodox_pdfs_v2", "ar": "orthodox_arabic_pdfs_v2"}  # INGEST_PLAN.md §9.1
MANIFEST = DATA_DIR / "manifest.json"


@dataclass
class Chunk:
    id: str
    document: str  # header + body: what is embedded and stored
    metadata: Dict[str, object]


# ---------------------------------------------------------------- units

def pdf_units(doc_ids: Optional[Iterable[str]] = None) -> Tuple[Dict[str, List[Unit]], Dict[str, Dict[str, object]]]:
    units: Dict[str, List[Unit]] = {}
    stats: Dict[str, Dict[str, object]] = {}
    for source in PDF_SOURCES:
        if doc_ids is None or source.doc_id in doc_ids:
            units[source.doc_id], stats[source.doc_id] = document_units(source.doc_id)
    return units, stats


def website_units() -> Tuple[Dict[str, List[Unit]], Dict[str, Dict[str, object]]]:
    units: Dict[str, List[Unit]] = {}
    stats: Dict[str, Dict[str, object]] = {}
    for url in WEBSITE_SOURCE_URLS:
        page = extract_web_page(url)
        doc_units = web_units(page)
        doc_id = f"web-{page.url_hash}"
        units[doc_id] = doc_units
        stats[doc_id] = {"url": page.url, "title": page.title, "sections": len(page.sections), "content_sha1": page.content_sha1}
    return units, stats


# ---------------------------------------------------------------- headers

def chunk_header(unit: Unit, saint_name: str = "") -> str:
    """The line that opens every chunk of a unit, so a continuation chunk still says what it is about
    (AUDIT C7a): "Catechism, Book 4 › The Life of Prayer — 896. What is prayer?"."""
    if unit.content_type == "catechism":
        work, comma = ("Catechism", ",") if unit.language == "en" else ("الكاتيكيزم", "،")
        where = f"{work}{comma} {unit.section_path}" if unit.section_path else work
        return where if unit.unit_type == "section_intro" else f"{where} — {unit.title}"
    if unit.content_type == "saints":
        if unit.language == "en":
            return f"Saint: {unit.saint_heading}"
        return f"سيرة: {unit.saint_heading}"
    return f"{unit.section_path} — {unit.title}" if unit.title and unit.title != unit.section_path else unit.section_path


def _with_subsection(header: str, subsection: str) -> str:
    return f"{header} — {subsection}" if subsection and not header.endswith(subsection) else header


# ---------------------------------------------------------------- chunks

def _source_fields(unit: Unit) -> Dict[str, object]:
    if unit.content_type == "web":
        return {"source_type": "website", "pdf": "", "url": unit.url, "work": WEB_WORK, "volume": 0, "author": "",
                "extractor": WEB_EXTRACTOR}
    source = pdf_source(unit.doc_id)
    extractor = extract_en.EXTRACTOR if source.language == "en" else extract_ar.EXTRACTOR
    return {"source_type": "pdf", "pdf": source.file, "url": "", "work": source.work, "volume": source.volume,
            "author": source.author, "extractor": extractor}


def unit_chunks(unit: Unit, printed: Dict[int, Optional[str]], saint: Optional[saints_index.SaintRecord]) -> List[Chunk]:
    raws = chunk_unit(unit)
    header = chunk_header(unit)
    base = _source_fields(unit)
    saint_name = ""
    if saint is not None:
        saint_name = (saint.name_en if unit.language == "en" else saint.name_ar) or unit.saint_name
    elif unit.content_type == "saints":
        saint_name = unit.saint_name
    out = []
    for index, raw in enumerate(raws, start=1):
        subsection = next((p.subsection for p in raw.pieces if p.subsection), "")
        body = chunk_text(raw)
        document = f"{_with_subsection(header, subsection)}\n\n{body}"
        page_start = min(p.page_start for p in raw.pieces)
        page_end = max(p.page_end for p in raw.pieces)
        chunk_id = f"{CORPUS_VERSION}:{unit.doc_id}:{unit.unit_id}:c{index}"
        metadata: Dict[str, object] = {
            "chunk_id": chunk_id,
            "corpus_version": CORPUS_VERSION,
            "doc_id": unit.doc_id,
            **base,
            "language": unit.language,
            "content_type": unit.content_type,
            "unit_type": unit.unit_type,
            "unit_id": unit.unit_id,
            "unit_title": unit.title,
            "section_path": unit.section_path,
            "subsection": subsection,
            "question_no": unit.question_no,
            "saint_id": saint.id if saint is not None else "",
            "saint_name": saint_name,
            "ref_book": "", "ref_chapter_start": 0, "ref_verse_start": 0, "ref_chapter_end": 0, "ref_verse_end": 0,
            "page_start": page_start,
            "page_end": page_end,
            "printed_page_start": printed.get(page_start) or "",
            "printed_page_end": printed.get(page_end) or "",
            "chunk_index": index,
            "chunk_count": len(raws),
            "token_count": count_tokens(document),
            "normalizer": NORMALIZER[unit.language],
            "text_sha1": hashlib.sha1(document.encode("utf-8")).hexdigest(),
            # commemorations from the Encyclopedia's reference lines ("[The Synaxarion: 4 Paona]")
            "synaxarion_date": saint.synaxarion_date if saint is not None else "",
            "western_date": saint.western_date if saint is not None else "",
        }
        out.append(Chunk(chunk_id, document, metadata))
    return out


# ---------------------------------------------------------------- build

def build(*, with_web: bool = True, doc_ids: Optional[Iterable[str]] = None, log=print) -> Dict[str, object]:
    """Extract, segment, index saints and chunk everything; write the dry-run outputs."""
    units, unit_stats = pdf_units(doc_ids)
    log(f"segmented {sum(len(u) for u in units.values())} units from {len(units)} PDFs")
    web_stats: Dict[str, Dict[str, object]] = {}
    if with_web:
        web, web_stats = website_units()
        units.update(web)
        log(f"segmented {sum(len(u) for u in web.values())} sections from {len(web)} web pages")

    en_saint_units = [u for doc_id in ("sts1", "sts2", "sts3", "sts4") for u in units.get(doc_id, [])]
    ar_saint_units = units.get("ar-sts", [])
    records, unit_saint, index_stats = saints_index.build(en_saint_units, ar_saint_units)
    by_id = {r.id: r for r in records}
    log(f"saints index: {len(records)} records")

    chunks: List[Chunk] = []
    skipped: Dict[str, List[str]] = {"cross_reference": [], "empty": []}
    for doc_id, doc_units in units.items():
        printed = {int(k): v for k, v in unit_stats.get(doc_id, {}).get("printed_pages", {}).items()}
        for unit in doc_units:
            saint = by_id.get(unit_saint.get(f"{doc_id}/{unit.unit_id}", ""))
            if unit.content_type == "saints" and saints_index.is_cross_reference(unit):
                skipped["cross_reference"].append(f"{doc_id}/{unit.unit_id}")  # a pointer, kept as an alias (§7)
                continue
            if not unit.body_text.strip():
                skipped["empty"].append(f"{doc_id}/{unit.unit_id}")
                continue
            chunks.extend(unit_chunks(unit, printed, saint))
    ids = [c.id for c in chunks]
    if len(ids) != len(set(ids)):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})[:10]
        raise RuntimeError(f"duplicate chunk ids: {duplicates}")
    log(f"{len(chunks)} chunks")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (BUILD_DIR / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps({"id": chunk.id, "document": chunk.document, "metadata": chunk.metadata}, ensure_ascii=False) + "\n")
    _write_json(DATA_DIR / "saints_index.json", saints_index.to_json(records, index_stats))
    stats = corpus_stats(chunks, units, unit_stats, web_stats, index_stats, skipped)
    _write_json(DATA_DIR / "stats.json", stats)
    _write_json(DATA_DIR / "manifest.json", manifest(chunks, web_stats))
    (DATA_DIR / "SAMPLES.md").write_text(samples_markdown(chunks), encoding="utf-8")
    return stats


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def chunk_kind(metadata: Dict[str, object]) -> str:
    return "web" if metadata["content_type"] == "web" else f"{metadata['content_type']}-{metadata['language']}"


def _distribution(values: List[int]) -> Dict[str, object]:
    if not values:
        return {}
    ordered = sorted(values)

    def pct(p: float) -> int:
        return ordered[min(len(ordered) - 1, int(p * (len(ordered) - 1) + 0.5))]

    return {"n": len(values), "min": ordered[0], "p10": pct(0.10), "p50": pct(0.50), "p90": pct(0.90), "max": ordered[-1],
            "mean": round(statistics.mean(values), 1), "total": sum(values)}


def _body_size(chunk: Chunk) -> int:
    body = chunk.document.split("\n\n", 1)[1] if "\n\n" in chunk.document else chunk.document
    return count_tokens(body) if chunk.metadata["language"] == "en" else len(body.split())


def corpus_stats(chunks: List[Chunk], units: Dict[str, List[Unit]], unit_stats: Dict[str, Dict[str, object]],
                 web_stats: Dict[str, Dict[str, object]], index_stats: Dict[str, object],
                 skipped: Dict[str, List[str]]) -> Dict[str, object]:
    kinds: Dict[str, List[Chunk]] = {}
    for chunk in chunks:
        kinds.setdefault(chunk_kind(chunk.metadata), []).append(chunk)
    by_kind = {}
    for kind, items in sorted(kinds.items()):
        language = items[0].metadata["language"]
        minimum, target, maximum = LIMITS[language]
        body_sizes = [_body_size(c) for c in items]
        by_kind[kind] = {
            "chunks": len(items),
            "units": len({(c.metadata["doc_id"], c.metadata["unit_id"]) for c in items}),
            "tokens_cl100k_with_header": _distribution([int(c.metadata["token_count"]) for c in items]),
            ("body_tokens" if language == "en" else "body_words"): _distribution(body_sizes),
            "size_limits": {"unit": "cl100k tokens" if language == "en" else "words", "min": minimum, "target": target, "max": maximum},
            "over_max": sum(1 for s in body_sizes if s > maximum),
            "under_min_whole_unit": sum(1 for c, s in zip(items, body_sizes) if s < minimum and c.metadata["chunk_count"] == 1),
            "under_min_in_multi_chunk_unit": sum(1 for c, s in zip(items, body_sizes) if s < minimum and c.metadata["chunk_count"] > 1),
            "no_section_path": sum(1 for c in items if not c.metadata["section_path"]),
            "no_saint_name": sum(1 for c in items if c.metadata["content_type"] == "saints" and not c.metadata["saint_name"]),
            "no_saint_id": sum(1 for c in items if c.metadata["content_type"] == "saints" and not c.metadata["saint_id"]),
            "no_printed_page": sum(1 for c in items if c.metadata["source_type"] == "pdf" and not c.metadata["printed_page_start"]),
        }
    documents = {}
    for doc_id, doc_units in units.items():
        info = {k: v for k, v in unit_stats.get(doc_id, web_stats.get(doc_id, {})).items() if k != "printed_pages"}
        info["units"] = len(doc_units)
        info["chunks"] = sum(1 for c in chunks if c.metadata["doc_id"] == doc_id)
        documents[doc_id] = info
    return {
        "corpus_version": CORPUS_VERSION,
        "chunks": len(chunks),
        "by_type": by_kind,
        "documents": documents,
        "saints_index": {k: v for k, v in index_stats.items()},
        "units_not_chunked": {k: len(v) for k, v in skipped.items()},
        "units_not_chunked_list": skipped,
    }


def manifest(chunks: List[Chunk], web_stats: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    import chromadb
    import pymupdf
    import pypdf
    import tiktoken

    per_doc: Dict[str, "hashlib._Hash"] = {}
    counts: Dict[str, int] = {}
    for chunk in chunks:
        doc_id = str(chunk.metadata["doc_id"])
        per_doc.setdefault(doc_id, hashlib.sha1()).update(str(chunk.metadata["text_sha1"]).encode())
        counts[doc_id] = counts.get(doc_id, 0) + 1
    ids = sorted(c.id for c in chunks)
    return {
        "corpus_version": CORPUS_VERSION,
        "chunks": len(chunks),
        "chunks_by_language": {lang: sum(1 for c in chunks if c.metadata["language"] == lang) for lang in ("en", "ar")},
        "collections": {lang: {"name": name, "chunks": sum(1 for c in chunks if c.metadata["language"] == lang),
                               "chunk_ids_sha1": ids_sha1(c.id for c in chunks if c.metadata["language"] == lang)}
                        for lang, name in COLLECTIONS.items()},
        "documents": {doc_id: {"chunks": counts[doc_id], "text_sha1": per_doc[doc_id].hexdigest()} for doc_id in sorted(counts)},
        "chunk_ids_sha1": hashlib.sha1("\n".join(ids).encode()).hexdigest(),
        "web_content_sha1": {doc_id: info["content_sha1"] for doc_id, info in sorted(web_stats.items())},
        "embedding_model": "text-embedding-3-small",
        "embedding_tokens": sum(int(c.metadata["token_count"]) for c in chunks),
        "versions": {"python": platform.python_version(), "pymupdf": pymupdf.VersionBind, "pypdf": pypdf.__version__,
                     "chromadb": chromadb.__version__, "tiktoken": tiktoken.__version__},
    }


# ---------------------------------------------------------------- embedding (Step 3) and verification

def embed_build(chroma_dir: Path, *, resume: bool = False, log=print) -> Dict[str, object]:
    """Embed build/corpus/v2/chunks.jsonl into `chroma_dir` (v2's own directory, never v1's).

    Refuses when the chunks on disk are not the ones the committed manifest describes, so what is
    embedded is exactly what was reviewed. Stops on the first quota or auth error (embed.py)."""
    import chromadb
    from chromadb.config import Settings

    from .embed import upsert_chunks

    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    chunks = load_chunks()
    if ids_sha1(c.id for c in chunks) != expected["chunk_ids_sha1"] or len(chunks) != expected["chunks"]:
        raise RuntimeError("build/corpus/v2/chunks.jsonl does not match data/corpus/v2/manifest.json; "
                           "re-run `python -m ingestion build --corpus v2 --dry-run` and review the diff first")
    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
    written = {}
    for language, name in COLLECTIONS.items():
        collection = client.get_or_create_collection(name, metadata={"source": name, "language": language,
                                                                     "corpus_version": CORPUS_VERSION})
        subset = [{"id": c.id, "text": c.document, "metadata": c.metadata} for c in chunks if c.metadata["language"] == language]
        stale = set(collection.get(include=[])["ids"]) - {c["id"] for c in subset}
        if stale:  # ids from an older build of v2 that the reviewed corpus no longer has
            collection.delete(ids=sorted(stale))
            log(f"{name}: removed {len(stale)} stale ids")
        written[name] = upsert_chunks(collection, subset, label=f"v2 {language}", resume=resume)
    problems = verify_store(client, expected)
    return {"written": written, "problems": problems}


def samples_markdown(chunks: List[Chunk], per_type: int = 10, seed: int = 2026) -> str:
    """Ten chunks of each type, picked at random with a fixed seed, plus the metadata that matters."""
    rng = random.Random(seed)
    lines = ["# v2 chunk samples", "",
             f"Ten random chunks of each type (seed {seed}), from `python -m ingestion build --corpus v2 --dry-run`. "
             "Each shows the stored document (header + body) and its key metadata.", ""]
    for kind in SAMPLE_TYPES:
        items = [c for c in chunks if chunk_kind(c.metadata) == kind]
        lines += [f"## {kind} ({len(items)} chunks)", ""]
        for chunk in sorted(rng.sample(items, min(per_type, len(items))), key=lambda c: c.id):
            m = chunk.metadata
            pages = f"PDF p. {m['page_start']}–{m['page_end']}, printed p. {m['printed_page_start'] or '?'}–{m['printed_page_end'] or '?'}" \
                if m["source_type"] == "pdf" else m["url"]
            extra = []
            if m["saint_id"]:
                extra.append(f"saint_id `{m['saint_id']}`")
            if m.get("synaxarion_date"):
                extra.append(f"Synaxarion {m['synaxarion_date']}")
            if m.get("western_date"):
                extra.append(f"western {m['western_date']}")
            lines += [f"### `{chunk.id}`", "",
                      f"- {m['work']} · {pages} · chunk {m['chunk_index']}/{m['chunk_count']} · {m['token_count']} tokens"
                      + (" · " + " · ".join(extra) if extra else ""),
                      f"- unit_title: {m['unit_title']}" + (f" · section_path: {m['section_path']}" if m["section_path"] else "")
                      + (f" · subsection: {m['subsection']}" if m["subsection"] else ""),
                      "", "```text", chunk.document, "```", ""]
    return "\n".join(lines)


def load_chunks(path: Path = BUILD_DIR / "chunks.jsonl") -> List[Chunk]:
    with path.open(encoding="utf-8") as handle:
        return [Chunk(**{k: v for k, v in json.loads(line).items()}) for line in handle if line.strip()]
