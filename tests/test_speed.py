"""Speed changes (RET-013 onwards): each must give the same results as before, only sooner."""

import hashlib
import json as _json
import math
import os
from concurrent.futures import Future
from types import SimpleNamespace

import chromadb
import pytest
from fastapi.testclient import TestClient

import api
from answer_cache import load_questions, replay_pieces
import task_analysis
from request_log import RequestTrace
from task_analysis import AnalysisCache, TaskAnalysis


class FakeArabicCollection:
    """Enough of a Chroma collection for the lexical scan: paged `get`, counted."""

    def __init__(self, rows):
        self.rows = rows
        self.gets = 0

    def get(self, include=None, limit=500, offset=0, where=None):
        self.gets += 1
        rows = [r for r in self.rows if not where or all(r["metadata"].get(k) == v for k, v in where.items())]
        page = rows[offset:offset + limit]
        return {"documents": [r["document"] for r in page], "metadatas": [r["metadata"] for r in page]}


def arabic_rows():
    texts = [
        ("الصلاة هي صلة الإنسان بالله", "catechism", 10),
        ("الصوم والصلاة معا في حياة الكنيسة", "catechism", 12),
        ("القديس أنطونيوس أب الرهبان وصلاته", "saints", 3),
        ("الصلاة الربانية التي علمها السيد المسيح", "catechism", 11),
        ("نص بلا صلة بالسؤال", "saints", 4),
    ] * 250  # past one 500-row page
    return [
        {"document": text, "metadata": {"chunk_id": f"c{i}", "content_type": kind, "page": page, "title": "t"}}
        for i, (text, kind, page) in enumerate(texts)
    ]


def lexical(question, metadata_filter=None):
    with RequestTrace("test"):
        return api._retrieve_arabic_lexical_documents(question, top_k=16, metadata_filter=metadata_filter)


@pytest.fixture
def arabic(monkeypatch):
    collection = FakeArabicCollection(arabic_rows())
    monkeypatch.setattr(api, "arabic_collection", collection)
    monkeypatch.setattr(api, "_arabic_lexical_cache", {"collection": None, "rows": {}})
    return collection


@pytest.mark.parametrize("metadata_filter", [None, {"content_type": "catechism"}, {"content_type": "saints"}])
def test_the_in_memory_lexical_index_gives_the_scan_s_results(arabic, monkeypatch, metadata_filter):
    monkeypatch.setattr(api, "ARABIC_LEXICAL_CACHE", False)
    before = [lexical(q, metadata_filter) for q in ("ما هي الصلاة؟", "الصوم والصلاة", "من هو الأنبا أنطونيوس؟")]
    monkeypatch.setattr(api, "ARABIC_LEXICAL_CACHE", True)
    after = [lexical(q, metadata_filter) for q in ("ما هي الصلاة؟", "الصوم والصلاة", "من هو الأنبا أنطونيوس؟")]
    assert after == before
    assert any(docs for docs, _ in after)


def test_the_collection_is_read_once_per_filter(arabic):
    lexical("ما هي الصلاة؟")
    reads = arabic.gets
    for _ in range(3):
        lexical("ما هي الصلاة؟")
        lexical("الصوم والصلاة")
    assert arabic.gets == reads  # no further reads
    lexical("ما هي الصلاة؟", {"content_type": "saints"})
    assert arabic.gets > reads  # a new filter is read once


def test_a_different_collection_is_read_again(arabic, monkeypatch):
    lexical("ما هي الصلاة؟")
    other = FakeArabicCollection(arabic_rows()[:5])
    monkeypatch.setattr(api, "arabic_collection", other)
    docs, _ = lexical("ما هي الصلاة؟")
    assert other.gets == 1 and len(docs) <= 5


# ---------------------------------------------------------------- RET-014: one embedding per text



class HashEmbedding(chromadb.EmbeddingFunction):
    """Deterministic stand-in for text-embedding-3-small (1536 numbers from a hash of the text)."""

    def __init__(self):
        self.calls = []

    def __call__(self, input):  # noqa: A002 - chromadb's signature
        self.calls.append(list(input))
        vectors = []
        for text in input:
            seed = hashlib.sha256(text.encode()).digest()
            raw = [((seed[i % 32] * (i + 7)) % 251) / 251 - 0.5 for i in range(1536)]
            norm = math.sqrt(sum(x * x for x in raw))
            vectors.append([x / norm for x in raw])
        return vectors


