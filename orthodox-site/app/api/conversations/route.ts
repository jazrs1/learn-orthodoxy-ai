import { NextResponse } from "next/server";
import { getOrCreateAnonymousSessionId } from "../../../lib/chat-auth";
import { createConversation, listConversations } from "../../../lib/conversations";
import { getDatabaseConfigError } from "../../../lib/db";
import { RouteTiming } from "../../../lib/route-timing";

export const runtime = "nodejs";

export async function GET() {
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const conversations = await listConversations(sessionId);
    const response = NextResponse.json({ conversations });
    await getOrCreateAnonymousSessionId(response, sessionId);
    return response;
  } catch (error) {
    const response = NextResponse.json(
      {
        error:
          error instanceof Error && error.message
            ? error.message
            : getDatabaseConfigError(),
      },
      { status: 500 }
    );
    await getOrCreateAnonymousSessionId(response, sessionId);
    return response;
  }
}

export async function POST(request: Request) {
  // A new chat's conversation, created before its first question is sent (timed for RET-018).
  const timing = new RouteTiming("conversation_create");
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const body = (await request.json().catch(() => ({}))) as { title?: string };
    const conversation = await timing.time("db", () => createConversation(sessionId, body.title?.trim() || "New Chat"));
    timing.log();
    const response = NextResponse.json({ conversation }, { headers: { "Server-Timing": timing.serverTiming() } });
    await getOrCreateAnonymousSessionId(response, sessionId);
    return response;
  } catch (error) {
    const response = NextResponse.json(
      {
        error:
          error instanceof Error && error.message
            ? error.message
            : getDatabaseConfigError(),
      },
      { status: 500 }
    );
    await getOrCreateAnonymousSessionId(response, sessionId);
    return response;
  }
}
