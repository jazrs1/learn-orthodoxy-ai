"""The embedder never retries quota or auth errors (the key is shared with production)."""

from types import SimpleNamespace

import pytest

from ingestion import embed


class FakeError(Exception):
    def __init__(self, message: str, status_code=None, code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.body = body


class RateLimitError(FakeError):
    pass


class AuthenticationError(FakeError):
    pass


class FakeClient:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0
        self.embeddings = self

    def create(self, model, input):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0, 1.0]) for _ in input])


def test_insufficient_quota_is_fatal_on_first_call():
    quota = RateLimitError("Error code: 429 - You exceeded your current quota", 429,
                           body={"error": {"code": "insufficient_quota", "type": "insufficient_quota"}})
    client = FakeClient([quota])
    with pytest.raises(embed.FatalOpenAIError):
        embed.embed_texts(client, ["a"], sleep=lambda s: None)
    assert client.calls == 1


@pytest.mark.parametrize("error", [AuthenticationError("bad key", 401), FakeError("forbidden", 403)])
def test_auth_errors_are_fatal(error):
    client = FakeClient([error])
    with pytest.raises(embed.FatalOpenAIError):
        embed.embed_texts(client, ["a"], sleep=lambda s: None)
    assert client.calls == 1


def test_transient_rate_limit_and_server_errors_are_retried():
    client = FakeClient([RateLimitError("Rate limit reached, try again in 0.5s", 429), FakeError("boom", 500)])
    waits = []
    assert embed.embed_texts(client, ["a", "b"], sleep=waits.append) == [[0.0, 1.0], [0.0, 1.0]]
    assert client.calls == 3 and waits[0] == 1.5


def test_bad_request_is_raised_not_retried():
    client = FakeClient([FakeError("input too long", 400)])
    with pytest.raises(FakeError):
        embed.embed_texts(client, ["a"], sleep=lambda s: None)
    assert client.calls == 1


def test_batches_use_real_token_counts():
    arabic = "القديس " * 400  # ~2,000+ tokens in cl100k; chars/4 would say ~700
    assert embed.count_tokens(arabic) > len(arabic) / 4
    chunks = [{"id": str(i), "text": arabic} for i in range(40)]
    for batch in embed.batches(chunks):
        assert sum(embed.count_tokens(c["text"]) for c in batch) <= embed.MAX_BATCH_TOKENS


def test_oversized_chunk_is_refused():
    with pytest.raises(ValueError):
        list(embed.batches([{"id": "x", "text": "word " * 9000}]))


class FakeCollection:
    def __init__(self, present):
        self.present = set(present)
        self.upserts = []

    def get(self, ids, include):
        return {"ids": [i for i in ids if i in self.present]}

    def upsert(self, ids, documents, metadatas, embeddings):
        self.upserts.append(ids)
        self.present.update(ids)


def test_resume_skips_stored_chunks():
    collection = FakeCollection(present={"a", "b"})
    chunks = [{"id": i, "text": i, "metadata": {}} for i in ("a", "b", "c")]
    client = FakeClient([])
    written = embed.upsert_chunks(collection, chunks, label="t", client=client, resume=True, sleep=lambda s: None)
    assert written == 1 and collection.upserts == [["c"]] and client.calls == 1
