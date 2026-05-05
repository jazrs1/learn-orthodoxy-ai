from dotenv import load_dotenv

from chroma_store import (
    COLLECTION_NAME,
    MIN_DOCUMENT_COUNT,
    collection_needs_ingestion,
    get_chroma_collection,
    get_collection_count,
    get_chroma_dir_env,
    get_resolved_chroma_dir,
    log_chroma_configuration,
)
from ingest_all_sources import ingest_all_sources

load_dotenv()


def main() -> None:
    log_chroma_configuration("chroma.preflight")
    print(f"[chroma.preflight] checking collection: {COLLECTION_NAME}")
    print(f"[chroma.preflight] CHROMA_DIR: {get_chroma_dir_env()}")
    print(f"[chroma.preflight] resolved path: {get_resolved_chroma_dir()}")

    _, collection = get_chroma_collection()
    starting_count = get_collection_count(collection=collection)
    print(f"[chroma.preflight] document_count_before: {starting_count}")

    if collection_needs_ingestion(starting_count):
        print(
            f"[chroma.preflight] collection count {starting_count} is below threshold "
            f"{MIN_DOCUMENT_COUNT}; starting full ingestion"
        )
        stats = ingest_all_sources()
        print(f"[chroma.preflight] ingestion finished: {stats}")
        _, verified_collection = get_chroma_collection()
        final_count = get_collection_count(collection=verified_collection)
        print(f"[chroma.preflight] document_count_after: {final_count}")
        if collection_needs_ingestion(final_count):
            raise RuntimeError(
                f"Chroma collection {COLLECTION_NAME} is still below threshold after ingestion: "
                f"{final_count} < {MIN_DOCUMENT_COUNT}"
            )
    else:
        print(
            f"[chroma.preflight] collection already populated; "
            f"skipping ingestion ({starting_count} docs)"
        )


if __name__ == "__main__":
    main()
