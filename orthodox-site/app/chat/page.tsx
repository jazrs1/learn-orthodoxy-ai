"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
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

type CatechismTopic = {
  title: string;
  description: string;
  prompts: CatechismPrompt[];
};

const SAINTS_PAGE_SIZE = 200;
const DEFAULT_ERROR =
  "Sorry — I could not reach the Orthodox AI server. Please try again in a moment.";
const PENDING_CHAT_MESSAGE_KEY = "orthodox:pending-chat-message";
const PENDING_CHAT_TOKEN_KEY = "orthodox:pending-chat-token";
const CATECHISM_TOPICS: CatechismTopic[] = [
  {
    title: "Prayer",
    description: "Daily prayer, worship, and the inner life with God.",
    prompts: [
      { label: "Prayer", prompt: "Why is prayer essential in the Coptic Orthodox life?" },
      { label: "Lord's Prayer", prompt: "How does the Coptic Orthodox Church explain the Lord's Prayer?" },
      { label: "Rule", prompt: "What guidance does the Coptic Orthodox Church give for a daily prayer rule?" },
    ],
  },
  {
    title: "Salvation",
    description: "Grace, repentance, faith, and life in Christ.",
    prompts: [
      { label: "Salvation", prompt: "What does the Coptic Orthodox Church teach about salvation?" },
      { label: "Faith", prompt: "How does the Coptic Orthodox Church explain faith and works in salvation?" },
      { label: "Cross", prompt: "Why is the cross central to salvation in Coptic Orthodox teaching?" },
    ],
  },
  {
    title: "Sacraments",
    description: "The mysteries of the Church and how grace is received.",
    prompts: [
      { label: "Sacraments", prompt: "What are the seven sacraments in the Coptic Orthodox Church?" },
      { label: "Eucharist", prompt: "What does the Coptic Orthodox Church teach about the Eucharist?" },
      { label: "Baptism", prompt: "Why is baptism necessary according to the Coptic Orthodox Church?" },
    ],
  },
  {
    title: "Repentance",
    description: "Confession, spiritual struggle, and returning to God.",
    prompts: [
      { label: "Confession", prompt: "What does the Coptic Orthodox Church teach about confession and repentance?" },
      { label: "Repentance", prompt: "What are the signs of true repentance in Coptic Orthodox teaching?" },
      { label: "Temptation", prompt: "How should someone respond after falling again into the same sin?" },
    ],
  },
  {
    title: "The Church",
    description: "The nature of the Church, tradition, and belonging to the body of Christ.",
    prompts: [
      { label: "Church", prompt: "What does the Coptic Orthodox Church teach about the Church itself?" },
      { label: "Tradition", prompt: "Why is Holy Tradition important in the Coptic Orthodox Church?" },
      { label: "Saints", prompt: "How does the Coptic Orthodox Church explain communion with the saints?" },
    ],
  },
  {
    title: "Fasting",
    description: "Ascetic discipline, self-control, and preparation for holiness.",
    prompts: [
      { label: "Fasting", prompt: "Why does the Coptic Orthodox Church place such emphasis on fasting?" },
      { label: "Purpose", prompt: "What is the spiritual purpose of fasting in the Coptic Orthodox Church?" },
      { label: "Prayer", prompt: "How should fasting be joined with prayer and repentance?" },
    ],
  },
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

function mergeUniqueSaints(current: string[], next: string[]) {
  const seen = new Set<string>();
  const merged: string[] = [];

  for (const name of [...current, ...next]) {
    const trimmed = name.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(trimmed);
  }

  return merged;
}

function submitCatechismPrompt(prompt: string, setActiveTab: (tab: "chat" | "saints" | "catechism") => void) {
  sendTextToInputAndSubmit(prompt);
  setActiveTab("chat");
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
  const [isDraftChat, setIsDraftChat] = useState(false);
  const [composerInitialValue, setComposerInitialValue] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState("");
  const [activeTab, setActiveTab] = useState<"chat" | "saints" | "catechism">("chat");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [pendingAutoSubmitText, setPendingAutoSubmitText] = useState("");
  const [saints, setSaints] = useState<string[]>([]);
  const [saintsTotal, setSaintsTotal] = useState(0);
  const [saintsLoading, setSaintsLoading] = useState(false);
  const [saintsError, setSaintsError] = useState("");
  const [saintSearch, setSaintSearch] = useState("");
  const searchParams = useSearchParams();
  const router = useRouter();
  const latestUserMessageRef = useRef<HTMLDivElement | null>(null);
  const saintsListRef = useRef<HTMLDivElement>(null);
  const saintsLoadingRef = useRef(false);
  const submittingRef = useRef(false);
  const pendingScrollToUserMessageRef = useRef(false);
  const createdConversationRef = useRef(false);
  const processedQuestionRef = useRef("");
  const handledChatRef = useRef("");

  const saintLookup = useMemo(() => buildSaintLookup(saints), [saints]);
  const messages = useMemo(() => currentConversation?.messages || [], [currentConversation]);
  const latestUserMessageId = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === "user") return messages[index].id;
    }
    return "";
  }, [messages]);
  const hasMoreSaints = saints.length < saintsTotal;

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
    if (!pendingScrollToUserMessageRef.current || activeTab !== "chat") return;

    requestAnimationFrame(() => {
      latestUserMessageRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      pendingScrollToUserMessageRef.current = false;
    });
  }, [messages, activeTab]);

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
        const params = new URLSearchParams({
          limit: String(SAINTS_PAGE_SIZE),
          offset: String(nextOffset),
        });
        if (normalizedQuery) {
          params.set("q", normalizedQuery);
        }

        const response = await fetch(`/api/saints?${params.toString()}`, {
          signal: AbortSignal.timeout(15000),
        });
        if (!response.ok) throw new Error("Failed to load saints list");
        const data = (await response.json()) as SaintsListResponse;
        const nextNames = Array.isArray(data.saints)
          ? data.saints.filter((name) => typeof name === "string" && name.trim())
          : [];

        setSaints((prev) => (reset ? nextNames : mergeUniqueSaints(prev, nextNames)));
        setSaintsTotal(typeof data.total === "number" ? data.total : nextNames.length);
        setSaintsError("");
      } catch (error) {
        setSaintsError(error instanceof Error ? error.message : "Unable to load saints list.");
      } finally {
        saintsLoadingRef.current = false;
        setSaintsLoading(false);
      }
    },
    [saintSearch]
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

  useEffect(() => {
    const el = saintsListRef.current;
    if (!el || saintsLoading || saintsError || !hasMoreSaints) return;

    if (el.scrollHeight <= el.clientHeight + 24) {
      void loadSaintsPage({ query: saintSearch, offset: saints.length });
    }
  }, [hasMoreSaints, loadSaintsPage, saintSearch, saints.length, saintsError, saintsLoading]);

  const startNewChat = useCallback(async (options?: { updateRoute?: boolean }) => {
    const updateRoute = options?.updateRoute ?? true;

    handledChatRef.current = "";
    pendingScrollToUserMessageRef.current = false;
    setCurrentConversation(null);
    setActiveConversationId("");
    setConversationError("");
    setActiveTab("chat");
    setIsDraftChat(true);
    setComposerInitialValue("");
    if (updateRoute) {
      router.replace("/chat", { scroll: false });
    }
    console.debug("[chat] draft chat started");
    return "";
  }, [router]);

  const selectSession = useCallback(
    async (conversationId: string) => {
      setIsDraftChat(false);
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

  const handleSendMessage = useCallback(
    async (rawQuestion: string) => {
      const question = rawQuestion.trim();
      if (!question || submittingRef.current) return;

      let conversationId = activeConversationId;
      if (!conversationId && createdConversationRef.current) {
        console.debug("[chat] duplicate conversation creation blocked");
        return;
      }

      const localConversationId = conversationId || `draft-${crypto.randomUUID()}`;

      const optimisticUserId = crypto.randomUUID();
      const optimisticAssistantId = crypto.randomUUID();
      const nextMessages = [
        ...((currentConversation?.id === localConversationId ? currentConversation.messages : []) || []),
        optimisticMessage(optimisticUserId, "user", question),
        { ...optimisticMessage(optimisticAssistantId, "assistant", ""), isTyping: true },
      ];

      pendingScrollToUserMessageRef.current = true;

      setCurrentConversation((prev) =>
        prev && prev.id === localConversationId
          ? { ...prev, messages: nextMessages }
          : {
              id: localConversationId,
              title: prev?.title || "New Chat",
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              messages: nextMessages,
            }
      );

      if (conversationId) {
        setActiveConversationId(conversationId);
      }
      setActiveTab("chat");
      setConversationError("");
      submittingRef.current = true;
      setIsSending(true);
      const requestMode = activeTab;

      try {
        if (!conversationId) {
          createdConversationRef.current = true;
          console.log("CREATE_CONVERSATION", { mode: "create" });
          const conversation = await createConversationRequest();
          conversationId = conversation.id;
          handledChatRef.current = conversation.id;
          setConversations((prev) => mergeConversationSummary(prev, conversation));
          setCurrentConversation((prev) => ({
            ...(prev && prev.id === localConversationId ? prev : { ...conversation, messages: [] }),
            ...conversation,
            messages: prev?.id === localConversationId ? prev.messages : nextMessages,
          }));
          setActiveConversationId(conversation.id);
          setIsDraftChat(false);
        } else {
          console.log("CREATE_CONVERSATION", { mode: "reuse", conversationId });
        }

        console.log("SAVE_USER_MESSAGE", { conversationId });
        console.log("CALL_BACKEND", { conversationId, question, mode: requestMode });
        const result = await sendChatRequest({ question, conversationId, mode: requestMode });
        handledChatRef.current = result.conversation.id;
        setIsDraftChat(false);
        console.log("SAVE_ASSISTANT_MESSAGE", {
          conversationId: result.conversation.id,
          assistantMessageId: result.assistantMessage.id,
        });
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
        setActiveConversationId(result.conversation.id);
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
        createdConversationRef.current = false;
        submittingRef.current = false;
        setIsSending(false);
      }
    },
    [activeConversationId, activeTab, currentConversation, router]
  );

  useEffect(() => {
    const chatId = searchParams.get("chat") || "";
    const hasPendingDraft =
      typeof window !== "undefined" &&
      Boolean(sessionStorage.getItem(PENDING_CHAT_TOKEN_KEY));

    if (chatId && chatId !== handledChatRef.current) {
      handledChatRef.current = chatId;
      setIsDraftChat(false);
      setComposerInitialValue("");
      void loadConversationDetail(chatId);
      return;
    }

    if (!chatId && !hasPendingDraft && conversations.length > 0 && !activeConversationId && !conversationLoading && !isDraftChat) {
      void loadConversationDetail(conversations[0].id);
    }
  }, [
    activeConversationId,
    conversationLoading,
    conversations,
    isDraftChat,
    loadConversationDetail,
    searchParams,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const pendingToken = sessionStorage.getItem(PENDING_CHAT_TOKEN_KEY) || "";
    if (!pendingToken || pendingToken === processedQuestionRef.current) return;

    const pendingMessage = (sessionStorage.getItem(PENDING_CHAT_MESSAGE_KEY) || "").trim();
    processedQuestionRef.current = pendingToken;
    sessionStorage.removeItem(PENDING_CHAT_TOKEN_KEY);
    sessionStorage.removeItem(PENDING_CHAT_MESSAGE_KEY);

    if (!pendingMessage) return;

    handledChatRef.current = "";
    setCurrentConversation(null);
    setActiveConversationId("");
    setConversationError("");
    setIsDraftChat(true);
    setComposerInitialValue(pendingMessage);
    setPendingAutoSubmitText(pendingMessage);
  }, []);

  useEffect(() => {
    if (!pendingAutoSubmitText) return;
    if (submittingRef.current || isSending) return;
    if (activeConversationId || messages.length > 0) return;

    const nextText = pendingAutoSubmitText;
    setPendingAutoSubmitText("");
    setComposerInitialValue("");
    void handleSendMessage(nextText);
  }, [activeConversationId, handleSendMessage, isSending, messages.length, pendingAutoSubmitText]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    function handleOpenSidebar() {
      setMobileSidebarOpen(true);
    }

    window.addEventListener("chat:openSidebar", handleOpenSidebar);
    return () => {
      window.removeEventListener("chat:openSidebar", handleOpenSidebar);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!mobileSidebarOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileSidebarOpen]);

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

  const copyMessage = useCallback(async (messageId: string, content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;

    try {
      await navigator.clipboard.writeText(trimmed);
      setCopiedMessageId(messageId);
      window.setTimeout(() => {
        setCopiedMessageId((current) => (current === messageId ? "" : current));
      }, 1800);
    } catch {
      setConversationError("Copy failed. Please try again.");
    }
  }, []);

  return (
    <main className="chat-page">
      <div className="chat-layout">
        <section className="chat-window">
          <div className="chat-window-header">
            <div className="chat-window-top">
              <div className="chat-window-title-wrap">
                <h1 className="chat-page-title">Learn Orthodoxy</h1>
                <p className="chat-page-subtitle">
                  Ask questions about Orthodox saints and Coptic Orthodox catechism.
                </p>
              </div>
              <div className="chat-header-actions">
                <button type="button" className="chat-header-btn chat-close-page-btn" onClick={() => router.push("/")}>
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
            <div className="chat-messages">
              {conversationError ? <div className="chat-empty-state">{conversationError}</div> : null}
              {conversationLoading ? <div className="chat-empty-state">Loading chat...</div> : null}
              {!conversationLoading && messages.length ? (
                messages.map((message) => (
                  <div
                    key={message.id}
                    data-message-role={message.role}
                    className={`message-row ${message.role === "user" ? "user-row" : "assistant-row"}`}
                  >
                    <div className="message-stack">
                      <div
                        ref={
                          message.role === "user" && message.id === latestUserMessageId
                            ? latestUserMessageRef
                            : null
                        }
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
                            </>
                          )
                        ) : (
                          message.content
                        )}
                      </div>
                      {!message.isTyping ? (
                        <div className={`message-actions ${message.role === "user" ? "user-actions" : "assistant-actions"}`}>
                          <button
                            type="button"
                            className="message-action-btn"
                            onClick={() => void copyMessage(message.id, message.content)}
                            aria-label={copiedMessageId === message.id ? "Copied" : "Copy message"}
                            title={copiedMessageId === message.id ? "Copied" : "Copy"}
                          >
                            <Image
                              src={copiedMessageId === message.id ? "/icons/checkmark.svg" : "/icons/copy.svg"}
                              alt=""
                              aria-hidden="true"
                              width={24}
                              height={24}
                              className={`message-copy-icon ${copiedMessageId === message.id ? "message-copy-icon-copied" : ""}`}
                            />
                          </button>
                        </div>
                      ) : null}
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
                {!saintsError && hasMoreSaints ? (
                  <button
                    type="button"
                    className="saints-load-more"
                    onClick={() => void loadSaintsPage({ query: saintSearch, offset: saints.length })}
                    disabled={saintsLoading}
                  >
                    {saintsLoading ? "Loading..." : `Load more saints (${saints.length}/${saintsTotal})`}
                  </button>
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
              <div className="catechism-more-topics">
                <div className="catechism-more-topics-label">More topics for catechism</div>
                <div className="catechism-topic-list">
                  {CATECHISM_TOPICS.map((topic) => (
                    <details key={topic.title} className="catechism-topic-group">
                      <summary className="catechism-topic-summary">
                        <span className="catechism-topic-summary-copy">
                          <span className="catechism-topic-title">{topic.title}</span>
                          <span className="catechism-topic-description">{topic.description}</span>
                        </span>
                        <span className="catechism-topic-chevron" aria-hidden="true" />
                      </summary>
                      <div className="catechism-prompt-grid">
                        {topic.prompts.map((item) => (
                          <button
                            key={`${topic.title}-${item.label}`}
                            type="button"
                            className="catechism-prompt-card"
                            onClick={() => submitCatechismPrompt(item.prompt, setActiveTab)}
                          >
                            <span className="catechism-prompt-label">{item.label}</span>
                            <span className="catechism-prompt-text">{item.prompt}</span>
                          </button>
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="chat-bottom-bar">
            <ChatShell initialValue={composerInitialValue} onSubmit={handleSendMessage} isSubmitting={isSending} />
          </div>
        </section>

        <button
          type="button"
          className={`chat-sidebar-overlay ${mobileSidebarOpen ? "chat-sidebar-overlay-visible" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
          aria-label="Close chats panel"
        />
        <ChatSidebar
          sessions={conversations}
          activeSessionId={activeConversationId}
          onSelectSession={selectSession}
          onNewChat={() => void startNewChat()}
          onDeleteSession={(conversationId) => void deleteSession(conversationId)}
          loading={conversationsLoading}
          error={conversationsError}
          isMobileOpen={mobileSidebarOpen}
          onClose={() => setMobileSidebarOpen(false)}
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
