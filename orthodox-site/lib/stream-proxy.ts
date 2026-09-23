import "server-only";

import { NextResponse } from "next/server";
import { backendFetch } from "./backend";
import { SseParser, type SseEvent, formatSseEvent } from "./sse";

// Relaying the backend's /chat/stream to the browser (GEN-007), shared by /api/chat/stream and
// /api/saint-detail/stream (UI-029). Each route decides what the final `done` event carries.

// The backend must start replying within this (analysis, retrieval, then the first byte), as
// /api/chat's 20 s; after that, at most this long between two events.
const FIRST_BYTE_TIMEOUT_MS = 20000;
const IDLE_TIMEOUT_MS = 30000;
const STREAM_FAILED = "The answer stream was interrupted. Please try again.";

/**
 * The backend's /chat/stream reply. `upstream` is aborted when the browser leaves, on a timeout,
 * or when the relay ends early; pass the same controller to `relayStream`.
 */
export async function fetchBackendStream(request: Request, backendBody: string, upstream: AbortController) {
  const leave = () => upstream.abort(request.signal.reason);
  request.signal.addEventListener("abort", leave, { once: true });
  const firstByte = setTimeout(
    () => upstream.abort(new DOMException("The backend did not answer in time.", "TimeoutError")),
    FIRST_BYTE_TIMEOUT_MS
  );
  try {
    return await backendFetch("/chat/stream", {
      request,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: backendBody,
      signal: upstream.signal,
    });
  } catch (error) {
    request.signal.removeEventListener("abort", leave);
    throw error;
  } finally {
    clearTimeout(firstByte);
  }
}

/** A refusal, a menu or an error comes as JSON; only an answer the model writes is a stream. */
export function isEventStream(response: Response): response is Response & { body: ReadableStream<Uint8Array> } {
  return (response.headers.get("content-type") || "").includes("text/event-stream") && Boolean(response.body);
}

/**
 * The backend's events passed on one at a time. Its `done` payload goes to `finish`, which sends the
 * final events itself with `emit`: the chat sends `done` (answer and sources) at once, then `saved`
 * (the conversation's IDs) after the database write (RET-021); the saints pane only `done`.
 * A dropped or silent backend becomes an `error`.
 */
export function relayStream<T>(
  body: ReadableStream<Uint8Array>,
  upstream: AbortController,
  finish: (payload: T, emit: (event: string, data: unknown) => void) => Promise<void>,
  hooks: { onFirstDelta?: () => void; onEnd?: (outcome: "done" | "error" | "gone") => void } = {}
) {
  const encoder = new TextEncoder();
  let idle: ReturnType<typeof setTimeout> | undefined;
  const waitForNextEvent = () => {
    clearTimeout(idle);
    idle = setTimeout(
      () => upstream.abort(new DOMException("The backend went silent.", "TimeoutError")),
      IDLE_TIMEOUT_MS
    );
  };

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const reader = body.getReader();
      const events: SseEvent[] = [];
      const parser = new SseParser((event) => events.push(event));
      const send = (text: string) => {
        try {
          controller.enqueue(encoder.encode(text));
        } catch {
          // The browser has gone; `cancel` below aborts the backend.
        }
      };
      let finished = false;
      let outcome: "done" | "error" | "gone" = "gone";
      let sentDelta = false;

      try {
        waitForNextEvent();
        while (!finished) {
          const { value, done } = await reader.read();
          if (done) parser.end();
          else {
            waitForNextEvent();
            parser.push(value);
          }
          for (const event of events.splice(0)) {
            if (event.event === "delta") {
              if (!sentDelta) {
                sentDelta = true;
                hooks.onFirstDelta?.();
              }
              send(`event: delta\ndata: ${event.data}\n\n`);
            } else if (event.event === "done") {
              await finish(JSON.parse(event.data) as T, (name, data) => send(formatSseEvent(name, data)));
              finished = true;
              outcome = "done";
              break;
            } else if (event.event === "error") {
              send(`event: error\ndata: ${event.data}\n\n`);
              finished = true;
              outcome = "error";
              break;
            }
          }
          if (done && !finished) {
            send(formatSseEvent("error", { message: STREAM_FAILED, retryable: true }));
            finished = true;
            outcome = "error";
          }
        }
      } catch (error) {
        if (!upstream.signal.aborted || upstream.signal.reason?.name === "TimeoutError") {
          console.error("answer stream relay failed", error);
          send(formatSseEvent("error", { message: STREAM_FAILED, retryable: true }));
          outcome = "error";
        }
      } finally {
        clearTimeout(idle);
        if (!finished) upstream.abort();
        reader.releaseLock();
        try {
          controller.close();
        } catch {
          // Already closed by a cancel.
        }
        hooks.onEnd?.(outcome);
      }
    },
    cancel() {
      // The browser stopped reading (Stop, a closed tab): stop the backend, which stops OpenAI.
      clearTimeout(idle);
      upstream.abort();
    },
  });
}

/** The relayed stream as a response nothing between here and the browser buffers or compresses. */
export function eventStreamResponse(stream: ReadableStream<Uint8Array>, headers: Record<string, string> = {}) {
  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      ...headers,
    },
  });
}

/** Server-Timing and the backend's request ID, for the browser and the timing line (RET-018). */
export function timingHeaders(timing: { serverTiming(): string }, backendResponse?: Response): Record<string, string> {
  const headers: Record<string, string> = { "Server-Timing": timing.serverTiming() };
  const requestId = backendResponse?.headers.get("x-request-id");
  if (requestId) headers["X-Request-ID"] = requestId;
  return headers;
}
