export type SourceRef = {
  pdf: string;
  page: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  entities?: string[];
  options?: string[];
  sources?: SourceRef[];
  createdAt?: string;
  isTyping?: boolean;
};

export type ConversationSummary = {
  id: string;
  title: string;
  updatedAt: string;
  createdAt: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessage[];
};

export type ChatBackendHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};
