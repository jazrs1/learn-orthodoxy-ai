"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ChatShell from "../../components/ChatShell";
import ChatSidebar from "../../components/ChatSidebar";
import InteractiveAnswer from "../../components/InteractiveAnswer";
import { buildSaintLookup, isValidSaintName } from "../../components/saintNameUtils";
import {
  createConversationRequest,
  deleteConversationRequest,
  fetchConversation,
  fetchConversationList,
  sendChatRequest,
} from "../../lib/chat-client";
import { ChatMessage, ConversationDetail, ConversationSummary } from "../../lib/chat-types";

type SaintsListResponse = {
  saints?: string[];
  total?: number;
};

type CatechismPrompt = {
  label: string;
  prompt: string;
};

const SAINTS_PAGE_SIZE = 200;
const DEFAULT_ERROR =
  "Sorry — I could not reach the Orthodox AI server. Please try again in a moment.";
const CATECHISM_PROMPTS: CatechismPrompt[] = [
  { label: "Prayer", prompt: "What does the catechism say about prayer?" },
  { label: "Salvation", prompt: "What does the catechism teach about salvation?" },
  { label: "Sacraments", prompt: "What does the catechism say about the sacraments?" },
  { label: "Fasting", prompt: "What does the catechism say about fasting?" },
  { label: "The Church", prompt: "What does the catechism teach about the Church?" },
  { label: "Repentance", prompt: "What does the catechism say about repentance and confession?" },
];

function sendTextToInputAndSubmit(text: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent("chat:insertAndSubmitText", {
      detail: text.trim(),
    })
  );
}

function optimisticMessage(id: string, role: "user" | "assistant", content: string): ChatMessage {
  return {
    id,
    role,
    content,
    entities: [],
    options: [],
    sources: [],
  };
}

function mergeConversationSummary(
  conversations: ConversationSummary[],
  nextConversation: ConversationSummary
) {
  return [nextConversation, ...conversations.filter((conversation) => conversation.id !== nextConversation.id)];
}

