from dotenv import load_dotenv

from ingest import CHROMA_DIR, COLLECTION_NAME, get_collection as get_pdf_collection, ingest_pdf_sources
from ingest_web import ingest_website_sources
from website_sources import WEBSITE_SOURCE_URLS

load_dotenv()


def main() -> None:
    print("Starting full source ingestion")
    print(f"CHROMA_DIR: {CHROMA_DIR}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Configured website URLs: {len(WEBSITE_SOURCE_URLS)}")

    pdf_stats = ingest_pdf_sources()
    web_stats = ingest_website_sources(WEBSITE_SOURCE_URLS)

    _, collection = get_pdf_collection()
    final_document_count = int(collection.count())

    print("\n✅ Full source ingestion complete.")
    print(f"Chroma DB saved to: {CHROMA_DIR}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"PDF chunks inserted: {pdf_stats['chunk_count']}")
    print(f"Website chunks inserted: {web_stats['chunk_count']}")
    print(f"Final document count: {final_document_count}")


if __name__ == "__main__":
    main()
