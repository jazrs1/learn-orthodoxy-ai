import { NextResponse } from "next/server";
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
import { RouteTiming } from "../../../../lib/route-timing";
import {
  eventStreamResponse,
  fetchBackendStream,
  isEventStream,
  relayStream,
  timingHeaders,
} from "../../../../lib/stream-proxy";

export const runtime = "nodejs";
// Long enough for the longest answer (ANSWER_MAX_TOKENS_TASK); lib/stream-proxy's timeouts end a stuck one.
export const maxDuration = 60;

// The same request as /api/chat, with the answer passed on as the backend writes it (GEN-007).
// A refusal or a saint menu comes from the backend as JSON and is answered exactly like
// /api/chat. A stream is relayed event by event; the backend's `done` is replaced with the saved
// turn ({conversation, userMessage, assistantMessage}, as /api/chat returns it).
// Timing (RET-018): `history` (Neon read), `backend_headers` (to Railway and back until the backend
// starts replying), `first_delta` and `done` (ms since the route started), `save` (Neon write).
export async function POST(request: Request) {
  const timing = new RouteTiming("chat_stream");
  const sessionId = await getOrCreateAnonymousSessionId();
  const upstream = new AbortController();

  let chat: PreparedChat;
  let backendResponse: Response;
  try {
    const prepared = await prepareChat(request, sessionId, timing);
    if (prepared instanceof NextResponse) return prepared;
    chat = prepared;
    timing.mark("backend_request");
    backendResponse = await timing.time("backend_headers", () => fetchBackendStream(request, chat.backendBody, upstream));
    timing.set({ request_id: backendResponse.headers.get("x-request-id") });
    if (!backendResponse.ok) return backendErrorReply(backendResponse, sessionId);
    if (!isEventStream(backendResponse)) {
      const assistantPayload = (await backendResponse.json()) as BackendChatResponse;
      const saved = await timing.time("save", () => saveAnswer(chat, assistantPayload));
      timing.set({ streamed: false });
      timing.log();
      const response = await jsonWithSession(saved, sessionId);
      for (const [name, value] of Object.entries(timingHeaders(timing, backendResponse))) response.headers.set(name, value);
      return response;
    }
  } catch (error) {
    return thrownErrorReply(error, sessionId);
  }

  const headers = timingHeaders(timing, backendResponse);
  const response = eventStreamResponse(
    relayStream<BackendChatResponse>(
      backendResponse.body,
      upstream,
      async (payload) => {
        const saved = await timing.time("save", () => savedTurn(chat, payload));
        timing.mark("done");
        return saved;
      },
      {
        onFirstDelta: () => timing.mark("first_delta"),
        onEnd: (outcome) => {
          timing.set({ streamed: true, outcome });
          timing.log();
        },
      }
    ),
    headers
  );
  await getOrCreateAnonymousSessionId(response, sessionId);
  return response;
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
