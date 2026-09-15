"""Structured, per-request tracing for the API.

One `RequestTrace` is created per request. Code along the request path attaches
facts to it (which queries ran, which chunk ids came back with what distance,
which survived filtering, token usage, per-stage latency, the final outcome).
When the request ends the trace is emitted as a single JSON line on stdout via
the ``orthodox.request`` logger, so a log platform can index it and a human can
grep it.

Design rules:
- Never log full chunk text or full conversation history. Chunk *ids* are logged;
  the id encodes pdf/page/chunk_index and is enough to look the text up.
- The active trace is stored in a ``contextvars.ContextVar`` so helper functions
  deep in the pipeline can annotate it without threading a parameter through
  every signature. FastAPI copies the context into the worker thread that runs
  a sync endpoint, so the variable is visible everywhere inside the request.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

request_logger = logging.getLogger("orthodox.request")

_current_trace: contextvars.ContextVar[Optional["RequestTrace"]] = contextvars.ContextVar(
    "orthodox_request_trace", default=None
)

QUESTION_PREVIEW_CHARS = 300
MAX_HITS_PER_QUERY = 32


def current_trace() -> Optional["RequestTrace"]:
    return _current_trace.get()


def chunk_id_from_metadata(metadata: Dict[str, Any] | None) -> str:
    """Reconstruct the deterministic Chroma id that ingestion assigned to a chunk.

    Mirrors the id formats in ingest.py, ingest_arabic_sources.py and ingest_web.py
    so that log lines and eval tooling can reference chunks without changing the
    retrieval functions' return values.
    """
    meta = metadata or {}
    source_type = str(meta.get("source_type", "pdf") or "pdf")
    chunk_index = meta.get("chunk_index", 0)
    if source_type == "website":
        url = str(meta.get("url", "") or "")
        url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return f"website::{url_hash}::c{chunk_index}"
    pdf = str(meta.get("pdf", "") or "")
    page = meta.get("page", 0)
    prefix = "ar::" if str(meta.get("language", "")) == "ar" else ""
    return f"{prefix}{pdf}::p{page}::c{chunk_index}"


def _round(value: Any, digits: int = 4) -> Any:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


class RequestTrace:
    """Accumulates facts about one request and emits them as one JSON line."""

    def __init__(self, endpoint: str, request_id: str | None = None):
        self.endpoint = endpoint
        self.request_id = request_id or uuid.uuid4().hex
        self.started = time.monotonic()
        self.fields: Dict[str, Any] = {}
        self.stages_ms: Dict[str, float] = {}
        self.retrieval: List[Dict[str, Any]] = []
        self.retrieved_ids: List[str] = []
        self.kept_ids: List[str] = []
        # Passage texts for the eval harness only: returned in debug_payload(), never logged.
        self.debug_passages: Optional[List[Dict[str, Any]]] = None
        self.emitted = False
        self._token: contextvars.Token | None = None

    # --- lifecycle -------------------------------------------------------

    def __enter__(self) -> "RequestTrace":
        self._token = _current_trace.set(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None and not self.emitted:
            self._record_exception(exc)
        self.emit()
        if self._token is not None:
            _current_trace.reset(self._token)
        return False  # never swallow exceptions

    def _record_exception(self, exc: BaseException) -> None:
        status = getattr(exc, "status_code", None)
        self.fields.setdefault("outcome", "error" if not status or status >= 500 else "rejected")
        self.fields["http_status"] = status or 500
        self.fields.setdefault("error_type", type(exc).__name__)

    def lap(self, name: str) -> None:
        """Record the time since the previous lap (or request start) as stage `name`."""
        now = time.monotonic()
        last = getattr(self, "_last_lap", self.started)
        self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + (now - last) * 1000.0, 1)
        self._last_lap = now

    # --- annotation ------------------------------------------------------

    def set(self, **fields: Any) -> None:
        self.fields.update(fields)

    def set_question(self, question: str) -> None:
        text = question or ""
        self.fields["question_chars"] = len(text)
        self.fields["question"] = text[:QUESTION_PREVIEW_CHARS]

    @contextmanager
    def stage(self, name: str):
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = (time.monotonic() - start) * 1000.0
            self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + elapsed, 1)

    def add_retrieval(
        self,
        source: str,
        query: str,
        hits: Iterable[Dict[str, Any]],
        collection: str | None = None,
        **extra: Any,
    ) -> None:
        hit_list = []
        for hit in list(hits)[:MAX_HITS_PER_QUERY]:
            item = {"id": hit.get("id")}
            if "distance" in hit:
                item["distance"] = _round(hit["distance"])
            if "score" in hit:
                item["score"] = _round(hit["score"], 2)
            hit_list.append(item)
            chunk_id = hit.get("id")
            if chunk_id and chunk_id not in self.retrieved_ids:
                self.retrieved_ids.append(chunk_id)
        record: Dict[str, Any] = {
            "source": source,
            "query": (query or "")[:QUESTION_PREVIEW_CHARS],
            "hits": hit_list,
        }
        if collection:
            record["collection"] = collection
        record.update(extra)
        self.retrieval.append(record)

    def set_kept(self, metadatas: Iterable[Dict[str, Any] | None], rejected_count: int | None = None) -> None:
        self.kept_ids = [chunk_id_from_metadata(meta) for meta in metadatas]
        if rejected_count is not None:
            self.fields["filter_rejected"] = rejected_count

    def set_generation(self, response: Any, model: str) -> None:
        self.fields["model"] = model
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.fields["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
            self.fields["completion_tokens"] = getattr(usage, "completion_tokens", None)
            self.fields["total_tokens"] = getattr(usage, "total_tokens", None)
        try:
            self.fields["finish_reason"] = response.choices[0].finish_reason
        except Exception:  # pragma: no cover - defensive
            pass

    # --- output ----------------------------------------------------------

    def debug_payload(self) -> Dict[str, Any]:
        """Subset of the trace that is safe to return to an authenticated caller.

        Used by the evaluation harness (``debug: true`` on /chat) to measure
        retrieval recall without parsing server logs. No chunk text is included.
        """
        keys = (
            "outcome", "refusal", "refusal_reason", "grounding", "retrieval_queries", "retry",
            "retry_queries", "entity", "rewritten_question", "filter_rejected", "context_chunks",
            "prompt_tokens", "completion_tokens", "model", "citations", "history_turns_sent",
            "prompt_version", "best_distance", "distance_threshold", "saint_intent_fallthrough",
        )
        payload: Dict[str, Any] = {"request_id": self.request_id}
        for key in keys:
            if key in self.fields:
                payload[key] = self.fields[key]
        payload["retrieval"] = self.retrieval
        payload["retrieved_ids"] = self.retrieved_ids
        payload["merged_ids"] = self.fields.get("merged_ids", [])
        payload["kept_ids"] = self.kept_ids
        payload["stages_ms"] = self.stages_ms
        if self.debug_passages is not None:
            payload["passages"] = self.debug_passages
        return payload

    def to_dict(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "event": "request",
            "endpoint": self.endpoint,
            "request_id": self.request_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "total_ms": round((time.monotonic() - self.started) * 1000.0, 1),
        }
        record.update(self.fields)
        record.setdefault("http_status", 200)
        record.setdefault("outcome", "unknown")
        if self.stages_ms:
            record["stages_ms"] = self.stages_ms
        if self.retrieval:
            record["retrieval"] = self.retrieval
            record["retrieved_ids"] = self.retrieved_ids
            record["kept_ids"] = self.kept_ids
        return record

    def emit(self) -> None:
        if self.emitted:
            return
        self.emitted = True
        try:
            request_logger.info(json.dumps(self.to_dict(), ensure_ascii=False, default=str))
        except Exception:  # pragma: no cover - logging must never break a request
            logging.getLogger(__name__).exception("failed to emit request trace")


def configure_request_logging(stream=None) -> None:
    """Route the request logger to stdout as bare JSON lines (no prefix)."""
    if any(getattr(handler, "_orthodox_json", False) for handler in request_logger.handlers):
        return
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler._orthodox_json = True  # type: ignore[attr-defined]
    request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    request_logger.propagate = False
