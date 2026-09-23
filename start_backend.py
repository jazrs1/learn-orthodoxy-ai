import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from chroma_store import (
    ARABIC_COLLECTION_NAME,
    COLLECTION_NAME,
    get_chroma_collection,
    get_collection_count,
    get_resolved_chroma_dir,
    log_chroma_configuration,
)


TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_MIN_CHROMA_DOCUMENTS = 1000
DEFAULT_MIN_ARABIC_CHROMA_DOCUMENTS = 1
ARABIC_PDF_NAMES = {"full arabic catechism.pdf", "full saints arabic.pdf"}


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


def _min_arabic_chroma_documents() -> int:
    raw_value = os.getenv(
        "MIN_ARABIC_CHROMA_DOCUMENTS",
        str(DEFAULT_MIN_ARABIC_CHROMA_DOCUMENTS),
    ).strip()
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_MIN_ARABIC_CHROMA_DOCUMENTS


def _pdf_sources_available() -> bool:
    return any(Path("data/pdfs").glob("*.pdf"))


def _arabic_pdf_sources_available() -> bool:
    pdf_dir = Path("data/pdfs")
    found = {path.name for path in pdf_dir.glob("*.pdf")}
    missing = sorted(ARABIC_PDF_NAMES - found)
    if missing:
        print(f"[start_backend] Missing Arabic PDFs: {missing}")
        return False
    return True


def _collection_count(collection_name: str = COLLECTION_NAME) -> int:
    collection = get_chroma_collection(collection_name=collection_name)
    return get_collection_count(collection=collection)


def _ingest_sources() -> None:
    # v1 rebuild through the ingestion package (ING-002); same chunks and ids as the old scripts.
    from ingestion.__main__ import build_v1_legacy

    build_v1_legacy(["en"])

    try:
        build_v1_legacy(["web"])
    except Exception as exc:
        if _require_website_ingest():
            raise
        print(f"[start_backend] Website ingestion failed; continuing with PDF sources. Error: {exc!r}")


def _ingest_arabic_sources() -> None:
    from ingestion.__main__ import build_v1_legacy

    build_v1_legacy(["ar"])


def ensure_chroma_populated() -> None:
    log_chroma_configuration("start_backend")
    print(f"[start_backend] collection_name: {COLLECTION_NAME}")
    print(f"[start_backend] arabic_collection_name: {ARABIC_COLLECTION_NAME}")
    print(f"[start_backend] resolved_chroma_dir: {get_resolved_chroma_dir()}")

    count = _collection_count()
    arabic_count = _collection_count(ARABIC_COLLECTION_NAME)
    min_documents = _min_chroma_documents()
    min_arabic_documents = _min_arabic_chroma_documents()
    print(f"[start_backend] collection_count_before_start: {count}")
    print(f"[start_backend] arabic_collection_count_before_start: {arabic_count}")
    print(f"[start_backend] min_chroma_documents: {min_documents}")
    print(f"[start_backend] min_arabic_chroma_documents: {min_arabic_documents}")

    if count < min_documents:
        if not _auto_ingest_enabled():
            print("[start_backend] AUTO_INGEST_ON_START is disabled; starting with underpopulated English Chroma collection.")
        else:
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

    if arabic_count < min_arabic_documents:
        if not _auto_ingest_enabled():
            print("[start_backend] AUTO_INGEST_ON_START is disabled; starting with underpopulated Arabic Chroma collection.")
            return
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required to ingest Arabic sources into Chroma.")
        if not _arabic_pdf_sources_available():
            raise RuntimeError("Arabic PDFs are missing from data/pdfs; cannot populate Arabic Chroma collection.")

        print("[start_backend] Arabic Chroma collection is empty or underpopulated; ingesting Arabic PDFs.")
        _ingest_arabic_sources()

        final_arabic_count = _collection_count(ARABIC_COLLECTION_NAME)
        print(f"[start_backend] arabic_collection_count_after_ingest: {final_arabic_count}")
        if final_arabic_count < min_arabic_documents:
            raise RuntimeError(
                "Arabic ingestion completed but Arabic Chroma collection is still underpopulated "
                f"({final_arabic_count} < {min_arabic_documents})."
            )