function ChatPageContent() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [conversationsError, setConversationsError] = useState("");
  const [activeConversationId, setActiveConversationId] = useState("");
  const [currentConversation, setCurrentConversation] = useState<ConversationDetail | null>(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationError, setConversationError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "saints" | "catechism">("chat");
  const [saints, setSaints] = useState<string[]>([]);
  const [saintsTotal, setSaintsTotal] = useState(0);
  const [saintsLoading, setSaintsLoading] = useState(false);
  const [saintsError, setSaintsError] = useState("");
  const [saintSearch, setSaintSearch] = useState("");
  const searchParams = useSearchParams();
  const router = useRouter();
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const saintsListRef = useRef<HTMLDivElement>(null);
  const saintsLoadingRef = useRef(false);
  const handledQueryRef = useRef("");
  const handledChatRef = useRef("");
  const handledNewRef = useRef("");

  const saintLookup = useMemo(() => buildSaintLookup(saints), [saints]);
  const messages = useMemo(() => currentConversation?.messages || [], [currentConversation]);
  const backendUrl = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "");

  const loadConversationList = useCallback(async () => {
    try {
      setConversationsLoading(true);
      setConversationsError("");
      const nextConversations = await fetchConversationList();
      setConversations(nextConversations);
      return nextConversations;
    } catch (error) {
      setConversationsError(error instanceof Error ? error.message : "Unable to load chats.");
      return [];
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  const loadConversationDetail = useCallback(async (conversationId: string) => {
    try {
      setConversationLoading(true);
      setConversationError("");
      const conversation = await fetchConversation(conversationId);
      setCurrentConversation(conversation);
      setActiveConversationId(conversation.id);
      return conversation;
    } catch (error) {
      setConversationError(error instanceof Error ? error.message : "Unable to load chat.");
      return null;
    } finally {
      setConversationLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConversationList();
  }, [loadConversationList]);

  useEffect(() => {
    const el = chatMessagesRef.current;
    if (!el || activeTab !== "chat") return;
    el.scrollTop = el.scrollHeight;
  }, [messages, isSending, activeTab]);

  useEffect(() => {
    saintsLoadingRef.current = saintsLoading;
  }, [saintsLoading]);

  const loadSaintsPage = useCallback(
    async ({
      reset = false,
      query,
      offset,
    }: {
      reset?: boolean;
      query?: string;
      offset?: number;
    } = {}) => {
      if (saintsLoadingRef.current) return;

      const normalizedQuery = (query ?? saintSearch).trim();
      const nextOffset = typeof offset === "number" ? offset : 0;

      saintsLoadingRef.current = true;
      setSaintsLoading(true);
      if (reset) {
        setSaintsError("");
      }

      try {
        if (!backendUrl) {
          throw new Error(
            "Saints search is unavailable because NEXT_PUBLIC_API_URL is not configured."
          );
        }

        const params = new URLSearchParams({
          limit: String(SAINTS_PAGE_SIZE),
          offset: String(nextOffset),
        });
        if (normalizedQuery) {
          params.set("q", normalizedQuery);
        }

        const response = await fetch(`${backendUrl}/saints?${params.toString()}`, {
          signal: AbortSignal.timeout(15000),
        });
        if (!response.ok) throw new Error("Failed to load saints list");
        const data = (await response.json()) as SaintsListResponse;
        const nextNames = Array.isArray(data.saints)
          ? data.saints.filter((name) => typeof name === "string" && name.trim())
          : [];

        setSaints((prev) => (reset ? nextNames : [...prev, ...nextNames]));
        setSaintsTotal(typeof data.total === "number" ? data.total : nextNames.length);
        setSaintsError("");
      } catch (error) {
        setSaintsError(error instanceof Error ? error.message : "Unable to load saints list.");
      } finally {
        saintsLoadingRef.current = false;
        setSaintsLoading(false);
      }
    },
    [backendUrl, saintSearch]
  );

  useEffect(() => {
    setSaints([]);
    setSaintsTotal(0);
    if (saintsListRef.current) {
      saintsListRef.current.scrollTop = 0;
    }
    void loadSaintsPage({ reset: true, query: saintSearch, offset: 0 });
  }, [loadSaintsPage, saintSearch]);

  useEffect(() => {
    const el = saintsListRef.current;
    if (!el) return;

    const handleScroll = () => {
      if (saintsLoading || saints.length >= saintsTotal) return;
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      if (distanceFromBottom < 160) {
        void loadSaintsPage({ query: saintSearch, offset: saints.length });
      }
    };

    el.addEventListener("scroll", handleScroll);
    return () => {
      el.removeEventListener("scroll", handleScroll);
    };
  }, [loadSaintsPage, saintSearch, saints.length, saintsLoading, saintsTotal]);

  const startNewChat = useCallback(async () => {
    try {
      const conversation = await createConversationRequest();
      setConversations((prev) => mergeConversationSummary(prev, conversation));
      setCurrentConversation({ ...conversation, messages: [] });
      setActiveConversationId(conversation.id);
      setActiveTab("chat");
      router.replace(`/chat?chat=${encodeURIComponent(conversation.id)}`, { scroll: false });
      return conversation.id;
    } catch (error) {
      setConversationError(error instanceof Error ? error.message : "Unable to create chat.");
      return "";
    }
  }, [router]);

  const selectSession = useCallback(
    async (conversationId: string) => {
      await loadConversationDetail(conversationId);
      setActiveTab("chat");
      router.replace(`/chat?chat=${encodeURIComponent(conversationId)}`, { scroll: false });
    },
    [loadConversationDetail, router]
  );

  const deleteSession = useCallback(
    async (conversationId: string) => {
      try {
        await deleteConversationRequest(conversationId);
        setConversations((prev) => prev.filter((conversation) => conversation.id !== conversationId));
        if (activeConversationId === conversationId) {
          setActiveConversationId("");
          setCurrentConversation(null);
        }
      } catch (error) {
        setConversationsError(error instanceof Error ? error.message : "Unable to delete chat.");
      }
    },
    [activeConversationId]
  );

  const submitQuestion = useCallback(
    async (rawQuestion: string, preferredConversationId?: string) => {
      const question = rawQuestion.trim();
      if (!question || isSending) return;

      let conversationId = preferredConversationId || activeConversationId;
      if (!conversationId) {
        conversationId = await startNewChat();
      }
      if (!conversationId) return;

      const optimisticUserId = crypto.randomUUID();
      const optimisticAssistantId = crypto.randomUUID();
      const nextMessages = [
        ...((currentConversation?.id === conversationId ? currentConversation.messages : []) || []),
        optimisticMessage(optimisticUserId, "user", question),
        { ...optimisticMessage(optimisticAssistantId, "assistant", ""), isTyping: true },
      ];

      setCurrentConversation((prev) =>
        prev && prev.id === conversationId
          ? { ...prev, messages: nextMessages }
          : {
              id: conversationId,
              title: prev?.title || "New Chat",
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              messages: nextMessages,
            }
      );

      setActiveConversationId(conversationId);
      setActiveTab("chat");
      setConversationError("");
      setIsSending(true);

      try {
        const result = await sendChatRequest({ question, conversationId });
        setConversations((prev) => mergeConversationSummary(prev, result.conversation));
        setCurrentConversation((prev) => {
          const baseMessages = prev?.messages.filter(
            (message) => message.id !== optimisticUserId && message.id !== optimisticAssistantId
          ) || [];

          return {
            ...result.conversation,
            messages: [...baseMessages, result.userMessage, result.assistantMessage],
          };
        });
        router.replace(`/chat?chat=${encodeURIComponent(result.conversation.id)}`, { scroll: false });
      } catch (error) {
        const message = error instanceof Error ? error.message : DEFAULT_ERROR;
        setConversationError(message);
        setCurrentConversation((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.map((entry) =>
              entry.id === optimisticAssistantId
                ? { ...entry, content: message, isTyping: false }
                : entry
            ),
          };
        });
      } finally {
        setIsSending(false);
      }
    },
    [activeConversationId, currentConversation, isSending, router, startNewChat]
  );

  useEffect(() => {
    const q = searchParams.get("q")?.trim() || "";
    const chatId = searchParams.get("chat") || "";
    const isNew = searchParams.get("new") || "";

    if (q && q !== handledQueryRef.current) {
      handledQueryRef.current = q;
      void (async () => {
        const conversationId = await startNewChat();
        if (conversationId) {
          await submitQuestion(q, conversationId);
        }
        router.replace(`/chat${conversationId ? `?chat=${encodeURIComponent(conversationId)}` : ""}`, {
          scroll: false,
        });
      })();
      return;
    }

    if (isNew && isNew !== handledNewRef.current) {
      handledNewRef.current = isNew;
      void startNewChat();
      return;
    }

    if (chatId && chatId !== handledChatRef.current) {
      handledChatRef.current = chatId;
      void loadConversationDetail(chatId);
      return;
    }

    if (!chatId && !q && !isNew && conversations.length > 0 && !activeConversationId && !conversationLoading) {
      void loadConversationDetail(conversations[0].id);
    }
  }, [
    activeConversationId,
    conversationLoading,
    conversations,
    loadConversationDetail,
    router,
    searchParams,
    startNewChat,
    submitQuestion,
  ]);

  const submitSaintLookup = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    sendTextToInputAndSubmit(`search saint: ${trimmed}`);
  }, []);

  const selectSaint = useCallback(
    (name: string) => {
      if (!isValidSaintName(name, saintLookup)) return;
      submitSaintLookup(name);
      setActiveTab("chat");
    },
    [saintLookup, submitSaintLookup]
  );

  return (
    <main className="chat-page">
      <div className="chat-layout">
        <section className="chat-window">
          <div className="chat-window-header">
            <div className="chat-window-top">
              <div>
                <h1 className="chat-page-title">Learn Orthodoxy</h1>
                <p className="chat-page-subtitle">
                  Ask about Scripture, saints, theology, liturgy, catechism, and Church history.
                </p>
              </div>
              <div className="chat-header-actions">
                <button type="button" className="chat-header-btn" onClick={() => router.push("/")}>
                  Close
                </button>
              </div>
            </div>

            <div className="chat-tabs">
              <button
                type="button"
                className={`chat-tab ${activeTab === "chat" ? "chat-tab-active" : ""}`}
                onClick={() => setActiveTab("chat")}
              >
                Chat
              </button>
              <button
                type="button"
                className={`chat-tab ${activeTab === "saints" ? "chat-tab-active" : ""}`}
                onClick={() => setActiveTab("saints")}
              >
                Saints Search
              </button>
              <button
                type="button"
                className={`chat-tab ${activeTab === "catechism" ? "chat-tab-active" : ""}`}
                onClick={() => setActiveTab("catechism")}
              >
                Catechism
              </button>
            </div>
          </div>

          {activeTab === "chat" ? (
            <div className="chat-messages" ref={chatMessagesRef}>
              {conversationError ? <div className="chat-empty-state">{conversationError}</div> : null}
              {conversationLoading ? <div className="chat-empty-state">Loading chat...</div> : null}
              {!conversationLoading && messages.length ? (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`message-row ${message.role === "user" ? "user-row" : "assistant-row"}`}
                  >
                    <div
                      className={`message-bubble ${
                        message.role === "user" ? "user-bubble" : "assistant-bubble"
                      }`}
                    >
                      {message.role === "assistant" ? (
                        message.isTyping ? (
                          <div className="typing-dots" aria-label="Assistant is typing" role="status">
                            <span />
                            <span />
                            <span />
                          </div>
                        ) : (
                          <>
                            <InteractiveAnswer
                              answer={message.content}
                              entities={message.entities}
                              saintLookup={saintLookup}
                            />
                            {message.options && message.options.length > 0 ? (
                              <div className="message-options">
                                <div className="message-options-label">Choose a saint</div>
                                <div className="message-options-list">
                                  {Array.from(new Set(message.options.map((option) => option.trim())))
                                    .filter((option) => isValidSaintName(option, saintLookup))
                                    .map((option) => (
                                      <button
                                        key={option}
                                        type="button"
                                        className="message-option-chip"
                                        onClick={() => submitSaintLookup(option)}
                                      >
                                        {option}
                                      </button>
                                    ))}
                                </div>
                              </div>
                            ) : null}
                            {message.sources && message.sources.length > 0 ? (
                              <div className="message-sources">
                                <div className="message-sources-label">Sources</div>
                                <div className="message-sources-list">
                                  {Array.from(
                                    new Map(
                                      message.sources.map((source) => [
                                        `${source.pdf}-${source.page}`,
                                        source,
                                      ])
                                    ).values()
                                  ).map((source) => (
                                    <Link
                                      key={`${source.pdf}-${source.page}`}
                                      href={`/sources?pdf=${encodeURIComponent(
                                        source.pdf
                                      )}&page=${source.page}`}
                                      className="message-source-chip"
                                    >
                                      {source.pdf.replace(".pdf", "")} p.{source.page}
                                    </Link>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </>
                        )
                      ) : (
                        message.content
                      )}
                    </div>
                  </div>
                ))
              ) : !conversationLoading && !conversationError ? (
                <div className="chat-empty-state">Start by asking a question below.</div>
              ) : null}
            </div>
          ) : activeTab === "saints" ? (
            <div className="saints-tab-panel">
              <div className="saints-tab-search">
                <input
                  type="text"
                  className="saints-search-input"
                  value={saintSearch}
                  onChange={(event) => setSaintSearch(event.target.value)}
                  placeholder="Search saints..."
                />
              </div>

              <div className="saints-list-shell" ref={saintsListRef}>
                {saintsLoading ? <div className="chat-empty-state">Loading saints...</div> : null}
                {saintsError ? <div className="chat-empty-state">{saintsError}</div> : null}
                {!saintsLoading && !saintsError ? (
                  saints.length > 0 ? (
                    saints.map((name) => (
                      <button
                        key={name}
                        type="button"
                        className="saints-list-item"
                        onClick={() => selectSaint(name)}
                      >
                        {name}
                      </button>
                    ))
                  ) : (
                    <div className="chat-empty-state">No saints found for that search.</div>
                  )
                ) : null}
                {!saintsLoading && !saintsError && saints.length > 0 && saints.length < saintsTotal ? (
                  <div className="chat-empty-state">Scroll to load more saints...</div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="catechism-tab-panel">
              <div className="catechism-panel-copy">
                <h2 className="catechism-panel-title">Catechism Topics</h2>
                <p className="catechism-panel-text">
                  Ask focused questions from the catechism volumes on doctrine, prayer,
                  sacraments, repentance, and Christian life.
                </p>
              </div>
              <div className="catechism-prompt-grid">
                {CATECHISM_PROMPTS.map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    className="catechism-prompt-card"
                    onClick={() => {
                      sendTextToInputAndSubmit(item.prompt);
                      setActiveTab("chat");
                    }}
                  >
                    <span className="catechism-prompt-label">{item.label}</span>
                    <span className="catechism-prompt-text">{item.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="chat-bottom-bar">
            <ChatShell onSubmit={submitQuestion} />
          </div>
        </section>

        <ChatSidebar
          sessions={conversations}
          activeSessionId={activeConversationId}
          onSelectSession={selectSession}
          onNewChat={() => void startNewChat()}
          onDeleteSession={(conversationId) => void deleteSession(conversationId)}
          loading={conversationsLoading}
          error={conversationsError}
        />
      </div>
    </main>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<main className="chat-page" />}>
      <ChatPageContent />
    </Suspense>
  );
}
