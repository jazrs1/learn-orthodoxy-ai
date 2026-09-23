"""Corpus selection and the v2 corpus helpers the API needs (INGEST_PLAN.md §9.1, §11).

`CORPUS_VERSION` (v1 default | v2) picks the Chroma directory, the collection names and the saints
index. Everything here is safe to import from the API process: no PyMuPDF, no extraction code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

MANIFEST_PATH = Path("data/corpus/v2/manifest.json")
SAINTS_INDEX_PATH = Path("data/corpus/v2/saints_index.json")


def corpus_version() -> str:
    value = os.getenv("CORPUS_VERSION", "v1").strip().lower()
    return value if value in {"v1", "v2"} else "v1"


def is_v2() -> bool:
    return corpus_version() == "v2"


def is_v2_metadata(metadata: Dict[str, Any] | None) -> bool:
    return str((metadata or {}).get("corpus_version", "")) == "v2"


def load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def v2_collection_names() -> Dict[str, str]:
    """{"en": "orthodox_pdfs_v2", "ar": "orthodox_arabic_pdfs_v2"}; the usual env names still override."""
    collections = load_manifest()["collections"]
    return {
        "en": os.getenv("CHROMA_COLLECTION") or collections["en"]["name"],
        "ar": os.getenv("CHROMA_ARABIC_COLLECTION") or collections["ar"]["name"],
    }


def ids_sha1(ids: Iterable[str]) -> str:
    return hashlib.sha1("\n".join(sorted(ids)).encode()).hexdigest()


def verify_store(client: Any, manifest: Optional[Dict[str, Any]] = None) -> List[str]:
    """Differences between the v2 collections and the manifest: counts and the chunk-ID hash per
    collection. Empty means the store is exactly the reviewed corpus."""
    manifest = manifest or load_manifest()
    problems = []
    for info in manifest["collections"].values():
        try:
            collection = client.get_collection(info["name"])
        except Exception:
            problems.append(f"{info['name']}: missing")
            continue
        ids = collection.get(include=[])["ids"]
        if len(ids) != info["chunks"]:
            problems.append(f"{info['name']}: {len(ids)} chunks, manifest says {info['chunks']}")
        elif ids_sha1(ids) != info["chunk_ids_sha1"]:
            problems.append(f"{info['name']}: chunk ids differ from the manifest")
    return problems


def v2_directory_problems(v2_dir: str, volume_mount: str | None) -> List[str]:
    """Why a v2 directory cannot be served: missing or empty, or (on Railway) outside the volume,
    where it would be lost on the next redeploy (INGEST_PLAN.md §9.1)."""
    path = Path(v2_dir)
    if not path.is_dir() or not any(path.iterdir()):
        return [f"CHROMA_DIR_V2 {path} does not exist or is empty"]
    if volume_mount:
        mount = Path(volume_mount).resolve()
        resolved = path.resolve()
        if resolved != mount and mount not in resolved.parents:
            return [f"CHROMA_DIR_V2 {resolved} is not inside the volume mount {mount}"]
        if os.stat(resolved).st_dev != os.stat(mount).st_dev:
            return [f"CHROMA_DIR_V2 {resolved} is not on the volume's filesystem ({mount})"]
    return []


# ---------------------------------------------------------------- citation labels (D5: printed pages)

def _pages(metadata: Dict[str, Any]) -> str:
    start = str(metadata.get("printed_page_start") or "") or str(metadata.get("page_start") or "")
    end = str(metadata.get("printed_page_end") or "") or str(metadata.get("page_end") or "")
    if not start:
        return ""
    return start if not end or end == start else f"{start}–{end}"


def entry_title(metadata: Dict[str, Any]) -> str:
    """What the passage is: "896. What is prayer?", "St. Abanoub El-Nehissy", a web section."""
    if metadata.get("content_type") == "saints":
        return str(metadata.get("saint_name") or metadata.get("unit_title") or "")
    return str(metadata.get("unit_title") or "")


def source_label(metadata: Dict[str, Any]) -> str:
    """"Catechism of the Coptic Orthodox Church, Vol. 2 — Q896 “What is prayer?”, pp. 11–12"
    "Encyclopedia of the Saints and Fathers of the Church, Vol. 1 — St. Abanoub El-Nehissy, pp. 33–35"
    "كاتيكيزم الكنيسة القبطية الأرثوذكسية — س 896 «ما هي الصلاة؟»، ص 19"."""
    arabic = metadata.get("language") == "ar"
    if metadata.get("source_type") == "website":
        section = str(metadata.get("unit_title") or "")
        page_title = str(metadata.get("section_path") or "")
        head = f"{metadata.get('work')}: {page_title}" if page_title else str(metadata.get("work") or "")
        return f"{head} — {section} ({metadata.get('url')})" if section and section != page_title else f"{head} ({metadata.get('url')})"
    work = str(metadata.get("work") or metadata.get("pdf") or "")
    volume = int(metadata.get("volume") or 0)
    if volume:
        work = f"{work}, Vol. {volume}"
    entry = entry_title(metadata)
    if metadata.get("unit_type") == "question" and metadata.get("question_no"):
        question = re.sub(r"^\d+\s*\.\s*", "", entry)
        entry = f"س {metadata['question_no']} «{question}»" if arabic else f"Q{metadata['question_no']} “{question}”"
    pages = _pages(metadata)
    if arabic:
        return f"{work} — {entry}، ص {pages}" if entry else f"{work}، ص {pages}"
    marker = "pp." if "–" in pages else "p."
    return f"{work} — {entry}, {marker} {pages}" if entry else f"{work}, {marker} {pages}"


def source_fields(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """The response `Source` for a v2 passage. `page` stays the PDF page (the eval and old clients
    read it); `pages` is what a reader finds in the book; `entry` names the question or saint."""
    base = {
        "chunk_id": metadata.get("chunk_id"),
        "entry": entry_title(metadata) or None,
        "work": metadata.get("work") or None,
    }
    if metadata.get("source_type") == "website":
        return {**base, "source_type": "website", "url": metadata.get("url") or None,
                "title": metadata.get("section_path") or None}
    return {
        **base,
        "source_type": "pdf",
        "pdf": metadata.get("pdf"),
        "page": int(metadata.get("page_start") or 0),
        "page_end": int(metadata.get("page_end") or 0),
        "pages": _pages(metadata) or None,
    }


# ---------------------------------------------------------------- the ingest-time saints index (§7)

def load_saints_index() -> List[Dict[str, Any]]:
    return json.loads(SAINTS_INDEX_PATH.read_text(encoding="utf-8"))["saints"]


def first_chunk_id(entry: Dict[str, Any]) -> str:
    return f"v2:{entry['doc_id']}:{entry['unit_id']}:c1"


def strip_header(document: str) -> str:
    """A stored v2 document is "header\n\nbody"; the body is what a list excerpt needs."""
    return document.split("\n\n", 1)[1] if "\n\n" in document else document


def arabic_display_name(saint: Dict[str, Any]) -> str:
    """The dictionary's own heading when it has an entry, else the index's Arabic name."""
    return str(saint.get("heading_ar") or saint.get("name_ar") or "")
