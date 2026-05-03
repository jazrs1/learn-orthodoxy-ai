import argparse
import hashlib
import os
import time
from typing import Any, Dict, List
from urllib.parse import urldefrag

import chromadb
import requests
from bs4 import BeautifulSoup
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma_db")
COLLECTION_NAME = "orthodox_pdfs"

CHUNK_SIZE_CHARS = 3500
CHUNK_OVERLAP_CHARS = 400

REMOVE_SELECTORS = ("script", "style", "nav", "footer", "noscript")
CONTENT_SELECTORS = ("article", "main", "[role='main']", ".post-content", ".entry-content")


def normalize_url(url: str) -> str:
    return urldefrag((url or "").strip())[0]


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


def extract_clean_text(url: str) -> Dict[str, str]:
    print(f"Fetching: {url}")
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "LearnOrthodoxyAI/1.0 (+https://github.com/jazrs1/learn-orthodoxy-ai)"
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = " ".join(h1.get_text(" ", strip=True).split())
    if not title and soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())

    for selector in REMOVE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    content_root = None
    for selector in CONTENT_SELECTORS:
        content_root = soup.select_one(selector)
        if content_root:
            break
    if content_root is None:
        content_root = soup.body or soup

    lines = []
    seen = set()
    for raw_line in content_root.get_text("\n", strip=True).splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if len(line) < 2:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)

    text = "\n".join(lines).replace("\x00", " ").strip()
    if not text:
        raise RuntimeError(f"No readable text extracted from {url}")

    return {
        "title": title or url,
        "text": text,
    }


def build_chunks(url: str, title: str, text: str) -> List[Dict[str, Any]]:
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    chunks = []
    for idx, chunk in enumerate(chunk_text(text, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)):
        chunks.append(
            {
                "id": f"website::{url_hash}::c{idx}",
                "text": chunk,
                "metadata": {
                    "source_type": "website",
                    "url": url,
                    "title": title,
                    "chunk_index": idx,
                },
            }
        )
    return chunks


def delete_existing_url_chunks(collection: Any, url: str, keep_ids: List[str]) -> None:
    existing = collection.get(where={"url": url})
    existing_ids = existing.get("ids", []) or []
    stale_ids = [chunk_id for chunk_id in existing_ids if chunk_id not in set(keep_ids)]
    if stale_ids:
        print(f"Deleting {len(stale_ids)} stale chunk(s) for {url}")
        collection.delete(ids=stale_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest website pages into the Learn Orthodoxy AI Chroma collection.")
    parser.add_argument("urls", nargs="+", help="One or more website URLs to ingest")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    urls = [normalize_url(url) for url in args.urls if normalize_url(url)]
    if not urls:
        raise RuntimeError("Provide at least one valid URL.")

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

    total_chunks = 0
    batch_size = 100
    max_retries = 6

    print(f"Starting website ingestion for {len(urls)} URL(s)")
    for url in urls:
        extracted = extract_clean_text(url)
        title = extracted["title"]
        text = extracted["text"]
        print(f"Parsed title: {title}")
        print(f"Readable text length: {len(text)} characters")

        chunks = build_chunks(url=url, title=title, text=text)
        if not chunks:
            print(f"Skipping {url}: no chunks created")
            continue

        print(f"Created {len(chunks)} chunk(s) for {url}")
        delete_existing_url_chunks(collection, url, [chunk["id"] for chunk in chunks])

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            for attempt in range(max_retries):
                try:
                    collection.upsert(
                        ids=[chunk["id"] for chunk in batch],
                        documents=[chunk["text"] for chunk in batch],
                        metadatas=[chunk["metadata"] for chunk in batch],
                    )
                    print(
                        f"Upserted {min(i + batch_size, len(chunks))}/{len(chunks)} chunk(s) for {url}"
                    )
                    break
                except Exception as exc:
                    if "rate_limit" not in str(exc).lower() and "429" not in str(exc):
                        raise
                    if attempt == max_retries - 1:
                        raise
                    sleep_seconds = min(30, 8 + attempt * 4)
                    print(
                        f"Rate limited while ingesting {url} at batch {i}. "
                        f"Retrying in {sleep_seconds}s..."
                    )
                    time.sleep(sleep_seconds)

        total_chunks += len(chunks)
        print(f"Finished ingesting {url}")

    print("\n✅ Website ingestion complete.")
    print(f"URLs processed: {len(urls)}")
    print(f"Total chunks upserted: {total_chunks}")
    print(f"Chroma DB saved to: {CHROMA_DIR}")
    print(f"Collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    main()
