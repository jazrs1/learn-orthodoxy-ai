import { ChatMessage, ConversationDetail, ConversationSummary } from "./chat-types";
import { Language } from "./i18n";

type ConversationsResponse = {
  conversations: ConversationSummary[];
};

type ConversationResponse = {
  conversation: ConversationDetail;
};

type ChatResponse = {
  conversation: ConversationSummary;
  userMessage: ChatMessage | null;
  assistantMessage: ChatMessage;
};

/** A failed API call. `message` is the server's text and is not meant for display (UI-008). */
export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
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

export async function sendChatRequest(payload: {
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
}) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<ChatResponse>(response);
}
