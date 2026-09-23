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
  /** The question or saint the passage belongs to (v2 corpus, ING-005). */
  entry?: string;
  /** Printed page or range as a reader finds it in the book, e.g. "33–35" (v2 corpus). */
  pages?: string;
  /** v2 passage id: one source per cited passage. */
  chunk_id?: string;
};

export type NamesakeLink = { label: string; name: string };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  entities?: string[];
  options?: string[];
  /** Saint menus: the entry ID behind each option ("" for a follow-up question), RET-010. */
  optionIds?: string[];
  /** An answer about a bare name's default saint: the "Looking for a different St. X?" link
   * (`name` is sent back as `namesakesOf`), RET-011. */
  namesakes?: NamesakeLink;
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
