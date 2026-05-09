import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from chroma_store import (
    COLLECTION_NAME,
    get_chroma_collection,
    get_collection_count,
    get_resolved_chroma_dir,
    log_chroma_configuration,
)


TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_MIN_CHROMA_DOCUMENTS = 1000


def _auto_ingest_enabled() -> bool:
    return os.getenv("AUTO_INGEST_ON_START", "1").strip().lower() in TRUTHY


def _require_website_ingest() -> bool:
    return os.getenv("REQUIRE_WEBSITE_INGEST_ON_START", "0").strip().lower() in TRUTHY


def _min_chroma_documents() -> int:
    raw_value = os.getenv("MIN_CHROMA_DOCUMENTS", str(DEFAULT_MIN_CHROMA_DOCUMENTS)).strip()
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_MIN_CHROMA_DOCUMENTS


def _pdf_sources_available() -> bool:
    return any(Path("data/pdfs").glob("*.pdf"))


def _collection_count() -> int:
    collection = get_chroma_collection()
    return get_collection_count(collection=collection)


def _ingest_sources() -> None:
    from ingest import ingest_pdf_sources
    from ingest_web import ingest_website_sources
    from website_sources import WEBSITE_SOURCE_URLS

    ingest_pdf_sources()

    try:
        ingest_website_sources(WEBSITE_SOURCE_URLS)
    except Exception as exc:
        if _require_website_ingest():
            raise
        print(f"[start_backend] Website ingestion failed; continuing with PDF sources. Error: {exc!r}")


def ensure_chroma_populated() -> None:
    log_chroma_configuration("start_backend")
    print(f"[start_backend] collection_name: {COLLECTION_NAME}")
    print(f"[start_backend] resolved_chroma_dir: {get_resolved_chroma_dir()}")

    count = _collection_count()
    min_documents = _min_chroma_documents()
    print(f"[start_backend] collection_count_before_start: {count}")
    print(f"[start_backend] min_chroma_documents: {min_documents}")
    if count >= min_documents:
        return

    if not _auto_ingest_enabled():
        print("[start_backend] AUTO_INGEST_ON_START is disabled; starting with empty Chroma collection.")
        return

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required to ingest sources into an empty Chroma collection.")

    if not _pdf_sources_available():
        raise RuntimeError("No PDFs found in data/pdfs; cannot populate Chroma collection.")

    print("[start_backend] Chroma collection is missing or underpopulated; ingesting source documents.")
    _ingest_sources()

    final_count = _collection_count()
    print(f"[start_backend] collection_count_after_ingest: {final_count}")
    if final_count < min_documents:
        raise RuntimeError(
            "Ingestion completed but Chroma collection is still underpopulated "
            f"({final_count} < {min_documents})."
        )


def start_server() -> None:
    port = os.getenv("PORT", "8001")
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "api:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]
    print(f"[start_backend] starting server on 0.0.0.0:{port}")
    os.execvp(args[0], args)


def main() -> None:
    load_dotenv()
    ensure_chroma_populated()
    start_server()


if __name__ == "__main__":
    main()
