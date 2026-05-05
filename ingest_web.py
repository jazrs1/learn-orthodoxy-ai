import argparse
import hashlib
import os
from typing import Any, Dict, List
from urllib.parse import urldefrag

import requests
from bs4 import BeautifulSoup
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
from dotenv import load_dotenv
from ingest_embeddings import upsert_chunks_with_embeddings

load_dotenv()

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


def get_collection():
    client = get_chroma_client()
    collection = get_chroma_collection(client=client, metadata={"source": "orthodox_pdfs"})
    return client, collection


def ingest_website_sources(urls: List[str]) -> Dict[str, int]:
    urls = [normalize_url(url) for url in urls if normalize_url(url)]
    if not urls:
        raise RuntimeError("Provide at least one valid URL.")

    log_chroma_configuration("ingest.web")
    print(f"CHROMA_DIR: {get_chroma_dir_env()}")
    print(f"Resolved Chroma dir: {get_resolved_chroma_dir()}")
    print(f"Collection: {COLLECTION_NAME}")
    client, collection = get_collection()
    print(f"Ingest start; resolved_chroma_dir: {get_resolved_chroma_dir()}")
    print(f"Collection count before ingest: {get_collection_count(collection=collection)}")

    total_chunks = 0

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

        upsert_chunks_with_embeddings(
            collection=collection,
            chunks=chunks,
            progress_label=f"Website ingestion [{title}]",
        )

        total_chunks += len(chunks)
        print(f"Finished ingesting {url}")

    persist_chroma_client(client)
    final_count = get_collection_count(collection=collection)
    print(f"Final document count after website ingestion: {final_count}")
    return {
        "url_count": len(urls),
        "chunk_count": total_chunks,
        "document_count": final_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest website pages into the Learn Orthodoxy AI Chroma collection.")
    parser.add_argument("urls", nargs="+", help="One or more website URLs to ingest")
    args = parser.parse_args()

    stats = ingest_website_sources(args.urls)

    print("\n✅ Website ingestion complete.")
    print(f"URLs processed: {stats['url_count']}")
    print(f"Total chunks upserted: {stats['chunk_count']}")
    print(f"Chroma DB saved to: {get_chroma_dir_env()}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Final document count: {stats['document_count']}")


if __name__ == "__main__":
    main()
