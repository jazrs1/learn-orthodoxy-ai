import { NextResponse } from "next/server";
import { backendFetch } from "../../../../lib/backend";
import { getOrCreateAnonymousSessionId } from "../../../../lib/chat-auth";
import {
  BackendChatResponse,
  PreparedChat,
  backendErrorReply,
  jsonWithSession,
  normalizeAssistantMessage,
  prepareChat,
  saveAnswer,
  thrownErrorReply,
} from "../../../../lib/chat-proxy";
import { SseParser, type SseEvent, formatSseEvent } from "../../../../lib/sse";

export const runtime = "nodejs";
// Long enough for the longest answer (ANSWER_MAX_TOKENS_TASK); the timeouts below end a stuck one.
export const maxDuration = 60;

// The backend must start replying within this (analysis, retrieval, then the first byte), as
// /api/chat's 20 s; after that, at most this long between two events.
const FIRST_BYTE_TIMEOUT_MS = 20000;
const IDLE_TIMEOUT_MS = 30000;
const STREAM_FAILED = "The answer stream was interrupted. Please try again.";

// The same request as /api/chat, with the answer passed on as the backend writes it (GEN-007).
// A refusal or a saint menu comes from the backend as JSON and is answered exactly like
// /api/chat. A stream is relayed event by event; the backend's `done` is replaced with the saved
// turn ({conversation, userMessage, assistantMessage}, as /api/chat returns it).
export async function POST(request: Request) {
  const sessionId = await getOrCreateAnonymousSessionId();
  // Aborted by the browser leaving, by a timeout, or when the relay ends early.
  const upstream = new AbortController();
  const leave = () => upstream.abort(request.signal.reason);
  request.signal.addEventListener("abort", leave, { once: true });

  let chat: PreparedChat;
  let backendResponse: Response;
  try {
    const prepared = await prepareChat(request, sessionId);
    if (prepared instanceof NextResponse) return prepared;
    chat = prepared;

    const firstByte = setTimeout(
      () => upstream.abort(new DOMException("The backend did not answer in time.", "TimeoutError")),
      FIRST_BYTE_TIMEOUT_MS
    );
    try {
      backendResponse = await backendFetch("/chat/stream", {
        request,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: chat.backendBody,
        signal: upstream.signal,
      });
    } finally {
      clearTimeout(firstByte);
    }

    if (!backendResponse.ok) return backendErrorReply(backendResponse, sessionId);
    const contentType = backendResponse.headers.get("content-type") || "";
    if (!contentType.includes("text/event-stream") || !backendResponse.body) {
      const assistantPayload = (await backendResponse.json()) as BackendChatResponse;
      return jsonWithSession(await saveAnswer(chat, assistantPayload), sessionId);
    }
  } catch (error) {
    request.signal.removeEventListener("abort", leave);
    return thrownErrorReply(error, sessionId);
  }

  const response = new NextResponse(relay(backendResponse.body, chat, upstream), {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
  await getOrCreateAnonymousSessionId(response, sessionId);
  return response;
}

function relay(body: ReadableStream<Uint8Array>, chat: PreparedChat, upstream: AbortController) {
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
              send(`event: delta\ndata: ${event.data}\n\n`);
            } else if (event.event === "done") {
              send(formatSseEvent("done", await savedTurn(chat, JSON.parse(event.data) as BackendChatResponse)));
              finished = true;
              break;
            } else if (event.event === "error") {
              send(`event: error\ndata: ${event.data}\n\n`);
              finished = true;
              break;
            }
          }
          if (done && !finished) {
            send(formatSseEvent("error", { message: STREAM_FAILED, retryable: true }));
            finished = true;
          }
        }
      } catch (error) {
        if (!upstream.signal.aborted || upstream.signal.reason?.name === "TimeoutError") {
          console.error("chat stream relay failed", error);
          send(formatSseEvent("error", { message: STREAM_FAILED, retryable: true }));
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
      }
    },
    cancel() {
      // The browser stopped reading (Stop, a closed tab): stop the backend, which stops OpenAI.
      clearTimeout(idle);
      upstream.abort();
    },
  });
}

/** Saves the finished turn. If the database fails, the answer is still delivered, unsaved. */
async function savedTurn(chat: PreparedChat, data: BackendChatResponse) {
  try {
    return await saveAnswer(chat, data);
  } catch (error) {
    console.error("chat stream: saving the turn failed", error);
    return {
      conversation: null,
      userMessage: null,
      assistantMessage: { role: "assistant" as const, ...normalizeAssistantMessage(data) },
    };
  }
}
