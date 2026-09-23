"""The v1 corpus, reproduced exactly (profile `v1-legacy`, D8 in INGEST_PLAN.md).

This is what `ingest.py`, `ingest_arabic_sources.py` and `ingest_web.py` did, moved here so those
scripts could be deleted without losing the ability to rebuild v1 (the rollback target) if the
Railway volume is ever lost. Same extractor (pypdf), same windows, same ids and metadata;
`python -m ingestion verify-legacy` checks it against the live v1 store without any API call.
Do not "improve" this module: its only job is to match v1 byte for byte.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterator, List

from pypdf import PdfReader

from .sources import PDF_SOURCES, WEBSITE_SOURCE_URLS
from .textnorm import NUL
from .web import content_root, fetch_html, normalize_url

EN_CHUNK_CHARS, EN_OVERLAP_CHARS = 3500, 400
AR_CHUNK_CHARS, AR_OVERLAP_CHARS = 3000, 350
ARABIC_CHAR = re.compile("[" + chr(0x0600) + "-" + chr(0x06FF) + "]")


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


def _pdf_pages(file: str) -> Iterator[tuple[int, str]]:
    reader = PdfReader(f"data/pdfs/{file}")
    for index, page in enumerate(reader.pages):
        yield index + 1, page.extract_text() or ""


def english_pdf_chunks() -> Iterator[Dict[str, Any]]:
    for source in (s for s in PDF_SOURCES if s.language == "en"):
        title = source.file.rsplit(".", 1)[0]
        for page, raw in _pdf_pages(source.file):
            text = raw.replace(NUL, " ").strip()
            if not text:
                continue
            for index, chunk in enumerate(chunk_text(text, EN_CHUNK_CHARS, EN_OVERLAP_CHARS)):
                yield {
                    "id": f"{source.file}::p{page}::c{index}",
                    "text": chunk,
                    "metadata": {
                        "source_type": "pdf", "pdf": source.file, "title": title, "page": page,
                        "chunk_index": index, "language": "en", "source_group": "english",
                    },
                }


def arabic_pdf_chunks() -> Iterator[Dict[str, Any]]:
    for source in sorted((s for s in PDF_SOURCES if s.language == "ar"), key=lambda s: s.file.lower()):
        title = source.file.rsplit(".", 1)[0]
        for page, raw in _pdf_pages(source.file):
            text = raw.replace(NUL, " ").strip()
            if not text or not ARABIC_CHAR.search(text):
                continue
            for index, chunk in enumerate(chunk_text(text, AR_CHUNK_CHARS, AR_OVERLAP_CHARS)):
                if not ARABIC_CHAR.search(chunk):
                    continue
                yield {
                    "id": f"ar::{source.file}::p{page}::c{index}",
                    "text": chunk,
                    "metadata": {
                        "source_type": "pdf", "pdf": source.file, "title": title, "page": page,
                        "chunk_index": index, "language": "ar", "source_group": "arabic",
                    },
                }


def _web_text(html: str) -> str:
    from bs4 import BeautifulSoup

    root = content_root(BeautifulSoup(html, "html.parser"))
    lines, seen = [], set()
    for raw_line in root.get_text("\n", strip=True).splitlines():
        line = " ".join(raw_line.split())
        if len(line) < 2 or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines).replace(NUL, " ").strip()


def _web_title(html: str, url: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = " ".join(h1.get_text(" ", strip=True).split()) if h1 else ""
    if not title and soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())
    return title or url


def web_chunks(urls: List[str] = WEBSITE_SOURCE_URLS) -> Iterator[Dict[str, Any]]:
    for url in (normalize_url(u) for u in urls if normalize_url(u)):
        html = fetch_html(url)
        title, text = _web_title(html, url), _web_text(html)
        if not text:
            raise RuntimeError(f"No readable text extracted from {url}")
        url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        for index, chunk in enumerate(chunk_text(text, EN_CHUNK_CHARS, EN_OVERLAP_CHARS)):
            yield {
                "id": f"website::{url_hash}::c{index}",
                "text": chunk,
                "metadata": {
                    "source_type": "website", "url": url, "title": title, "chunk_index": index,
                    "language": "en", "source_group": "english",
                },
            }
