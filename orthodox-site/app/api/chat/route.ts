import { NextResponse } from "next/server";
import { backendFetch } from "../../../lib/backend";
import { getOrCreateAnonymousSessionId } from "../../../lib/chat-auth";
import {
  BackendChatResponse,
  backendErrorReply,
  jsonWithSession,
  prepareChat,
  saveAnswer,
  thrownErrorReply,
} from "../../../lib/chat-proxy";

export const runtime = "nodejs";

// The whole answer in one reply. The chat page streams through /api/chat/stream and falls back
// to this route when the stream can't start (GEN-007).
export async function POST(request: Request) {
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const chat = await prepareChat(request, sessionId);
    if (chat instanceof NextResponse) return chat;

    const backendResponse = await backendFetch("/chat", {
      request,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: chat.backendBody,
      timeoutMs: 20000,
    });

    if (!backendResponse.ok) return backendErrorReply(backendResponse, sessionId);
    const assistantPayload = (await backendResponse.json()) as BackendChatResponse;
    return jsonWithSession(await saveAnswer(chat, assistantPayload), sessionId);
  } catch (error) {
    return thrownErrorReply(error, sessionId);
  }
}
