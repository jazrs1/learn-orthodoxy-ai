"""/chat/stream (GEN-007): what is streamed, what comes back at once, and what gets logged.

No OpenAI calls: `_chat_prepare` and the async client are replaced with fakes, so these tests
cover the streaming layer only. `/chat`'s own behaviour is covered by the other test files.
"""

import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

import api
from request_log import RequestTrace, request_logger

KEY = "test-internal-key"


def chunk(text=None, finish_reason=None, usage=None):
    choices = [] if text is None and finish_reason is None else [
        SimpleNamespace(delta=SimpleNamespace(content=text), finish_reason=finish_reason)
    ]
    return SimpleNamespace(choices=choices, usage=usage)


class FakeStream:
    """An OpenAI chat-completions stream: yields the chunks, remembers whether it was closed."""

    def __init__(self, chunks, fail_after=None):
        self.chunks = chunks
        self.fail_after = fail_after
        self.sent = 0
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.fail_after is not None and self.sent == self.fail_after:
            raise api.APIConnectionError(request=httpx.Request("POST", "https://api.openai.test"))
        if self.sent >= len(self.chunks):
            raise StopAsyncIteration
        self.sent += 1
        return self.chunks[self.sent - 1]

    async def close(self):
        self.closed = True


class FakeAsyncClient:
    def __init__(self, stream):
        self.stream = stream
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.stream


def usage(completion=3):
    return SimpleNamespace(prompt_tokens=10, completion_tokens=completion, total_tokens=10 + completion)


def answer_chunks(*texts):
    return [chunk(t) for t in texts] + [chunk(finish_reason="stop"), chunk(usage=usage(len(texts)))]


class LogLines(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(json.loads(record.getMessage()))


@pytest.fixture
def logs():
    handler = LogLines()
    request_logger.addHandler(handler)
    yield handler.lines
    request_logger.removeHandler(handler)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "INTERNAL_API_KEY", KEY)
    monkeypatch.setattr(api, "chat_ip_limiter", api.SlidingWindowRateLimiter(100, 60))
    monkeypatch.setattr(api, "chat_global_limiter", api.SlidingWindowRateLimiter(100, 60))
    return TestClient(api.app)


def pending(expects_decline=False, seen=None):
    def finish(reply):
        if seen is not None:
            seen.append(reply)
        answer = api._enforce_entity_decline(
            reply, {"action": "decline", "absent": ["X"]} if expects_decline else None, "en"
        )
        return {"answer": answer, "sources": [{"pdf": "catechism1.pdf", "page": 3, "n": 1}], "options": []}

    return api.PendingAnswer(
        messages=[{"role": "user", "content": "q"}], max_tokens=50, finish=finish, expects_decline=expects_decline
    )


def events(body: str):
    """Parse an SSE body into (event, data) pairs."""
    out = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        out.append((fields["event"], json.loads(fields["data"])))
    return out


def post(client, **body):
    return client.post(
        "/chat/stream",
        json={"question": "What is prayer?", **body},
        headers={"X-Internal-Key": KEY, "X-Client-IP": "1.2.3.4"},
    )


def test_an_answer_is_streamed_then_done_carries_the_chat_payload(client, logs, monkeypatch):
    seen = []
    fake = FakeAsyncClient(FakeStream(answer_chunks("Prayer is ", "talking with God [1].")))
    monkeypatch.setattr(api, "async_oai_client", fake)
    monkeypatch.setattr(api, "_chat_prepare", lambda req, trace: pending(seen=seen))

    response = post(client)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    got = events(response.text)
    assert got[:2] == [("delta", {"t": "Prayer is "}), ("delta", {"t": "talking with God [1]."})]
    assert got[2][0] == "done"
    assert got[2][1] == api._chat_payload(pending().finish("Prayer is talking with God [1]."))
    assert seen == ["Prayer is talking with God [1]."]
    assert fake.calls[0]["stream"] is True and fake.calls[0]["stream_options"] == {"include_usage": True}
    assert fake.stream.closed

    [line] = logs
    assert line["endpoint"] == "chat_stream" and line["stream"] is True
    assert line["ttft_ms"] >= 0 and line["streamed_chars"] == len("Prayer is talking with God [1].")
    assert line["completion_tokens"] == 2 and line["finish_reason"] == "stop"
    assert "generation" in line["stages_ms"] and line["http_status"] == 200


def test_a_refusal_or_menu_comes_back_at_once_as_chat_json(client, logs, monkeypatch):
    menu = {"answer": "Which one?", "sources": [], "options": ["St. A", "St. B"], "option_ids": ["a", "b"]}

    def prepare(req, trace):
        trace.set(outcome="options")
        return menu

    monkeypatch.setattr(api, "_chat_prepare", prepare)
    monkeypatch.setattr(api, "async_oai_client", None)  # never called

    response = post(client)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == api._chat_payload(menu)
    [line] = logs
    assert line["outcome"] == "options" and line["stream"] is True