def verify_v2_or_exit() -> None:
    """CORPUS_VERSION=v2 (INGEST_PLAN.md §9.1, §9.3): never ingest at boot; refuse to start unless
    the v2 store exists, lives on the Railway volume, and is exactly the reviewed corpus. Exiting
    non-zero keeps the previous deployment serving."""
    import chromadb
    from chromadb.config import Settings

    import corpus_runtime
    from chroma_store import get_chroma_path_v2

    v2_dir = get_chroma_path_v2()
    print(f"[start_backend] corpus_version: v2 chroma_dir_v2: {v2_dir}")
    problems = corpus_runtime.v2_directory_problems(v2_dir, os.getenv("RAILWAY_VOLUME_MOUNT_PATH"))
    if not problems:
        client = chromadb.PersistentClient(path=v2_dir, settings=Settings(anonymized_telemetry=False))
        problems = corpus_runtime.verify_store(client)
    if problems:
        for problem in problems:
            print(f"[start_backend] v2 check failed: {problem}")
        print("[start_backend] refusing to start with CORPUS_VERSION=v2; set CORPUS_VERSION=v1 to roll back.")
        raise SystemExit(1)
    manifest = corpus_runtime.load_manifest()
    print(f"[start_backend] v2 store matches the manifest ({manifest['chunks_by_language']})")


def maybe_start_v2_build(popen=None) -> str:
    """BUILD_CORPUS_V2=1 while v1 serves (ING-008, D7 option B): build v2 in the background into
    CHROMA_DIR_V2, in a separate low-priority process whose output goes to the service log, so a crash
    or a quota stop in the build never touches the API. Every restart resumes it (`--resume` skips
    stored ids) until the store matches the manifest; after that it only logs "v2 complete".
    Returns what it did, for the log and the tests."""
    if os.getenv("BUILD_CORPUS_V2", "0").strip().lower() not in TRUTHY:
        return "off"
    import subprocess

    import chromadb
    from chromadb.config import Settings

    import corpus_runtime
    from chroma_store import get_chroma_path_v2

    v2_dir = Path(get_chroma_path_v2())
    problem = corpus_runtime.outside_volume(str(v2_dir), os.getenv("RAILWAY_VOLUME_MOUNT_PATH"))
    if problem:
        print(f"[start_backend] v2 build not started: {problem}")
        return "outside-volume"
    failed = v2_dir / "BUILD_FAILED"
    if failed.exists():
        print(f"[start_backend] v2 build not started: the last run stopped ({failed.read_text(encoding='utf-8').strip()}). "
              "Check the OpenAI key and budget, delete that file, and redeploy.")
        return "failed-before"
    if v2_dir.is_dir() and any(p.name != "BUILD_FAILED" for p in v2_dir.iterdir()):
        client = chromadb.PersistentClient(path=str(v2_dir), settings=Settings(anonymized_telemetry=False))
        if not corpus_runtime.verify_store(client):
            print("[start_backend] v2 complete: the store matches the manifest. Remove BUILD_CORPUS_V2 and switch with CORPUS_VERSION=v2.")
            return "complete"
    v2_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "ingestion", "build", "--corpus", "v2", "--resume", "--chroma-dir", str(v2_dir)]
    lower_priority = (lambda: os.nice(10)) if hasattr(os, "nice") else None
    process = (popen or subprocess.Popen)(command, env={**os.environ, "PYTHONUNBUFFERED": "1"}, start_new_session=True,
                                          preexec_fn=lower_priority)
    print(f"[start_backend] v2 build started in the background (pid {process.pid}): {' '.join(command)}")
    return "started"


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
    import corpus_runtime

    if corpus_runtime.is_v2():
        verify_v2_or_exit()
    else:
        ensure_chroma_populated()
        maybe_start_v2_build()  # BUILD_CORPUS_V2=1 only; never while v2 is being served
    start_server()


if __name__ == "__main__":
    main()
