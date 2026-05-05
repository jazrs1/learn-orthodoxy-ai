import os
from pathlib import Path
from typing import Any, Tuple

import chromadb
from chromadb.config import Settings


def _default_chroma_dir() -> str:
    if (
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_PROJECT_ID")
        or Path.cwd().as_posix().startswith("/app")
    ):
        return "/app/chroma_db"
    return "chroma_db"


COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "orthodox_pdfs")


def get_chroma_dir_env() -> str:
    return os.getenv("CHROMA_DIR", _default_chroma_dir())


def get_resolved_chroma_dir() -> Path:
    path = Path(get_chroma_dir_env()).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_chroma_path() -> str:
    return str(get_resolved_chroma_dir())


def log_chroma_configuration(context: str = "chroma") -> None:
    print(f"[{context}] cwd: {Path.cwd()}")
    print(f"[{context}] CHROMA_DIR env/raw: {get_chroma_dir_env()}")
    print(f"[{context}] resolved_chroma_dir: {get_chroma_path()}")
    print(f"[{context}] collection_name: {COLLECTION_NAME}")


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
) -> Tuple[Any, Any]:
    chroma_client = client or get_chroma_client()
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata=metadata,
    )
    return chroma_client, collection


def persist_chroma_client(client) -> None:
    try:
        client.persist()
    except Exception:
        pass
