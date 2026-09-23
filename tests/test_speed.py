"""Speed changes (RET-013 onwards): each must give the same results as before, only sooner."""

import hashlib
import math
import os
from concurrent.futures import Future

import chromadb
import pytest

import api
from request_log import RequestTrace


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
