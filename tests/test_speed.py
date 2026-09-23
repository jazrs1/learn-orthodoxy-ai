"""Speed changes (RET-013 onwards): each must give the same results as before, only sooner."""

from types import SimpleNamespace

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
