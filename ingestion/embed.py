"""Embedding and upsert, safe to run with the production key (INGEST_PLAN.md §8).

Differences from the old `ingest_embeddings.py`:
- `insufficient_quota`, 401 and 403 are fatal: the build stops at once with the batch number,
  instead of treating "429" in any message as a rate limit and retrying ten times.
- Batches are sized with the real tokenizer (cl100k): the old chars/4 estimate was 3x too low for
  Arabic, which tokenizes at ~0.75 tokens per character.
- `resume=True` skips chunks whose ids are already in the collection, so an interrupted build
  (dropped ssh session, restart) finishes without paying twice.
"""

from __future__ import annotations

import os
import random
import re
import time
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, List, Optional

EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
MAX_BATCH_ITEMS = int(os.getenv("EMBED_BATCH_MAX_ITEMS", "64"))
MAX_BATCH_TOKENS = int(os.getenv("EMBED_BATCH_MAX_TOKENS", "60000"))
MAX_RETRIES = int(os.getenv("EMBED_MAX_RETRIES", "8"))
MAX_INPUT_TOKENS = 8191  # text-embedding-3 limit per input


class FatalOpenAIError(RuntimeError):
    """Quota, authentication or permission problem: never retried (the key is shared with production)."""


@lru_cache(maxsize=1)
def _encoding():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text or "", disallowed_special=()))


def _status(error: Exception) -> Optional[int]:
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    return status


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None) or ""
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict):
            code = code or inner.get("code") or inner.get("type") or ""
    return str(code)


def classify(error: Exception) -> str:
    """'fatal' (stop now), 'retry' (transient) or 'raise' (a bug or bad input: surface it)."""
    status = _status(error)
    name = type(error).__name__
    text = str(error).lower()
    if "insufficient_quota" in (_error_code(error) + " " + text):
        return "fatal"
    if status in (401, 403) or name in ("AuthenticationError", "PermissionDeniedError"):
        return "fatal"
    if status == 429 or name == "RateLimitError":
        return "retry"
    if (status is not None and status >= 500) or name in ("APIConnectionError", "APITimeoutError", "InternalServerError"):
        return "retry"
    return "raise"


def _retry_delay(error: Exception, attempt: int) -> float:
    match = re.findall(r"try again in ([0-9]+(?:\.[0-9]+)?)s", str(error), flags=re.IGNORECASE)
    if match:
        return float(match[-1]) + 1.0
    return min(60.0, 2.0 * 2 ** attempt + random.uniform(0.0, 1.0))


def embed_texts(
    client: Any,
    texts: List[str],
    model: str = EMBED_MODEL,
    *,
    label: str = "",
    sleep: Callable[[float], None] = time.sleep,
) -> List[List[float]]:
    for attempt in range(MAX_RETRIES):
        try:
            response = client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as error:  # noqa: BLE001 - classified below
            kind = classify(error)
            if kind == "fatal":
                raise FatalOpenAIError(f"{label}: stopping, OpenAI refused the request: {error}") from error
            if kind == "raise" or attempt == MAX_RETRIES - 1:
                raise
            delay = _retry_delay(error, attempt)
            print(f"{label}: transient error ({type(error).__name__}), retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s", flush=True)
            sleep(delay)
    raise RuntimeError("unreachable")


def batches(chunks: List[Dict[str, Any]]) -> Iterable[List[Dict[str, Any]]]:
    batch: List[Dict[str, Any]] = []
    tokens = 0
    for chunk in chunks:
        size = count_tokens(chunk["text"])
        if size > MAX_INPUT_TOKENS:
            raise ValueError(f"chunk {chunk['id']} has {size} tokens (> {MAX_INPUT_TOKENS}); fix the chunker")
        if batch and (len(batch) >= MAX_BATCH_ITEMS or tokens + size > MAX_BATCH_TOKENS):
            yield batch
            batch, tokens = [], 0
        batch.append(chunk)
        tokens += size
    if batch:
        yield batch


def existing_ids(collection: Any, ids: List[str]) -> set:
    found: set = set()
    for start in range(0, len(ids), 500):
        found.update(collection.get(ids=ids[start:start + 500], include=[]).get("ids", []) or [])
    return found


def upsert_chunks(
    collection: Any,
    chunks: List[Dict[str, Any]],
    *,
    label: str,
    client: Any = None,
    resume: bool = False,
    model: str = EMBED_MODEL,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Embed and upsert; returns the number of chunks written in this run."""
    if resume:
        done = existing_ids(collection, [chunk["id"] for chunk in chunks])
        chunks = [chunk for chunk in chunks if chunk["id"] not in done]
        print(f"{label}: resume, {len(done)} already stored, {len(chunks)} to embed", flush=True)
    if not chunks:
        return 0
    if client is None:
        from openai import OpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")
        client = OpenAI(max_retries=0)  # retries are ours, so quota errors are never retried
    written = 0
    for number, batch in enumerate(batches(chunks), start=1):
        vectors = embed_texts(client, [c["text"] for c in batch], model, label=f"{label} batch {number}", sleep=sleep)
        collection.upsert(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
            embeddings=vectors,
        )
        written += len(batch)
        print(f"{label}: upserted {written}/{len(chunks)}", flush=True)
    return written
