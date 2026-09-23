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
import { RouteTiming } from "../../../lib/route-timing";
import { timingHeaders } from "../../../lib/stream-proxy";

export const runtime = "nodejs";

// The whole answer in one reply. The chat page streams through /api/chat/stream and falls back
// to this route when the stream can't start (GEN-007).
export async function POST(request: Request) {
  const timing = new RouteTiming("chat");
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const chat = await prepareChat(request, sessionId, timing);
    if (chat instanceof NextResponse) return chat;

    timing.mark("backend_request");
    const backendResponse = await timing.time("backend", () => backendFetch("/chat", {
      request,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: chat.backendBody,
      timeoutMs: 20000,
    }));
    timing.set({ request_id: backendResponse.headers.get("x-request-id") });

    if (!backendResponse.ok) return backendErrorReply(backendResponse, sessionId);
    const assistantPayload = (await backendResponse.json()) as BackendChatResponse;
    const saved = await timing.time("save", () => saveAnswer(chat, assistantPayload));
    timing.log();
    const response = await jsonWithSession(saved, sessionId);
    for (const [name, value] of Object.entries(timingHeaders(timing, backendResponse))) response.headers.set(name, value);
    return response;
  } catch (error) {
    return thrownErrorReply(error, sessionId);
  }
}
