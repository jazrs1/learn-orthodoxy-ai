export type SourceRef = {
  source_type?: "pdf" | "website";
  pdf?: string;
  page?: number;
  url?: string | null;
  title?: string | null;
  /** Passage number the answer cites as [n] (backend phase 2+). */
  n?: number;
  /** Backend label, e.g. "Catechism of the Coptic Orthodox Church, Volume 2, p. 31". */
  label?: string;
  /** Saint entry name; not sent by the backend yet (see DECISIONS.md UI-006). */
  entry?: string;
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
