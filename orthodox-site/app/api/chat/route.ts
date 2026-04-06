import { NextResponse } from "next/server";
import { getOrCreateAnonymousSessionId } from "../../../lib/chat-auth";
import { getRecentHistory, saveChatTurn } from "../../../lib/conversations";
import { getDatabaseConfigError } from "../../../lib/db";
import { ChatMessage, SourceRef } from "../../../lib/chat-types";

export const runtime = "nodejs";

type BackendChatResponse = {
  answer?: string;
  entities?: string[];
  options?: string[];
  sources?: SourceRef[];
};

type ChatRequestBody = {
  question?: string;
  conversationId?: string;
};

function backendUrl() {
  const value = process.env.ORTHODOX_API_URL || process.env.NEXT_PUBLIC_API_URL || "";
  return value.trim().replace(/\/+$/, "");
}

function normalizeAssistantMessage(data: BackendChatResponse): Omit<ChatMessage, "role"> {
  return {
    id: crypto.randomUUID(),
    content: data.answer || "Sorry — I could not generate a response.",
    entities: Array.isArray(data.entities) ? data.entities : [],
    options: Array.isArray(data.options) ? data.options : [],
    sources: Array.isArray(data.sources)
      ? data.sources.filter(
          (source) =>
            source &&
            typeof source.pdf === "string" &&
            typeof source.page === "number"
        )
      : [],
  };
}

export async function POST(request: Request) {
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const body = (await request.json().catch(() => ({}))) as ChatRequestBody;
    const question = body.question?.trim() || "";

    if (!question) {
      const badRequest = NextResponse.json({ error: "Question is required." }, { status: 400 });
      await getOrCreateAnonymousSessionId(badRequest, sessionId);
      return badRequest;
    }

    const history = body.conversationId
      ? await getRecentHistory(sessionId, body.conversationId, 6)
      : [];

    const apiBaseUrl = backendUrl();
    if (!apiBaseUrl) {
      const missingConfig = NextResponse.json(
        {
          error:
            "The backend API URL is not configured. Set ORTHODOX_API_URL or NEXT_PUBLIC_API_URL.",
        },
        { status: 500 }
      );
      await getOrCreateAnonymousSessionId(missingConfig, sessionId);
      return missingConfig;
    }

    const backendResponse = await fetch(`${apiBaseUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        history,
        top_k: 8,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(20000),
    });

    let assistantPayload: BackendChatResponse;
    if (backendResponse.ok) {
      assistantPayload = (await backendResponse.json()) as BackendChatResponse;
    } else {
      const data = (await backendResponse.json().catch(() => ({}))) as { detail?: string };
      const errorResponse = NextResponse.json(
        {
          error:
            data.detail ||
            "The Orthodox AI backend returned an error while generating a response.",
        },
        { status: backendResponse.status >= 400 ? backendResponse.status : 502 }
      );
      await getOrCreateAnonymousSessionId(errorResponse, sessionId);
      return errorResponse;
    }

    const saved = await saveChatTurn({
      sessionId,
      conversationId: body.conversationId,
      question,
      assistantMessage: normalizeAssistantMessage(assistantPayload),
    });

    const response = NextResponse.json({
      conversation: saved.conversation,
      userMessage: saved.userMessage,
      assistantMessage: saved.assistantMessage,
    });
    await getOrCreateAnonymousSessionId(response, sessionId);
    return response;
  } catch (error) {
    const message =
      error instanceof Error && error.name !== "TimeoutError"
        ? error.message
        : "The Orthodox AI backend is unreachable right now. Please try again in a moment.";
    const response = NextResponse.json(
      {
        error:
          message.includes("POSTGRES_URL") || message.includes("DATABASE_URL")
            ? getDatabaseConfigError()
            : message,
      },
      { status: 500 }
    );
    await getOrCreateAnonymousSessionId(response, sessionId);
    return response;
  }
}