def test_http_errors_before_generation_keep_their_status(client, logs, monkeypatch):
    def prepare(req, trace):
        raise api.HTTPException(status_code=400, detail="Question cannot be empty")

    monkeypatch.setattr(api, "_chat_prepare", prepare)
    response = post(client)
    assert response.status_code == 400 and response.json() == {"detail": "Question cannot be empty"}
    assert logs[0]["outcome"] == "rejected"


def test_internal_key_and_rate_limit_apply(client, monkeypatch):
    monkeypatch.setattr(api, "_chat_prepare", lambda req, trace: {"answer": "x", "sources": []})
    assert client.post("/chat/stream", json={"question": "q"}).status_code == 401

    monkeypatch.setattr(api, "chat_ip_limiter", api.SlidingWindowRateLimiter(1, 60))
    assert post(client).status_code == 200
    limited = post(client)
    assert limited.status_code == 429 and "retry-after" in limited.headers


def test_a_reply_that_declines_as_asked_is_streamed_after_the_hold(client, monkeypatch):
    decline = "I could not find anything about X in the loaded sources."
    fake = FakeAsyncClient(FakeStream(answer_chunks("I could not ", "find anything about X ", "in the loaded sources.")))
    monkeypatch.setattr(api, "async_oai_client", fake)
    monkeypatch.setattr(api, "_chat_prepare", lambda req, trace: pending(expects_decline=True))

    got = events(post(client).text)

    # The first two pieces are held (under 48 characters), then released together.
    assert got[0] == ("delta", {"t": decline})
    assert got[-1][0] == "done" and got[-1][1]["answer"] == decline


def test_a_reply_that_should_decline_but_does_not_is_never_shown(client, logs, monkeypatch):
    fake = FakeAsyncClient(FakeStream(answer_chunks("Papal infallibility is ", "the teaching that ", "the pope cannot err.", " More.")))
    monkeypatch.setattr(api, "async_oai_client", fake)
    monkeypatch.setattr(api, "_chat_prepare", lambda req, trace: pending(expects_decline=True))

    got = events(post(client).text)

    assert [name for name, _ in got] == ["done"]
    assert got[0][1]["answer"] == "I could not find anything about X in the loaded sources."
    assert fake.stream.sent == 3 and fake.stream.closed  # generation stopped early
    assert logs[0]["finish_reason"] == "decline_enforced" and "ttft_ms" not in logs[0]


def test_an_openai_failure_mid_stream_becomes_an_error_event(client, logs, monkeypatch):
    fake = FakeAsyncClient(FakeStream(answer_chunks("Prayer is ", "talking"), fail_after=1))
    monkeypatch.setattr(api, "async_oai_client", fake)
    monkeypatch.setattr(api, "_chat_prepare", lambda req, trace: pending())

    got = events(post(client).text)

    assert got == [("delta", {"t": "Prayer is "}), ("error", {"message": api.GENERIC_BUSY_ERROR, "retryable": True})]
    assert fake.stream.closed
    assert logs[0]["outcome"] == "error" and logs[0]["error_type"] == "APIConnectionError"
    assert logs[0]["streamed_chars"] == len("Prayer is ")


def test_a_client_that_goes_away_stops_generation_and_is_logged(logs, monkeypatch):
    fake = FakeAsyncClient(FakeStream(answer_chunks("one ", "two ", "three ", "four")))
    monkeypatch.setattr(api, "async_oai_client", fake)
    trace = RequestTrace("chat_stream")

    async def read_one_then_leave():
        stream = api._stream_answer(pending(), trace)
        first = await stream.__anext__()
        await stream.aclose()  # what Starlette does when the client disconnects
        return first

    first = asyncio.run(read_one_then_leave())

    assert first == 'event: delta\ndata: {"t": "one "}\n\n'
    assert fake.stream.closed and fake.stream.sent == 1
    [line] = logs
    assert line["outcome"] == "client_disconnected" and line["disconnected"] is True
    assert line["streamed_chars"] == 4


def test_chat_is_unchanged_and_uses_the_same_preparation(client, monkeypatch):
    message = SimpleNamespace(content="Prayer is talking with God [1].")
    completion = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=usage())
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return completion

    monkeypatch.setattr(api, "oai_client", SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(api, "_chat_prepare", lambda req, trace: pending())

    response = client.post("/chat", json={"question": "q"}, headers={"X-Internal-Key": KEY})

    assert response.status_code == 200
    assert response.json() == api._chat_payload(pending().finish("Prayer is talking with God [1]."))
    assert "stream" not in calls[0] and calls[0]["max_tokens"] == 50


def test_the_trace_is_current_while_preparing_in_the_thread_pool(client, logs, monkeypatch):
    # Helpers deep in the pipeline (entity check, task analysis) annotate `current_trace()`.
    def prepare(req, trace):
        api.current_trace().set(entity_check={"action": "none"})
        return {"answer": "x", "sources": []}

    monkeypatch.setattr(api, "_chat_prepare", prepare)
    assert post(client).status_code == 200
    assert logs[0]["entity_check"] == {"action": "none"}
