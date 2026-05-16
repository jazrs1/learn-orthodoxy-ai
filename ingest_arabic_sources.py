import os
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from pypdf import PdfReader

from chroma_store import (
    ARABIC_COLLECTION_NAME,
    get_chroma_client,
    get_chroma_collection,
    get_collection_count,
    get_chroma_dir_env,
    get_resolved_chroma_dir,
    log_chroma_configuration,
    persist_chroma_client,
)
from ingest_embeddings import upsert_chunks_with_embeddings

load_dotenv()

PDF_DIR = "data/pdfs"
ARABIC_SOURCE_TITLES = {
    "full arabic catechism",
    "full saints arabic",
}

CHUNK_SIZE_CHARS = 3000
CHUNK_OVERLAP_CHARS = 350


def contains_arabic(value: str) -> bool:
    return bool(re.search(r"[\u0600-\u06ff]", value or ""))


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


def arabic_pdf_paths(pdf_dir: str = PDF_DIR) -> List[Path]:
    paths = []
    for title in ARABIC_SOURCE_TITLES:
        path = Path(pdf_dir) / f"{title}.pdf"
        if path.exists():
            paths.append(path)
    return sorted(paths, key=lambda item: item.name.lower())


def extract_pages(pdf_path: Path) -> List[Dict[str, Any]]:
    print(f"\nArabic PDF diagnostics: {pdf_path.name}")
    print(f"  File path: {pdf_path}")
    print(f"  File exists: {pdf_path.exists()}")
    print(f"  File size bytes: {pdf_path.stat().st_size if pdf_path.exists() else 0}")
    if not pdf_path.exists():
        raise FileNotFoundError(f"Arabic PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    pages: List[Dict[str, Any]] = []
    title = pdf_path.stem
    pages_with_text = 0
    pages_with_arabic = 0
    total_extracted_characters = 0

    print(f"  Page count: {len(reader.pages)}")

    for index, page in enumerate(reader.pages):
        text = (page.extract_text() or "").replace("\x00", " ").strip()
        if not text:
            continue
        pages_with_text += 1
        total_extracted_characters += len(text)
        if not contains_arabic(text):
            continue
        pages_with_arabic += 1
        pages.append(
            {
                "pdf": pdf_path.name,
                "title": title,
                "page": index + 1,
                "text": text,
            }
        )

    print(f"  Pages with extracted text: {pages_with_text}")
    print(f"  Pages with Arabic characters: {pages_with_arabic}")
    print(f"  Total extracted characters: {total_extracted_characters}")
    if pages:
        preview = re.sub(r"\s+", " ", pages[0]["text"][:180]).strip()
        print(f"  First Arabic text preview: {preview}")
    else:
        print("Arabic PDF text extraction returned 0 usable text. OCR or another extractor is needed.")
    return pages


def build_chunks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for page in pages:
        for index, chunk in enumerate(chunk_text(page["text"], CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)):
            if not contains_arabic(chunk):
                continue
            chunks.append(
                {
                    "id": f'ar::{page["pdf"]}::p{page["page"]}::c{index}',
                    "text": chunk,
                    "metadata": {
                        "source_type": "pdf",
                        "pdf": page["pdf"],
                        "title": page["title"],
                        "page": page["page"],
                        "chunk_index": index,
                        "language": "ar",
                        "source_group": "arabic",
                    },
                }
            )
    return chunks


def get_arabic_collection():
    client = get_chroma_client()
    collection = get_chroma_collection(
        client=client,
        collection_name=ARABIC_COLLECTION_NAME,
        metadata={"source": ARABIC_COLLECTION_NAME, "language": "ar"},
    )
    return client, collection


def ingest_arabic_sources(pdf_dir: str = PDF_DIR) -> Dict[str, int]:
    paths = arabic_pdf_paths(pdf_dir)

    log_chroma_configuration("ingest.arabic")
    print(f"CHROMA_DIR: {get_chroma_dir_env()}")
    print(f"Resolved Chroma dir: {get_resolved_chroma_dir()}")
    print(f"Arabic collection: {ARABIC_COLLECTION_NAME}")
    print(f"Arabic PDFs found: {[path.name for path in paths]}")

    missing = sorted(ARABIC_SOURCE_TITLES - {path.stem for path in paths})
    if missing:
        print(f"Missing Arabic PDFs: {[f'{title}.pdf' for title in missing]}")

    if not paths:
        raise RuntimeError(f"No Arabic PDFs found in {pdf_dir}. Expected: {sorted(ARABIC_SOURCE_TITLES)}")

    all_pages: List[Dict[str, Any]] = []
    chunks: List[Dict[str, Any]] = []
    for path in paths:
        pages = extract_pages(path)
        if not pages:
            raise RuntimeError(
                f"Arabic PDF text extraction returned 0 usable text for {path.name}. "
                "OCR or another extractor is needed."
            )
        pdf_chunks = build_chunks(pages)
        print(f"  Chunks created for {path.name}: {len(pdf_chunks)}")
        if not pdf_chunks:
            raise RuntimeError(
                f"Arabic chunking produced 0 chunks for {path.name}. OCR or another extractor is needed."
            )
        all_pages.extend(pages)
        chunks.extend(pdf_chunks)

    print(f"Total Arabic pages extracted: {len(all_pages)}")
    if not all_pages:
        raise RuntimeError(
            "Arabic PDF extraction returned no Arabic text. OCR or a different extraction pipeline is required."
        )

    print(f"Arabic chunks created: {len(chunks)}")
    if not chunks:
        raise RuntimeError(
            "Arabic chunking produced no Arabic chunks. OCR or a different extraction pipeline is required."
        )

    client, collection = get_arabic_collection()
    print(f"Collection count before Arabic ingest: {get_collection_count(collection=collection)}")

    chunks_upserted = upsert_chunks_with_embeddings(
        collection=collection,
        chunks=chunks,
        progress_label="Arabic PDF ingestion",
    )
    print(f"Arabic chunks upserted: {chunks_upserted}")

    persist_chroma_client(client)
    final_count = get_collection_count(collection=collection)
    print(f"Final Arabic document count: {final_count}")
    if final_count <= 0:
        raise RuntimeError(
            f"Arabic ingestion completed but {ARABIC_COLLECTION_NAME} still has 0 documents."
        )

    return {
        "pdf_count": len(paths),
        "page_count": len(all_pages),
        "chunk_count": len(chunks),
        "chunks_upserted": chunks_upserted,
        "document_count": final_count,
    }


def main() -> None:
    try:
        stats = ingest_arabic_sources()

        print("\nArabic ingestion complete.")
        print(f"Chroma DB saved to: {get_chroma_dir_env()}")
        print(f"Collection: {ARABIC_COLLECTION_NAME}")
        print(f"Arabic chunks inserted: {stats['chunk_count']}")
        print(f"Arabic chunks upserted: {stats['chunks_upserted']}")
        print(f"Final Arabic document count: {stats['document_count']}")
    except Exception as exc:
        print(f"\nArabic ingestion failed: {exc!r}")
        traceback.print_exc()
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
