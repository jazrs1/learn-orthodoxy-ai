import { NextResponse } from "next/server";
import { backendConfigError, backendFetch } from "../../../lib/backend";
import { getOrCreateAnonymousSessionId } from "../../../lib/chat-auth";
import { getRecentHistory, saveChatTurn } from "../../../lib/conversations";
import { getDatabaseConfigError } from "../../../lib/db";
import { ChatMessage, SourceRef } from "../../../lib/chat-types";
import { Language, normalizeLanguage } from "../../../lib/i18n";
import { backendSaintSelection, namesakesFromBackend, optionsFromBackend } from "../../../lib/message-options";

export const runtime = "nodejs";

// Mirrors MAX_QUESTION_CHARS on the backend so the user gets a clear message
// before a network round-trip.
const MAX_QUESTION_CHARS = 1000;

type BackendChatResponse = {
  answer?: string;
  entities?: string[];
  options?: string[];
  option_ids?: string[];
  namesakes?: { label?: string; name?: string } | null;
  sources?: SourceRef[];
};

type ChatRequestBody = {
  question?: string;
  displayQuestion?: string;
  conversationId?: string;
  mode?: "chat" | "saints" | "catechism";
  language?: Language;
  hideUserMessage?: boolean;
  saintId?: string;
  saintName?: string;
  namesakesOf?: string;
};

type ChatMode = "chat" | "saints" | "catechism";

function normalizeAssistantMessage(data: BackendChatResponse): Omit<ChatMessage, "role"> {
  return {
    id: crypto.randomUUID(),
    content: data.answer || "Sorry — I could not generate a response.",
    entities: Array.isArray(data.entities) ? data.entities : [],
    // Saint menus: each option's entry ID, sent back when the option is chosen (RET-010).
    ...optionsFromBackend(data),
    ...(namesakesFromBackend(data) ? { namesakes: namesakesFromBackend(data) } : {}),
    sources: Array.isArray(data.sources)
      ? data.sources.filter(
          (source) =>
            source &&
            (
              (typeof source.pdf === "string" && typeof source.page === "number") ||
              typeof source.url === "string"
            )
        )
      : [],
  };
}

export async function POST(request: Request) {
  const sessionId = await getOrCreateAnonymousSessionId();
  try {
    const body = (await request.json().catch(() => ({}))) as ChatRequestBody;
    const question = body.question?.trim() || "";
    const displayQuestion = body.displayQuestion?.trim() || question;
    const mode: ChatMode =
      body.mode === "saints" || body.mode === "catechism" ? body.mode : "chat";
    const language = normalizeLanguage(body.language);
    const saintSelection = backendSaintSelection(body);

    if (!question) {
      const badRequest = NextResponse.json({ error: "Question is required." }, { status: 400 });
      await getOrCreateAnonymousSessionId(badRequest, sessionId);
      return badRequest;
    }

    if (question.length > MAX_QUESTION_CHARS) {
      const tooLong = NextResponse.json(
        { error: `Question is too long. Please keep it under ${MAX_QUESTION_CHARS} characters.` },
        { status: 400 }
      );
      await getOrCreateAnonymousSessionId(tooLong, sessionId);
      return tooLong;
    }

    const history = body.conversationId
      ? await getRecentHistory(sessionId, body.conversationId, 6)
      : [];

    const configError = backendConfigError();
    if (configError) {
      const missingConfig = NextResponse.json({ error: configError }, { status: 500 });
      await getOrCreateAnonymousSessionId(missingConfig, sessionId);
      return missingConfig;
    }

    const backendResponse = await backendFetch("/chat", {
      request,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        history,
        top_k: 8,
        mode,
        language,
        ...saintSelection,
      }),
      timeoutMs: 20000,
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
      question: displayQuestion,
      assistantMessage: normalizeAssistantMessage(assistantPayload),
      saveUserMessage: !body.hideUserMessage,
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