class RecordingCollection:
    def __init__(self):
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        n = len(kwargs.get("query_embeddings") or kwargs.get("query_texts"))
        return {"documents": [["d"]] * n, "metadatas": [[{"chunk_id": "c1"}]] * n, "ids": [["c1"]] * n, "distances": [[0.5]] * n}


def test_a_query_text_is_embedded_once_per_request(monkeypatch):
    embedding = HashEmbedding()
    monkeypatch.setattr(api, "embed_fn", embedding)
    collection = RecordingCollection()
    with RequestTrace("test") as trace, api._embedding_memo():
        api._retrieve_documents(["What is prayer?"], top_k=4, target_collection=collection)
        # A comparison question's per-tradition searches use the same text again.
        api._retrieve_documents(["What is prayer?"], top_k=4, target_collection=collection, where_document={"$contains": "Catholic"})
        api._retrieve_documents(["What is prayer?", "Why pray?"], top_k=4, target_collection=collection)
    assert embedding.calls == [["What is prayer?"], ["Why pray?"]]
    assert all("query_embeddings" in q and "query_texts" not in q for q in collection.queries)
    assert collection.queries[1]["where_document"] == {"$contains": "Catholic"}
    assert trace.fields["embeddings_reused"] == 2
    # A new request starts afresh.
    with api._embedding_memo():
        api._retrieve_documents(["What is prayer?"], top_k=4, target_collection=collection)
    assert len(embedding.calls) == 3


def test_a_failed_prefetch_is_embedded_again(monkeypatch):
    embedding = HashEmbedding()
    monkeypatch.setattr(api, "embed_fn", embedding)
    failed = Future()
    failed.set_exception(RuntimeError("timeout"))
    with api._embedding_memo():
        api._request_embeddings.get()["What is prayer?"] = failed
        api._retrieve_documents(["What is prayer?"], top_k=4, target_collection=RecordingCollection())
    assert embedding.calls == [["What is prayer?"]]


def test_without_an_embedding_function_chroma_embeds_as_before(monkeypatch):
    monkeypatch.setattr(api, "embed_fn", None)
    collection = RecordingCollection()
    api._retrieve_documents(["What is prayer?"], top_k=4, target_collection=collection)
    assert collection.queries[0]["query_texts"] == ["What is prayer?"]


V2_STORE = os.path.join(os.getenv("CHROMA_DIR", "chroma_db"), "v2")


@pytest.mark.skipif(not os.path.isdir(V2_STORE), reason="needs the local v2 store")
def test_querying_with_our_vectors_is_what_chroma_does_with_texts():
    # Chroma's own path embeds query_texts with the collection's function and searches; handing it
    # the same function's vectors must give the same chunks, distances and order.
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(path=V2_STORE, settings=ChromaSettings(anonymized_telemetry=False))
    embedding = HashEmbedding()
    for name in ("orthodox_pdfs_v2", "orthodox_arabic_pdfs_v2"):
        collection = client.get_collection(name, embedding_function=embedding)
        texts = ["What is prayer?", "ما هي الصلاة؟", "Who was St. Athanasius?"]
        by_text = collection.query(query_texts=texts, n_results=16)
        by_vector = collection.query(query_embeddings=embedding(texts), n_results=16)
        assert by_vector["ids"] == by_text["ids"]
        assert by_vector["distances"] == by_text["distances"]


# ---------------------------------------------------------------- RET-015: prefetch during analysis


@pytest.fixture
def prefetching(monkeypatch):
    embedding = HashEmbedding()
    monkeypatch.setattr(api, "embed_fn", embedding)
    monkeypatch.setattr(api, "EMBEDDING_PREFETCH", True)
    monkeypatch.setattr(api, "TASK_ANALYSIS_ENABLED", True)
    return embedding


def test_an_unchanged_question_reuses_the_prefetched_embedding(prefetching):
    with RequestTrace("test") as trace, api._embedding_memo():
        api._prefetch_question_embedding("What is  prayer?")
        api._retrieve_documents(["What is prayer?"], top_k=4, target_collection=RecordingCollection())
    assert prefetching.calls == [["What is prayer?"]]
    assert trace.fields["embedding_prefetch"] == "reused"


def test_a_rewritten_question_is_embedded_as_rewritten(prefetching):
    with RequestTrace("test") as trace, api._embedding_memo():
        api._prefetch_question_embedding("it's feast?")
        api._retrieve_documents(["When is the feast of St. Mark?"], top_k=4, target_collection=RecordingCollection())
    # The prefetch runs on another thread, so the two calls may come in either order.
    assert sorted(prefetching.calls) == sorted([["it's feast?"], ["When is the feast of St. Mark?"]])
    assert trace.fields["embedding_prefetch"] == "unused"


