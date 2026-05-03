import os
from pathlib import Path

import chromadb
from chromadb.config import Settings


CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma_db")
COLLECTION_NAME = "orthodox_pdfs"


def get_resolved_chroma_dir() -> Path:
    return Path(CHROMA_DIR).resolve()


def get_chroma_client():
    persist_dir = get_resolved_chroma_dir()
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )


def persist_chroma_client(client) -> None:
    try:
        client.persist()
    except Exception:
        pass
