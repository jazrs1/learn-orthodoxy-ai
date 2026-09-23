import "server-only";

import { NextResponse } from "next/server";
import { backendConfigError } from "./backend";
import { getOrCreateAnonymousSessionId } from "./chat-auth";
import { getRecentHistory, saveChatTurn } from "./conversations";
import { getDatabaseConfigError } from "./db";
import type { ChatMessage, SourceRef } from "./chat-types";
import { Language, normalizeLanguage } from "./i18n";
import { backendSaintSelection, namesakesFromBackend, optionsFromBackend } from "./message-options";
import type { RouteTiming } from "./route-timing";

// Shared by /api/chat and /api/chat/stream (GEN-007): the same checks, history, backend request,
// saving and error text, so the two routes differ only in how the answer travels.

// Mirrors MAX_QUESTION_CHARS on the backend so the user gets a clear message
// before a network round-trip.
const MAX_QUESTION_CHARS = 1000;

export type BackendChatResponse = {
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

export type PreparedChat = {
  sessionId: string;
  conversationId?: string;
  displayQuestion: string;
  hideUserMessage: boolean;
  /** JSON body for the backend's /chat or /chat/stream. */
  backendBody: string;
};

export function normalizeAssistantMessage(data: BackendChatResponse): Omit<ChatMessage, "role"> {
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

/** A JSON reply that also sets the anonymous session cookie when it is new. */
export async function jsonWithSession(body: unknown, sessionId: string, status = 200) {
  const response = NextResponse.json(body, { status });
  await getOrCreateAnonymousSessionId(response, sessionId);
  return response;
}

/** Validates the browser's request and builds the backend's, or returns the error reply. */
export async function prepareChat(
  request: Request,
  sessionId: string,
  timing?: RouteTiming
): Promise<PreparedChat | NextResponse> {
  const body = (await request.json().catch(() => ({}))) as ChatRequestBody;
  const question = body.question?.trim() || "";
  const displayQuestion = body.displayQuestion?.trim() || question;
  const mode: ChatMode =
    body.mode === "saints" || body.mode === "catechism" ? body.mode : "chat";
  const language = normalizeLanguage(body.language);
  const saintSelection = backendSaintSelection(body);

  if (!question) {
    return jsonWithSession({ error: "Question is required." }, sessionId, 400);
  }

  if (question.length > MAX_QUESTION_CHARS) {
    return jsonWithSession(
      { error: `Question is too long. Please keep it under ${MAX_QUESTION_CHARS} characters.` },
      sessionId,
      400
    );
  }

  // The conversation so far, read from Postgres (Neon in production).
  const readHistory = () =>
    body.conversationId ? getRecentHistory(sessionId, body.conversationId, 6) : Promise.resolve([]);
  const history = timing ? await timing.time("history", readHistory) : await readHistory();
  timing?.set({ history_messages: history.length });

  const configError = backendConfigError();
  if (configError) {
    return jsonWithSession({ error: configError }, sessionId, 500);
  }

  return {
    sessionId,
    conversationId: body.conversationId,
    displayQuestion,
    hideUserMessage: Boolean(body.hideUserMessage),
    backendBody: JSON.stringify({
      question,
      history,
      top_k: 8,
      mode,
      language,
      ...saintSelection,
    }),
  };
}

/** Saves the finished turn; the reply the browser gets once the answer is complete. */
export async function saveAnswer(chat: PreparedChat, data: BackendChatResponse) {
  const saved = await saveChatTurn({
    sessionId: chat.sessionId,
    conversationId: chat.conversationId,
    question: chat.displayQuestion,
    assistantMessage: normalizeAssistantMessage(data),
    saveUserMessage: !chat.hideUserMessage,
  });
  return {
    conversation: saved.conversation,
    userMessage: saved.userMessage,
    assistantMessage: saved.assistantMessage,
  };
}

/** The backend answered with an error status: its message, or a generic one. */
export async function backendErrorReply(backendResponse: Response, sessionId: string) {
  const data = (await backendResponse.json().catch(() => ({}))) as { detail?: string };
  return jsonWithSession(
    {
      error:
        data.detail ||
        "The Orthodox AI backend returned an error while generating a response.",
    },
    sessionId,
    backendResponse.status >= 400 ? backendResponse.status : 502
  );
}

/** A request that threw (timeout, network, database): the error reply. */
export function thrownErrorReply(error: unknown, sessionId: string) {
  const message =
    error instanceof Error && error.name !== "TimeoutError"
      ? error.message
      : "The Orthodox AI backend is unreachable right now. Please try again in a moment.";
  return jsonWithSession(
    {
      error:
        message.includes("POSTGRES_URL") || message.includes("DATABASE_URL")
          ? getDatabaseConfigError()
          : message,
    },
    sessionId,
    500
  );
}
