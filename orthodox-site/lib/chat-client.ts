import { ChatMessage, ConversationDetail, ConversationSummary } from "./chat-types";

type ConversationsResponse = {
  conversations: ConversationSummary[];
};

type ConversationResponse = {
  conversation: ConversationDetail;
};

type ChatResponse = {
  conversation: ConversationSummary;
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
};

async function readJson<T>(response: Response): Promise<T> {
  const data = (await response.json().catch(() => ({}))) as T & { error?: string };
  if (!response.ok) {
    throw new Error((data as { error?: string }).error || "Request failed.");
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

export async function sendChatRequest(payload: { question: string; conversationId?: string }) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<ChatResponse>(response);
}
