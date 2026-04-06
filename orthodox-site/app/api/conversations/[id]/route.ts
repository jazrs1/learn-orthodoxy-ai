import { NextResponse } from "next/server";
import { getOrCreateAnonymousSessionId } from "../../../../lib/chat-auth";
import { archiveConversation, getConversation } from "../../../../lib/conversations";
import { getDatabaseConfigError } from "../../../../lib/db";

export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const { id } = await context.params;
    const conversation = await getConversation(sessionId, id);

    if (!conversation) {
      const notFound = NextResponse.json({ error: "Conversation not found." }, { status: 404 });
      await getOrCreateAnonymousSessionId(notFound, sessionId);
      return notFound;
    }

    const response = NextResponse.json({ conversation });
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

export async function DELETE(_request: Request, context: RouteContext) {
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const { id } = await context.params;
    await archiveConversation(sessionId, id);
    const response = NextResponse.json({ success: true });
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
