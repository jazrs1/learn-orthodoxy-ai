import os
import glob
from typing import List, Dict, Any

from dotenv import load_dotenv
from pypdf import PdfReader
from chroma_store import (
    COLLECTION_NAME,
    get_chroma_collection,
    get_chroma_client,
    get_collection_count,
    get_chroma_dir_env,
    get_resolved_chroma_dir,
    log_chroma_configuration,
    persist_chroma_client,
)
from ingest_embeddings import upsert_chunks_with_embeddings

load_dotenv()

PDF_DIR = "data/pdfs"
ARABIC_PDF_FILENAMES = {
    "full arabic catechism.pdf",
    "full saints arabic.pdf",
}

CHUNK_SIZE_CHARS = 3500
CHUNK_OVERLAP_CHARS = 400


def extract_pages(pdf_path: str) -> List[Dict[str, Any]]:
    reader = PdfReader(pdf_path)
    pdf_name = os.path.basename(pdf_path)
    title = os.path.splitext(pdf_name)[0]
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.replace("\x00", " ").strip()
        if text:
            pages.append({
                "pdf": pdf_name,
                "title": title,
                "page": i + 1,
                "text": text
            })

    return pages


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


def build_chunks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_chunks = []
    for p in pages:
        page_chunks = chunk_text(p["text"], CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
        for idx, ch in enumerate(page_chunks):
            all_chunks.append({
                "id": f'{p["pdf"]}::p{p["page"]}::c{idx}',
                "text": ch,
                "metadata": {
                    "source_type": "pdf",
                    "pdf": p["pdf"],
                    "title": p.get("title", p["pdf"]),
                    "page": p["page"],
                    "chunk_index": idx,
                    "language": "en",
                    "source_group": "english",
                }
            })
    return all_chunks


def get_collection():
    client = get_chroma_client()
    collection = get_chroma_collection(client=client, metadata={"source": "orthodox_pdfs"})
    return client, collection


def ingest_pdf_sources(pdf_dir: str = PDF_DIR) -> Dict[str, int]:
    pdf_paths = [
        path
        for path in sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
        if os.path.basename(path).lower() not in ARABIC_PDF_FILENAMES
    ]
    if not pdf_paths:
        raise RuntimeError(f"No PDFs found in {pdf_dir}. Put your PDFs there first.")

    log_chroma_configuration("ingest.pdf")
    print(f"CHROMA_DIR: {get_chroma_dir_env()}")
    print(f"Resolved Chroma dir: {get_resolved_chroma_dir()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Found {len(pdf_paths)} PDFs.")
    all_pages = []

    for path in pdf_paths:
        print(f"Extracting: {os.path.basename(path)}")
        pages = extract_pages(path)
        print(f"  Pages extracted with text: {len(pages)}")
        all_pages.extend(pages)

    print(f"Total pages with text: {len(all_pages)}")

    chunks = build_chunks(all_pages)
    print(f"Total PDF chunks created: {len(chunks)}")

    client, collection = get_collection()
    print(f"Ingest start; resolved_chroma_dir: {get_resolved_chroma_dir()}")
    print(f"Collection count before ingest: {get_collection_count(collection=collection)}")

    upsert_chunks_with_embeddings(
        collection=collection,
        chunks=chunks,
        progress_label="PDF ingestion",
    )

    persist_chroma_client(client)
    final_count = get_collection_count(collection=collection)
    print(f"Final document count after PDF ingestion: {final_count}")
    return {
        "pdf_count": len(pdf_paths),
        "page_count": len(all_pages),
        "chunk_count": len(chunks),
        "document_count": final_count,
    }


def main():
    stats = ingest_pdf_sources()

    print("\n✅ Ingestion complete.")
    print(f"Chroma DB saved to: {get_chroma_dir_env()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"PDF chunks inserted: {stats['chunk_count']}")
    print(f"Final document count: {stats['document_count']}")


if __name__ == "__main__":
    main()