def test_no_prefetch_where_no_analysis_runs(prefetching):
    with api._embedding_memo():
        api._prefetch_question_embedding("search saint: St. Mark")
        assert api._request_embeddings.get() == {}


def test_chat_starts_the_prefetch_before_the_analysis_and_retrieval_reuses_it(prefetching, monkeypatch):
    seen_at_analysis = {}

    def analyze(question, history):
        seen_at_analysis.update(api._request_embeddings.get())
        return TaskAnalysis(retrieval_query=question, ok=True)

    collection = RecordingCollection()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(api, "_analyze_request", analyze)
    monkeypatch.setattr(api, "collection", collection)
    monkeypatch.setattr(api, "arabic_collection", FakeArabicCollection([]))
    monkeypatch.setattr(api, "oai_client", SimpleNamespace())
    with RequestTrace("chat") as trace:
        api._prepare_or_http_error(api.ChatRequest(question="What is prayer?", language="en"), trace)
    assert list(seen_at_analysis) == ["What is prayer?"]
    assert prefetching.calls[0] == ["What is prayer?"]
    assert all(call != ["What is prayer?"] for call in prefetching.calls[1:])
    assert trace.fields["embedding_prefetch"] == "reused"


# ---------------------------------------------------------------- RET-016: analysis cache



def analysed(question, **fields):
    return TaskAnalysis(retrieval_query=question, ok=True, prompt_tokens=900, completion_tokens=60, **fields)


@pytest.fixture
def analysis_calls(monkeypatch):
    calls = []

    def analyze(client, question, history, model, timeout_seconds):
        calls.append((question, bool(history)))
        return analysed(question, named_subjects=["papal infallibility"], used_history=bool(history))

    monkeypatch.setattr(api, "analyze_request", analyze)
    monkeypatch.setattr(api, "analysis_cache", AnalysisCache())
    monkeypatch.setattr(api, "ANALYSIS_CACHE", True)
    monkeypatch.setattr(api, "TASK_ANALYSIS_ENABLED", True)
    return calls


def test_a_repeated_first_turn_question_reuses_its_analysis(analysis_calls):
    first = api._analyze_request("What is papal infallibility?", [])
    with RequestTrace("test") as trace:
        second = api._analyze_request("What is papal infallibility?", [])
    assert analysis_calls == [("What is papal infallibility?", False)]
    assert second.named_subjects == first.named_subjects == ["papal infallibility"]
    assert second.prompt_tokens is None and trace.fields["analysis_cached"] is True
    # A copy: changing it doesn't change the cache.
    second.named_subjects.append("x")
    assert api._analyze_request("What is papal infallibility?", []).named_subjects == ["papal infallibility"]


def test_follow_ups_and_failures_are_always_analysed(analysis_calls, monkeypatch):
    history = [{"role": "user", "content": "Who was St. Mark?"}, {"role": "assistant", "content": "…"}]
    api._analyze_request("When is his feast?", history)
    api._analyze_request("When is his feast?", history)
    assert analysis_calls == [("When is his feast?", True)] * 2
    monkeypatch.setattr(api, "analyze_request", lambda *a, **k: TaskAnalysis(retrieval_query="q", error="Timeout"))
    api._analyze_request("Why fast?", [])
    assert api.analysis_cache.get("Why fast?", api.TASK_ANALYSIS_MODEL) is None


def test_a_changed_prompt_or_model_misses_the_cache(monkeypatch):
    cache = AnalysisCache()
    cache.put("Why fast?", "gpt-4o-mini", analysed("Why fast?"))
    assert cache.get("Why fast?", "gpt-4o-mini") is not None
    assert cache.get("Why fast?", "gpt-4.1-nano") is None
    monkeypatch.setattr(task_analysis, "ANALYSIS_SYSTEM_PROMPT", task_analysis.ANALYSIS_SYSTEM_PROMPT + " Also…")
    assert AnalysisCache()._key("Why fast?", "gpt-4o-mini") != cache._key("Why fast?", "gpt-4o-mini")


def test_the_oldest_analyses_are_dropped_first():
    cache = AnalysisCache(max_entries=2)
    for q in ("a", "b"):
        cache.put(q, "m", analysed(q))
    cache.get("a", "m")  # used recently
    cache.put("c", "m", analysed("c"))
    assert cache.get("b", "m") is None and cache.get("a", "m") and cache.get("c", "m")


# ---------------------------------------------------------------- RET-017: answer cache


