from dotenv import load_dotenv

from chroma_store import COLLECTION_NAME, get_chroma_collection, get_chroma_dir_env, get_resolved_chroma_dir, log_chroma_configuration
from ingest import ingest_pdf_sources
from ingest_web import ingest_website_sources
from website_sources import WEBSITE_SOURCE_URLS

load_dotenv()


def main() -> None:
    log_chroma_configuration("ingest.all")
    print("Starting full source ingestion")
    print(f"CHROMA_DIR: {get_chroma_dir_env()}")
    print(f"Resolved Chroma dir: {get_resolved_chroma_dir()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Configured website URLs: {len(WEBSITE_SOURCE_URLS)}")

    pdf_stats = ingest_pdf_sources()
    web_stats = ingest_website_sources(WEBSITE_SOURCE_URLS)

    _, collection = get_chroma_collection()
    final_document_count = int(collection.count())

    print("\n✅ Full source ingestion complete.")
    print(f"Chroma DB saved to: {get_chroma_dir_env()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"PDF chunks inserted: {pdf_stats['chunk_count']}")
    print(f"Website chunks inserted: {web_stats['chunk_count']}")
    print(f"Final document count: {final_document_count}")


if __name__ == "__main__":
    main()
