import math
import os
import random
import re
import time
from typing import Any, Dict, Iterable, List

from openai import OpenAI, RateLimitError


EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
MAX_BATCH_ITEMS = int(os.getenv("EMBED_BATCH_MAX_ITEMS", "16"))
MAX_BATCH_TOKENS = int(os.getenv("EMBED_BATCH_MAX_TOKENS", "12000"))
MAX_RETRIES = int(os.getenv("EMBED_MAX_RETRIES", "10"))


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text or "") / 4))


def build_embedding_batches(chunks: List[Dict[str, Any]]) -> Iterable[List[Dict[str, Any]]]:
    batch: List[Dict[str, Any]] = []
    batch_tokens = 0

    for chunk in chunks:
        text = chunk.get("text", "")
        tokens = estimate_tokens(text)
        if batch and (len(batch) >= MAX_BATCH_ITEMS or batch_tokens + tokens > MAX_BATCH_TOKENS):
            yield batch
            batch = []
            batch_tokens = 0
        batch.append(chunk)
        batch_tokens += tokens

    if batch:
        yield batch


def _extract_retry_seconds(message: str, attempt: int) -> float:
    matches = re.findall(r"try again in ([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
    if matches:
        return float(matches[-1]) + 1.0
    return min(60.0, 5.0 + attempt * 3.0 + random.uniform(0.0, 1.5))


def _is_rate_limit_error(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        return True
    message = str(error).lower()
    return "rate limit" in message or "429" in message or "tokens per min" in message


def _embed_texts(client: OpenAI, texts: List[str]) -> List[List[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def upsert_chunks_with_embeddings(
    *,
    collection: Any,
    chunks: List[Dict[str, Any]],
    progress_label: str,
) -> int:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)
    completed = 0
    total = len(chunks)

    for batch_index, batch in enumerate(build_embedding_batches(chunks), start=1):
        texts = [chunk["text"] for chunk in batch]
        embeddings = None

        for attempt in range(MAX_RETRIES):
            try:
                embeddings = _embed_texts(client, texts)
                break
            except Exception as exc:
                if not _is_rate_limit_error(exc) or attempt == MAX_RETRIES - 1:
                    raise
                sleep_seconds = _extract_retry_seconds(str(exc), attempt)
                print(
                    f"{progress_label}: embedding batch {batch_index} rate limited "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}). Sleeping {sleep_seconds:.1f}s..."
                )
                time.sleep(sleep_seconds)

        if embeddings is None:
            raise RuntimeError(f"{progress_label}: embeddings were not created for batch {batch_index}")

        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=texts,
            metadatas=[chunk["metadata"] for chunk in batch],
            embeddings=embeddings,
        )
        completed += len(batch)
        print(f"{progress_label}: upserted {completed}/{total} chunks")

    return completed
