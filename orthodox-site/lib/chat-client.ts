// Type-only imports and a .ts path, so `node --test` can load this file (chat-client.test.ts).
import type { ChatMessage, ConversationDetail, ConversationSummary } from "./chat-types";
import type { Language } from "./i18n";
import { SseParser } from "./sse.ts";

type ConversationsResponse = {
  conversations: ConversationSummary[];
};

type ConversationResponse = {
  conversation: ConversationDetail;
};

export type ChatResponse = {
  /** Null only when a streamed answer could not be saved (it is still shown). */
  conversation: ConversationSummary | null;
  userMessage: ChatMessage | null;
  assistantMessage: ChatMessage;
};

/** A failed API call. `message` is the server's text and is not meant for display (UI-008). */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readJson<T>(response: Response): Promise<T> {
  const data = (await response.json().catch(() => ({}))) as T & { error?: string };
  if (!response.ok) {
    throw new ApiError((data as { error?: string }).error || "Request failed.", response.status);
  }
  return data;
}

export async function fetchConversationList() {
  const response = await fetch("/api/conversations", { cache: "no-store" });
  const data = await readJson<ConversationsResponse>(response);
  return data.conversations;
}

export async function createConversationRequest() {
  const response = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await readJson<{ conversation: ConversationSummary }>(response);
  return data.conversation;
}

export async function fetchConversation(conversationId: string) {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    cache: "no-store",
  });
  const data = await readJson<ConversationResponse>(response);
  return data.conversation;
}

export async function deleteConversationRequest(conversationId: string) {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
  await readJson<{ success: boolean }>(response);
}

export type ChatRequestPayload = {
  question: string;
  displayQuestion?: string;
  conversationId?: string;
  mode?: "chat" | "saints" | "catechism";
  language?: Language;
  hideUserMessage?: boolean;
  /** A namesake-menu choice: the entry's ID (RET-010). */
  saintId?: string;
  /** A saint named exactly (a menu choice saved without an ID). */
  saintName?: string;
  /** "Looking for a different St. X?": the menu of that name's other saints (RET-011). */
  namesakesOf?: string;
};

export async function sendChatRequest(payload: ChatRequestPayload, signal?: AbortSignal) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  return readJson<ChatResponse>(response);
}

/** The backend reported a failure after the answer had started (an `error` event). */
export class StreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamError";
  }
}

// The streaming path isn't there (the route or the backend's /chat/stream not deployed yet, a
// gateway error before anything was sent): the same request goes to /api/chat (GEN-007). Not on
// 400, 429, 500 or 503: those are the backend's real answer, and asking twice would count twice
// against the rate limit.
const FALLBACK_STATUSES = new Set([404, 405, 502, 504]);

/**
 * Asks for an answer through /api/chat/stream: `onDelta` receives the text as it is written and
 * the promise resolves with the saved turn, as `sendChatRequest` does. A refusal or a saint menu
 * comes back whole. Aborting `signal` (Stop) rejects with an AbortError.
 */
export async function streamChatRequest(
  payload: ChatRequestPayload,
  { signal, onDelta }: { signal?: AbortSignal; onDelta: (text: string) => void }
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    return sendChatRequest(payload, signal);
  }
  if (FALLBACK_STATUSES.has(response.status)) return sendChatRequest(payload, signal);
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok || !response.body || !contentType.includes("text/event-stream")) {
    return readJson<ChatResponse>(response);
  }
  return readChatStream(response.body, onDelta);
}

export async function readChatStream(
  body: ReadableStream<Uint8Array>,
  onDelta: (text: string) => void
): Promise<ChatResponse> {
  const reader = body.getReader();
  const result: { turn: ChatResponse | null; failure: StreamError | null } = { turn: null, failure: null };
  const parser = new SseParser(({ event, data }) => {
    if (result.turn || result.failure) return;
    if (event === "delta") onDelta(String(JSON.parse(data).t ?? ""));
    else if (event === "done") result.turn = JSON.parse(data) as ChatResponse;
    else if (event === "error") result.failure = new StreamError(String(JSON.parse(data).message || "Stream failed."));
  });
  let ended = false;
  try {
    while (!result.turn && !result.failure) {
      const { value, done } = await reader.read();
      if (done) {
        ended = true;
        parser.end();
        break;
      }
      parser.push(value);
    }
  } finally {
    if (!ended) void reader.cancel().catch(() => undefined);
    else reader.releaseLock();
  }
  if (result.failure) throw result.failure;
  if (!result.turn) throw new StreamError("The answer stream ended early.");
  return result.turn;
}
