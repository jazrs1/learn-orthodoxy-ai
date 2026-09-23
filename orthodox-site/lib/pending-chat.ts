/**
 * Hand a first question to /chat, which sends it on arrival. The same sessionStorage keys are read
 * by app/chat/chat-page.tsx and written by the home page's question box.
 */
export const PENDING_CHAT_MESSAGE_KEY = "orthodox:pending-chat-message";
export const PENDING_CHAT_TOKEN_KEY = "orthodox:pending-chat-token";

export function queueChatMessage(message: string) {
  sessionStorage.setItem(PENDING_CHAT_MESSAGE_KEY, message);
  sessionStorage.setItem(PENDING_CHAT_TOKEN_KEY, `${Date.now()}`);
}
