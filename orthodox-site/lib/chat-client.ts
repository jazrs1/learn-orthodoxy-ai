// Type-only imports and a .ts path, so `node --test` can load this file (chat-client.test.ts).
import type { ChatMessage, ConversationDetail, ConversationSummary, SaintDetail } from "./chat-types";
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

export type StreamOptions = { signal?: AbortSignal; onDelta: (text: string) => void };

/**
 * Asks for an answer through `streamPath`: `onDelta` receives the text as it is written and the
 * promise resolves with the final `done` payload. A refusal or a saint menu comes back whole as
 * JSON. When the stream can't start, the same request goes to `wholePath`. Aborting `signal`
 * (Stop) rejects with an AbortError.
 */
async function streamRequest<T>(
  streamPath: string,
  wholePath: string,
  payload: unknown,
  { signal, onDelta }: StreamOptions
): Promise<T> {
  const post = (path: string) =>
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  let response: Response;
  try {
    response = await post(streamPath);
  } catch (error) {
    if (signal?.aborted) throw error;
    return readJson<T>(await post(wholePath));
  }
  if (FALLBACK_STATUSES.has(response.status)) return readJson<T>(await post(wholePath));
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok || !response.body || !contentType.includes("text/event-stream")) {
    return readJson<T>(response);
  }
  return readStream<T>(response.body, onDelta);
}

/** A chat answer through /api/chat/stream (fallback /api/chat); resolves with the saved turn. */
export function streamChatRequest(payload: ChatRequestPayload, options: StreamOptions) {
  return streamRequest<ChatResponse>("/api/chat/stream", "/api/chat", payload, options);
}

export type SaintDetailRequestPayload = {
  name: string;
  language: Language;
  /** A menu choice: the entry's ID (RET-010). */
  saintId?: string;
  /** "Looking for a different St. X?" in the saints pane (RET-011). */
  namesakesOf?: string;
};

/** The saints pane's answer through /api/saint-detail/stream (UI-029); nothing is saved. */
export function streamSaintDetail(payload: SaintDetailRequestPayload, options: StreamOptions) {
  return streamRequest<SaintDetail>("/api/saint-detail/stream", "/api/saint-detail", payload, options);
}

export async function readStream<T>(body: ReadableStream<Uint8Array>, onDelta: (text: string) => void): Promise<T> {
  const reader = body.getReader();
  const result: { turn: T | null; failure: StreamError | null } = { turn: null, failure: null };
  const parser = new SseParser(({ event, data }) => {
    if (result.turn || result.failure) return;
    if (event === "delta") onDelta(String(JSON.parse(data).t ?? ""));
    else if (event === "done") result.turn = JSON.parse(data) as T;
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
