import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "orthodox_pdfs")
ARABIC_COLLECTION_NAME = os.getenv("CHROMA_ARABIC_COLLECTION", "orthodox_arabic_pdfs")


def _default_chroma_dir() -> str:
    railway_volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_volume_path:
        volume_path = Path(railway_volume_path)
        if volume_path.name.lower() in {"chroma", "chroma_db"}:
            return str(volume_path)
        return str(volume_path / "chroma_db")

    app_dir = Path("/app")
    if app_dir.exists() and os.access(app_dir, os.W_OK):
        return "/app/chroma_db"
    return "chroma_db"


def get_chroma_path() -> str:
    raw = os.getenv("CHROMA_DIR", _default_chroma_dir())
    path = Path(raw).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_resolved_chroma_dir() -> Path:
    return Path(get_chroma_path())


def get_chroma_dir_env() -> str:
    return os.getenv("CHROMA_DIR", _default_chroma_dir())


def log_chroma_configuration(context: str = "chroma") -> None:
    print(f"[{context}] cwd: {Path.cwd()}")
    print(f"[{context}] CHROMA_DIR env/raw: {get_chroma_dir_env()}")
    print(f"[{context}] resolved_chroma_dir: {get_chroma_path()}")
    print(f"[{context}] collection_name: {COLLECTION_NAME}")
    print(f"[{context}] arabic_collection_name: {ARABIC_COLLECTION_NAME}")


def get_chroma_client():
    return chromadb.PersistentClient(
        path=get_chroma_path(),
        settings=Settings(anonymized_telemetry=False),
    )


def get_chroma_collection(
    *,
    client: Any | None = None,
    embedding_function: Any | None = None,
    metadata: dict[str, Any] | None = None,
    collection_name: str | None = None,
) -> Any:
    chroma_client = client or get_chroma_client()
    return chroma_client.get_or_create_collection(
        collection_name or COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata=metadata,
    )


def get_collection_count(*, collection: Any | None = None) -> int:
    chroma_collection = collection or get_chroma_collection()
    return int(chroma_collection.count())


def persist_chroma_client(client: Any) -> None:
    try:
        client.persist()
    except Exception:
        pass