EXAMPLE = load_questions()["en"][0]
ARABIC_EXAMPLE = load_questions()["ar"][0]


def test_replay_pieces_join_back_to_the_answer_exactly():
    for answer in ("Prayer is **conversation** with God [1].\n\n- Praise\n- Thanks  [2]", "الصلاة هي صلة الإنسان بالله [1].\n\nومن أنواعها:", "  lead space"):
        pieces = replay_pieces(answer)
        assert "".join(pieces) == answer
        assert len(pieces) == -(-len(answer.split()) // 3) or answer.startswith(" ")


@pytest.fixture
def cached_backend(monkeypatch):
    """/chat and /chat/stream with preparation and both models stubbed; counts model calls."""
    calls = {"prepare": 0, "model": 0}

    def prepare(req, trace):
        calls["prepare"] += 1

        def finish(reply):
            trace.set(outcome="refused" if "refuse" in reply else "answered")
            return {"answer": reply, "sources": [] if "refuse" in reply else [{"pdf": "catechism1.pdf", "page": 3, "n": 1}], "options": []}

        return api.PendingAnswer(messages=[{"role": "user", "content": req.question}], max_tokens=50, finish=finish)

    def create(**kwargs):
        calls["model"] += 1
        text = "Prayer is conversation with God [1]." if kwargs["messages"][0]["content"] != "refuse me" else "refuse"
        message = SimpleNamespace(content=text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None)

    monkeypatch.setattr(api, "_chat_prepare", prepare)
    monkeypatch.setattr(api, "oai_client", SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(api, "ANSWER_CACHE", True)
    monkeypatch.setattr(api, "answer_cache", api.AnswerCache(load_questions()))
    monkeypatch.setattr(api, "INTERNAL_API_KEY", "k")
    monkeypatch.setattr(api, "chat_ip_limiter", api.SlidingWindowRateLimiter(100, 60))
    monkeypatch.setattr(api, "chat_global_limiter", api.SlidingWindowRateLimiter(100, 60))
    return calls, TestClient(api.app)


def chat(client, **body):
    return client.post("/chat", json={"language": "en", "mode": "chat", **body}, headers={"X-Internal-Key": "k"})


def test_an_example_question_is_answered_once_then_served_from_the_cache(cached_backend):
    calls, client = cached_backend
    first = chat(client, question=EXAMPLE).json()
    second = chat(client, question=EXAMPLE).json()
    assert second == first and calls == {"prepare": 1, "model": 1}


def test_the_stream_replays_a_cached_answer_in_pieces_then_done(cached_backend):
    calls, client = cached_backend
    stored = chat(client, question=EXAMPLE).json()
    response = client.post("/chat/stream", json={"question": EXAMPLE, "language": "en"}, headers={"X-Internal-Key": "k"})
    assert response.headers["content-type"].startswith("text/event-stream")
    blocks = [b for b in response.text.strip().split("\n\n")]
    events = [(b.split("\n")[0][7:], _json.loads(b.split("\n")[1][6:])) for b in blocks]
    deltas = [data["t"] for name, data in events if name == "delta"]
    assert len(deltas) > 1 and "".join(deltas) == stored["answer"]
    assert events[-1] == ("done", stored)
    assert calls["model"] == 1


def test_only_first_turn_example_questions_are_cached(cached_backend):
    calls, client = cached_backend
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    for body in (
        {"question": "What is prayer?"},  # not an example
        {"question": EXAMPLE, "history": history},  # a follow-up
        {"question": EXAMPLE, "debug": True},  # the eval harness
        {"question": EXAMPLE, "mode": "catechism"},
        {"question": ARABIC_EXAMPLE, "language": "en"},  # detected by its language list only
    ):
        chat(client, **body)
        chat(client, **body)
    assert calls["model"] == 10


def test_a_refusal_is_not_cached(cached_backend, monkeypatch):
    calls, client = cached_backend
    monkeypatch.setattr(api.answer_cache, "questions", {"en": {"refuse me"}, "ar": set()})
    chat(client, question="refuse me")
    chat(client, question="refuse me")
    assert calls["model"] == 2


def test_a_prompt_or_corpus_change_misses_the_cache(cached_backend, monkeypatch):
    calls, client = cached_backend
    chat(client, question=EXAMPLE)
    monkeypatch.setattr(api, "PROMPT_VERSION", "v4")
    chat(client, question=EXAMPLE)
    monkeypatch.setattr(api, "_corpus_manifest_sha", lambda: "another corpus")
    chat(client, question=EXAMPLE)
    chat(client, question=EXAMPLE)
    assert calls["model"] == 3
