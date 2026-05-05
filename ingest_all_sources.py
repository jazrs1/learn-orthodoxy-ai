from typing import Dict

from dotenv import load_dotenv

from chroma_store import COLLECTION_NAME, get_chroma_client, get_chroma_collection, get_collection_count, get_chroma_dir_env, get_resolved_chroma_dir, log_chroma_configuration
from ingest import ingest_pdf_sources
from ingest_web import ingest_website_sources
from website_sources import WEBSITE_SOURCE_URLS

load_dotenv()


def ingest_all_sources() -> Dict[str, int]:
    log_chroma_configuration("ingest.all")
    print("Starting full source ingestion")
    print(f"CHROMA_DIR: {get_chroma_dir_env()}")
    print(f"Resolved Chroma dir: {get_resolved_chroma_dir()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Configured website URLs: {len(WEBSITE_SOURCE_URLS)}")

    pdf_stats = ingest_pdf_sources()
    web_stats = ingest_website_sources(WEBSITE_SOURCE_URLS)

    client = get_chroma_client()
    collection = get_chroma_collection(client=client)
    final_document_count = get_collection_count(collection=collection)

    print("\n✅ Full source ingestion complete.")
    print(f"Chroma DB saved to: {get_chroma_dir_env()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"PDF chunks inserted: {pdf_stats['chunk_count']}")
    print(f"Website chunks inserted: {web_stats['chunk_count']}")
    print(f"Final document count: {final_document_count}")
    return {
        "pdf_chunk_count": pdf_stats["chunk_count"],
        "website_chunk_count": web_stats["chunk_count"],
        "document_count": final_document_count,
    }


def main() -> None:
    ingest_all_sources()


if __name__ == "__main__":
    main()
