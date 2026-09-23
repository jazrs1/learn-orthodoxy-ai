/** Reading a streamed answer in the browser, Stop, and the fallback to /api/chat (GEN-007,
 * UI-026). `fetch` is replaced with a fake. Run with `npm test`. */

import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { ApiError, StreamError, streamChatRequest, type ChatResponse } from "./chat-client.ts";
import { formatSseEvent } from "./sse.ts";

const TURN: ChatResponse = {
  conversation: { id: "c1", title: "What is prayer?", createdAt: "", updatedAt: "" },
  userMessage: { id: "u1", role: "user", content: "What is prayer?" },
  assistantMessage: { id: "a1", role: "assistant", content: "Prayer is talking with God [1].", sources: [] },
};

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

type Call = { url: string; signal?: AbortSignal | null };

/** Replies to /api/chat/stream with `stream` and to /api/chat with `fallback`. */
function fakeFetch(stream: (init: RequestInit) => Response | Promise<Response>, fallback?: () => Response) {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
    calls.push({ url, signal: init.signal });
    if (url === "/api/chat/stream") return stream(init);
    if (url === "/api/chat" && fallback) return fallback();
    throw new Error(`unexpected ${url}`);
  }) as typeof fetch;
  return calls;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** An event stream that sends `events`, then stays open until `closeAfter` is sent or the fetch is aborted. */
function eventStream(init: RequestInit, events: string[], log: string[] = []) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) controller.enqueue(encoder.encode(event));
      init.signal?.addEventListener("abort", () => {
        log.push("aborted");
        controller.error(new DOMException("The operation was aborted.", "AbortError"));
      });
      if (events.some((event) => event.startsWith("event: done") || event.startsWith("event: error"))) {
        controller.close();
      }
    },
    cancel() {
      log.push("cancelled");
    },
  });
  return new Response(body, { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}

describe("streamChatRequest", () => {
  test("text arrives piece by piece, then the saved turn", async () => {
    fakeFetch((init) =>
      eventStream(init, [
        formatSseEvent("delta", { t: "Prayer is " }),
        // One network chunk holding two events, and one event split over two chunks.
        formatSseEvent("delta", { t: "talking " }) + formatSseEvent("delta", { t: "with God" }).slice(0, 10),
        formatSseEvent("delta", { t: "with God" }).slice(10),
        formatSseEvent("delta", { t: " [1]." }),
        formatSseEvent("done", TURN),
      ])
    );
    const pieces: string[] = [];
    const turn = await streamChatRequest({ question: "What is prayer?" }, { onDelta: (t) => pieces.push(t) });
    assert.deepEqual(pieces, ["Prayer is ", "talking ", "with God", " [1]."]);
    assert.deepEqual(turn, TURN);
  });

  test("Stop aborts the request: it rejects with an AbortError and no more text is delivered", async () => {
    const log: string[] = [];
    const controller = new AbortController();
    fakeFetch((init) => eventStream(init, [formatSseEvent("delta", { t: "Prayer is " })], log));
    const pieces: string[] = [];
    const pending = streamChatRequest(
      { question: "What is prayer?" },
      {
        signal: controller.signal,
        onDelta: (t) => {
          pieces.push(t);
          controller.abort();
        },
      }
    );
    await assert.rejects(pending, { name: "AbortError" });
    assert.deepEqual(pieces, ["Prayer is "]);
    assert.deepEqual(log, ["aborted"]);
  });

  test("Stop before the reply starts rejects with an AbortError and does not fall back", async () => {
    const controller = new AbortController();
    const calls = fakeFetch(
      (init) =>
        new Promise((_, reject) =>
          init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))
        ),
      () => json(TURN)
    );
    const pending = streamChatRequest({ question: "q" }, { signal: controller.signal, onDelta: () => undefined });
    controller.abort();
    await assert.rejects(pending, { name: "AbortError" });
    assert.deepEqual(calls.map((c) => c.url), ["/api/chat/stream"]);
  });

  test("a refusal or saint menu comes back whole as JSON", async () => {
    fakeFetch(() => json(TURN));
    const pieces: string[] = [];
    assert.deepEqual(await streamChatRequest({ question: "q" }, { onDelta: (t) => pieces.push(t) }), TURN);
    assert.deepEqual(pieces, []);
  });

  test("an error event after some text rejects with a StreamError", async () => {
    fakeFetch((init) =>
      eventStream(init, [
        formatSseEvent("delta", { t: "Prayer is " }),
        formatSseEvent("error", { message: "The assistant is busy right now.", retryable: true }),
      ])
    );
    await assert.rejects(streamChatRequest({ question: "q" }, { onDelta: () => undefined }), StreamError);
  });

  test("a stream that ends without done or error rejects with a StreamError", async () => {
    fakeFetch(() => new Response(formatSseEvent("delta", { t: "Pray" }), { headers: { "Content-Type": "text/event-stream" } }));
    await assert.rejects(streamChatRequest({ question: "q" }, { onDelta: () => undefined }), StreamError);
  });

  test("falls back to /api/chat when the stream route is missing, a gateway fails, or the network drops", async () => {
    for (const failure of [() => json({}, 404), () => json({}, 502), () => json({}, 504), () => Promise.reject(new TypeError("fetch failed"))]) {
      const calls = fakeFetch(failure, () => json(TURN));
      assert.deepEqual(await streamChatRequest({ question: "q" }, { onDelta: () => undefined }), TURN);
      assert.deepEqual(calls.map((c) => c.url), ["/api/chat/stream", "/api/chat"]);
    }
  });

  test("does not fall back on the backend's own errors (asking twice would count twice)", async () => {
    for (const status of [400, 429, 500, 503]) {
      const calls = fakeFetch(() => json({ error: "no" }, status), () => json(TURN));
      await assert.rejects(streamChatRequest({ question: "q" }, { onDelta: () => undefined }), (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.status, status);
        return true;
      });
      assert.deepEqual(calls.map((c) => c.url), ["/api/chat/stream"]);
    }
  });
});
