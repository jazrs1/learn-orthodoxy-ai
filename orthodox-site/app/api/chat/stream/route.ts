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
import { eventStreamResponse, fetchBackendStream, isEventStream, relayStream } from "../../../../lib/stream-proxy";

export const runtime = "nodejs";
// Long enough for the longest answer (ANSWER_MAX_TOKENS_TASK); lib/stream-proxy's timeouts end a stuck one.
export const maxDuration = 60;

// The same request as /api/chat, with the answer passed on as the backend writes it (GEN-007).
// A refusal or a saint menu comes from the backend as JSON and is answered exactly like
// /api/chat. A stream is relayed event by event; the backend's `done` is replaced with the saved
// turn ({conversation, userMessage, assistantMessage}, as /api/chat returns it).
export async function POST(request: Request) {
  const sessionId = await getOrCreateAnonymousSessionId();
  const upstream = new AbortController();

  let chat: PreparedChat;
  let backendResponse: Response;
  try {
    const prepared = await prepareChat(request, sessionId);
    if (prepared instanceof NextResponse) return prepared;
    chat = prepared;
    backendResponse = await fetchBackendStream(request, chat.backendBody, upstream);
    if (!backendResponse.ok) return backendErrorReply(backendResponse, sessionId);
    if (!isEventStream(backendResponse)) {
      const assistantPayload = (await backendResponse.json()) as BackendChatResponse;
      return jsonWithSession(await saveAnswer(chat, assistantPayload), sessionId);
    }
  } catch (error) {
    return thrownErrorReply(error, sessionId);
  }

  const response = eventStreamResponse(
    relayStream<BackendChatResponse>(backendResponse.body, upstream, (payload) => savedTurn(chat, payload))
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
