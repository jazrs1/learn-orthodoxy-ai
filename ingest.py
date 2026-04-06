import os
import glob
import time
from typing import List, Dict, Any

from dotenv import load_dotenv
from pypdf import PdfReader
import chromadb
from chromadb.utils import embedding_functions

load_dotenv()

PDF_DIR = "data/pdfs"
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "orthodox_pdfs"

CHUNK_SIZE_CHARS = 3500
CHUNK_OVERLAP_CHARS = 400


def extract_pages(pdf_path: str) -> List[Dict[str, Any]]:
    reader = PdfReader(pdf_path)
    pdf_name = os.path.basename(pdf_path)
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.replace("\x00", " ").strip()
        if text:
            pages.append({
                "pdf": pdf_name,
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
                    "pdf": p["pdf"],
                    "page": p["page"],
                    "chunk_index": idx
                }
            })
    return all_chunks


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    pdf_paths = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    if not pdf_paths:
        raise RuntimeError(f"No PDFs found in {PDF_DIR}. Put your PDFs there first.")

    print(f"Found {len(pdf_paths)} PDFs.")
    all_pages = []

    for path in pdf_paths:
        print(f"Extracting: {os.path.basename(path)}")
        pages = extract_pages(path)
        print(f"  Pages extracted with text: {len(pages)}")
        all_pages.extend(pages)

    print(f"Total pages with text: {len(all_pages)}")

    chunks = build_chunks(all_pages)
    print(f"Total chunks created: {len(chunks)}")

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"source": "orthodox_pdfs"},
    )

    BATCH = 200
    MAX_RETRIES = 6
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        for attempt in range(MAX_RETRIES):
            try:
                collection.upsert(
                    ids=[c["id"] for c in batch],
                    documents=[c["text"] for c in batch],
                    metadatas=[c["metadata"] for c in batch],
                )
                print(f"Upserted {min(i + BATCH, len(chunks))}/{len(chunks)} chunks")
                break
            except Exception as exc:
                if "rate_limit" not in str(exc).lower() and "429" not in str(exc):
                    raise
                if attempt == MAX_RETRIES - 1:
                    raise
                sleep_seconds = min(30, 8 + attempt * 4)
                print(
                    f"Rate limited during batch starting at {i}. "
                    f"Retrying in {sleep_seconds}s..."
                )
                time.sleep(sleep_seconds)

    print("\n✅ Ingestion complete.")
    print(f"Chroma DB saved to: {CHROMA_DIR}")
    print(f"Collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    main()
