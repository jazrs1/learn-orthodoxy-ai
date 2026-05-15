"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import ChatShell from "../../components/ChatShell";
import ChatSidebar from "../../components/ChatSidebar";
import InteractiveAnswer from "../../components/InteractiveAnswer";
import { useLanguage } from "../../components/LanguageProvider";
import { buildSaintLookup, isValidSaintName } from "../../components/saintNameUtils";
import {
  createConversationRequest,
  deleteConversationRequest,
  fetchConversation,
  fetchConversationList,
  sendChatRequest,
} from "../../lib/chat-client";
import { ChatMessage, ConversationDetail, ConversationSummary, SourceRef } from "../../lib/chat-types";
import { displaySaintName } from "../../lib/saint-display";

type SaintsListResponse = {
  saints?: string[];
  total?: number;
};

type SaintDetailResponse = {
  answer?: string;
  entities?: string[];
  options?: string[];
  sources?: SourceRef[];
  error?: string;
};

type ChatMode = "chat" | "saints" | "catechism";

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

const CATECHISM_TOPICS_AR: CatechismTopic[] = [
  {
    title: "الصلاة",
    description: "الصلاة اليومية والعبادة والحياة الداخلية مع الله.",
    prompts: [
      { label: "الصلاة", prompt: "لماذا الصلاة مهمة في الحياة القبطية الأرثوذكسية؟" },
      { label: "الصلاة الربانية", prompt: "كيف تشرح الكنيسة القبطية الأرثوذكسية الصلاة الربانية؟" },
      { label: "قانون الصلاة", prompt: "ما إرشاد الكنيسة القبطية الأرثوذكسية لقانون صلاة يومي؟" },
    ],
  },
  {
    title: "الخلاص",
    description: "النعمة والتوبة والإيمان والحياة في المسيح.",
    prompts: [
      { label: "الخلاص", prompt: "ماذا تعلّم الكنيسة القبطية الأرثوذكسية عن الخلاص؟" },
      { label: "الإيمان", prompt: "كيف تشرح الكنيسة القبطية الأرثوذكسية الإيمان والأعمال في الخلاص؟" },
      { label: "الصليب", prompt: "لماذا الصليب أساسي في التعليم القبطي الأرثوذكسي عن الخلاص؟" },
    ],
  },
  {
    title: "الأسرار",
    description: "أسرار الكنيسة وكيف ننال النعمة.",
    prompts: [
      { label: "الأسرار", prompt: "ما هي الأسرار السبعة في الكنيسة القبطية الأرثوذكسية؟" },
      { label: "الإفخارستيا", prompt: "ماذا تعلّم الكنيسة القبطية الأرثوذكسية عن الإفخارستيا؟" },
      { label: "المعمودية", prompt: "لماذا المعمودية ضرورية بحسب الكنيسة القبطية الأرثوذكسية؟" },
    ],
  },
  {
    title: "التوبة",
    description: "الاعتراف والجهاد الروحي والرجوع إلى الله.",
    prompts: [
      { label: "الاعتراف", prompt: "ماذا تعلّم الكنيسة القبطية الأرثوذكسية عن الاعتراف والتوبة؟" },
      { label: "التوبة", prompt: "ما علامات التوبة الحقيقية في التعليم القبطي الأرثوذكسي؟" },
      { label: "التجربة", prompt: "كيف يتعامل الإنسان مع السقوط المتكرر في نفس الخطية؟" },
    ],
  },
  {
    title: "الكنيسة",
    description: "طبيعة الكنيسة والتقليد والانتماء إلى جسد المسيح.",
    prompts: [
      { label: "الكنيسة", prompt: "ماذا تعلّم الكنيسة القبطية الأرثوذكسية عن الكنيسة نفسها؟" },
      { label: "التقليد", prompt: "لماذا التقليد المقدس مهم في الكنيسة القبطية الأرثوذكسية؟" },
      { label: "القديسون", prompt: "كيف تشرح الكنيسة القبطية الأرثوذكسية الشركة مع القديسين؟" },
    ],
  },
  {
    title: "الصوم",
    description: "تدريب نسكي وضبط للنفس واستعداد للقداسة.",
    prompts: [
      { label: "الصوم", prompt: "لماذا تهتم الكنيسة القبطية الأرثوذكسية بالصوم بهذا الشكل؟" },
      { label: "الهدف", prompt: "ما الهدف الروحي من الصوم في الكنيسة القبطية الأرثوذكسية؟" },
      { label: "الصلاة", prompt: "كيف يرتبط الصوم بالصلاة والتوبة؟" },
    ],
  },
];

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

function normalizeOptionText(option: string) {
  return option
    .trim()
    .replace(/^You might also ask:\s*/i, "")
    .replace(/^يمكنك أيضًا أن تسأل[:：]\s*/i, "")
    .replace(/^[-–—•]\s*/, "")
    .trim();
}

function looksLikeQuestionOption(option: string) {
  return (
    option.includes("?") ||
    option.includes("؟") ||
    /^(هل|كيف|لماذا|ما|ماذا|متى|أين|من)\b/i.test(option) ||
    /^(i\s+(?:would\s+like|want)|would|how|why|what|when|where|who|which|can|should|do|does|is|are)\b/i.test(option)
  );
}

function followUpToUserMessage(option: string) {
  const cleaned = option.trim().replace(/[?？]\s*$/, "").trim();
  const replacements: Array<[RegExp, string]> = [
    [/^would\s+you\s+like\s+to\s+/i, "I would like to "],
    [/^would\s+you\s+like\s+/i, "I would like "],
    [/^do\s+you\s+want\s+to\s+/i, "I want to "],
    [/^do\s+you\s+want\s+/i, "I want "],
  ];

  for (const [pattern, replacement] of replacements) {
    if (pattern.test(cleaned)) {
      return cleaned.replace(pattern, replacement).trim();
    }
  }

  return cleaned;
}

function compactFollowUpContext(answer: string) {
  return answer
    .replace(/\s+/g, " ")
    .replace(/\b(?:Would you like to|I would like to|I would like|I want to)\b.*$/i, "")
    .trim()
    .slice(0, 1200);
}

function followUpBackendQuestion(displayQuestion: string, answerContext: string) {
  const context = compactFollowUpContext(answerContext);
  if (!context) return displayQuestion;

  return `${displayQuestion}\n\nPrevious answer context for resolving this follow-up:\n${context}`;
}

function visibleMessageOptions(options: string[] | undefined, saintLookup: Set<string>) {
  const saintOptions: string[] = [];
  const questionOptions: string[] = [];
  const seen = new Set<string>();

  for (const option of options || []) {
    const normalized = normalizeOptionText(option);
    if (!normalized) continue;

    if (isValidSaintName(normalized, saintLookup)) {
      if (seen.has(normalized.toLowerCase())) continue;
      seen.add(normalized.toLowerCase());
      saintOptions.push(normalized);
    } else if (looksLikeQuestionOption(normalized)) {
      const dedupeKey = followUpToUserMessage(normalized).toLowerCase();
      if (seen.has(dedupeKey)) continue;
      seen.add(dedupeKey);
      questionOptions.push(normalized);
    }
  }

  return questionOptions.length ? questionOptions.slice(0, 2) : saintOptions;
}

function hasSourceBackedSaintDetail(detail: SaintDetailResponse | null) {
  const answer = detail?.answer?.trim() || "";
  if (!answer) return false;
  if (!Array.isArray(detail?.sources) || detail.sources.length === 0) return false;

  const lowerAnswer = answer.toLowerCase();
  return !(
    lowerAnswer.includes("i don't have enough information") ||
    lowerAnswer.includes("i could not find enough information") ||
    lowerAnswer.includes("i found multiple saints") ||
    lowerAnswer.includes("choose one option") ||
    answer.includes("لم أجد معلومات كافية") ||
    answer.includes("اختر")
  );
}

function ChatPageContent() {
  const { language, t } = useLanguage();
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
  const [activeTab, setActiveTab] = useState<ChatMode>("chat");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [pendingAutoSubmitText, setPendingAutoSubmitText] = useState("");
  const [saints, setSaints] = useState<string[]>([]);
  const [saintsTotal, setSaintsTotal] = useState(0);
  const [saintsLoading, setSaintsLoading] = useState(false);
  const [saintsError, setSaintsError] = useState("");
  const [saintSearch, setSaintSearch] = useState("");
  const [selectedSaint, setSelectedSaint] = useState("");
  const [saintDetail, setSaintDetail] = useState<SaintDetailResponse | null>(null);
  const [saintDetailLoading, setSaintDetailLoading] = useState(false);
  const [saintDetailError, setSaintDetailError] = useState("");
  const searchParams = useSearchParams();
  const router = useRouter();
  const latestUserMessageRef = useRef<HTMLDivElement | null>(null);
  const chatMessagesRef = useRef<HTMLDivElement | null>(null);
  const saintsListRef = useRef<HTMLDivElement>(null);
  const saintsLoadingRef = useRef(false);
  const saintsRequestIdRef = useRef(0);
  const submittingRef = useRef(false);
  const pendingScrollToUserMessageRef = useRef(false);
  const pendingScrollToMessageIdRef = useRef("");
  const createdConversationRef = useRef(false);
  const processedQuestionRef = useRef("");
  const handledChatRef = useRef("");

  const saintLookup = useMemo(() => buildSaintLookup(saints), [saints]);
  const messages = useMemo(() => currentConversation?.messages || [], [currentConversation]);
  const catechismTopics = useMemo(
    () => (language === "ar" ? CATECHISM_TOPICS_AR : CATECHISM_TOPICS),
    [language]
  );
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
      setConversationsError(error instanceof Error ? error.message : t("unableToLoadChats"));
      return [];
    } finally {
      setConversationsLoading(false);
    }
  }, [t]);

  const loadConversationDetail = useCallback(async (conversationId: string) => {
    try {
      setConversationLoading(true);
      setConversationError("");
      const conversation = await fetchConversation(conversationId);
      setCurrentConversation(conversation);
      setActiveConversationId(conversation.id);
      return conversation;
    } catch (error) {
      setConversationError(error instanceof Error ? error.message : t("unableToLoadChat"));
      return null;
    } finally {
      setConversationLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadConversationList();
  }, [loadConversationList]);

  useEffect(() => {
    if (!pendingScrollToUserMessageRef.current || activeTab !== "chat") return;

    const scrollToPendingMessage = () => {
      const container = chatMessagesRef.current;
      const messageId = pendingScrollToMessageIdRef.current;
      const target =
        messageId && container
          ? container.querySelector<HTMLElement>(`[data-message-id="${CSS.escape(messageId)}"]`)
          : latestUserMessageRef.current;

      if (!container || !target) return false;

      const containerTop = container.getBoundingClientRect().top;
      const targetTop = target.getBoundingClientRect().top;
      const scrollMargin = window.matchMedia("(max-width: 720px)").matches ? 72 : 96;

      container.scrollTo({
        top: container.scrollTop + targetTop - containerTop - scrollMargin,
        behavior: "smooth",
      });
      return true;
    };

    requestAnimationFrame(() => {
      const didScroll = scrollToPendingMessage();
      pendingScrollToUserMessageRef.current = false;
      pendingScrollToMessageIdRef.current = "";

      if (didScroll) {
        window.setTimeout(scrollToPendingMessage, 120);
      }
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
      if (saintsLoadingRef.current && !reset) return;

      const normalizedQuery = (query ?? saintSearch).trim();
      const nextOffset = typeof offset === "number" ? offset : 0;
      const requestId = saintsRequestIdRef.current + 1;
      saintsRequestIdRef.current = requestId;

      saintsLoadingRef.current = true;
      setSaintsLoading(true);
      if (reset) {
        setSaintsError("");
      }

      try {
        const params = new URLSearchParams({
          limit: String(SAINTS_PAGE_SIZE),
          offset: String(nextOffset),
          language,
        });
        if (normalizedQuery) {
          params.set("q", normalizedQuery);
        }

        const response = await fetch(`/api/saints?${params.toString()}`, {
          signal: AbortSignal.timeout(15000),
        });
        if (!response.ok) throw new Error("Failed to load saints list");
        const data = (await response.json()) as SaintsListResponse;
        if (requestId !== saintsRequestIdRef.current) return;

        const nextNames = Array.isArray(data.saints)
          ? data.saints.filter((name) => typeof name === "string" && name.trim())
          : [];

        setSaints((prev) => (reset ? nextNames : mergeUniqueSaints(prev, nextNames)));
        setSaintsTotal(typeof data.total === "number" ? data.total : nextNames.length);
        setSaintsError("");
      } catch (error) {
        if (requestId !== saintsRequestIdRef.current) return;
        setSaintsError(error instanceof Error ? error.message : t("unableToLoadChats"));
      } finally {
        if (requestId === saintsRequestIdRef.current) {
          saintsLoadingRef.current = false;
          setSaintsLoading(false);
        }
      }
    },
    [language, saintSearch, t]
  );

  useEffect(() => {
    setSaints([]);
    setSaintsTotal(0);
    setSelectedSaint("");
    setSaintDetail(null);
    setSaintDetailError("");
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
    pendingScrollToMessageIdRef.current = "";
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
        setConversationsError(error instanceof Error ? error.message : t("unableToDeleteChat"));
      }
    },
    [activeConversationId, t]
  );

  const handleSendMessage = useCallback(
    async (rawQuestion: string, options?: { displayMessage?: string; mode?: ChatMode; hideUserMessage?: boolean }) => {
      const question = followUpToUserMessage(rawQuestion.trim());
      if (!question || submittingRef.current) return;
      const displayQuestion = options?.displayMessage?.trim() || question;
      const hideUserMessage = Boolean(options?.hideUserMessage);

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
        ...(hideUserMessage ? [] : [optimisticMessage(optimisticUserId, "user", displayQuestion)]),
        { ...optimisticMessage(optimisticAssistantId, "assistant", ""), isTyping: true },
      ];

      pendingScrollToUserMessageRef.current = !hideUserMessage;
      pendingScrollToMessageIdRef.current = hideUserMessage ? "" : optimisticUserId;

      setCurrentConversation((prev) =>
        prev && prev.id === localConversationId
          ? { ...prev, messages: nextMessages }
          : {
              id: localConversationId,
              title: prev?.title || t("newChat"),
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              messages: nextMessages,
            }
      );

      if (conversationId) {
        setActiveConversationId(conversationId);
      }
      setConversationError("");
      submittingRef.current = true;
      setIsSending(true);
      const requestMode = options?.mode || activeTab;
      if (activeTab !== "chat") {
        setActiveTab("chat");
      }

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

        console.log("SAVE_CHAT_TURN", { conversationId, hideUserMessage });
        console.log("CALL_BACKEND", { conversationId, question, displayQuestion, mode: requestMode, language });
        const result = await sendChatRequest({
          question,
          displayQuestion,
          conversationId,
          mode: requestMode,
          language,
          hideUserMessage,
        });
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
            messages: [
              ...baseMessages,
              ...(result.userMessage ? [result.userMessage] : []),
              result.assistantMessage,
            ],
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
    [activeConversationId, activeTab, currentConversation, language, router, t]
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

    function selectMode(mode: string) {
      if (mode === "chat" || mode === "catechism" || mode === "saints") {
        setActiveTab(mode);
      }
    }

    function syncModeFromHash() {
      selectMode(window.location.hash.replace("#", ""));
    }

    function handleSetMode(event: Event) {
      const mode = (event as CustomEvent<{ mode?: string }>).detail?.mode || "";
      selectMode(mode);
    }

    syncModeFromHash();
    window.addEventListener("hashchange", syncModeFromHash);
    window.addEventListener("chat:setMode", handleSetMode);
    return () => {
      window.removeEventListener("hashchange", syncModeFromHash);
      window.removeEventListener("chat:setMode", handleSetMode);
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

  const loadSaintDetail = useCallback(async (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;

    setSelectedSaint(trimmed);
    setSaintDetail(null);
    setSaintDetailError("");
    setSaintDetailLoading(true);

    try {
      const response = await fetch("/api/saint-detail", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, language }),
      });
      const data = (await response.json().catch(() => ({}))) as SaintDetailResponse;
      if (!response.ok) throw new Error(data.error || "Unable to load saint details right now.");
      setSaintDetail(data);
    } catch (error) {
      setSaintDetailError(error instanceof Error ? error.message : "Unable to load saint details right now.");
    } finally {
      setSaintDetailLoading(false);
    }
  }, [language]);

  const submitSaintLookup = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    void handleSendMessage(`search saint: ${trimmed}`, { displayMessage: displaySaintName(trimmed, language) });
  }, [handleSendMessage, language]);

  const submitMessageOption = useCallback(
    (option: string, answerContext = "") => {
      if (isValidSaintName(option, saintLookup)) {
        submitSaintLookup(option);
        return;
      }
      const displayQuestion = followUpToUserMessage(option);
      const backendQuestion = followUpBackendQuestion(displayQuestion, answerContext);
      void handleSendMessage(backendQuestion, { displayMessage: displayQuestion, hideUserMessage: true });
    },
    [handleSendMessage, saintLookup, submitSaintLookup]
  );

  const selectSaint = useCallback(
    (name: string) => {
      if (!isValidSaintName(name, saintLookup)) return;
      void loadSaintDetail(name);
    },
    [loadSaintDetail, saintLookup]
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
      setConversationError(t("copyFailed"));
    }
  }, [t]);

  return (
    <main className="chat-page">
      <div className="chat-layout">
        <section className="chat-window">
          {activeTab === "chat" ? (
            <div className="chat-messages" ref={chatMessagesRef}>
              {conversationError ? <div className="chat-empty-state">{conversationError}</div> : null}
              {conversationLoading ? <div className="chat-empty-state">{t("loadingChat")}</div> : null}
              {!conversationLoading && messages.length ? (
                messages.map((message) => (
                  <div
                    key={message.id}
                    data-message-id={message.id}
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
                        dir="auto"
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
                              {(() => {
                                const options = visibleMessageOptions(message.options, saintLookup);
                                return options.length > 0 ? (
                                  <div className="message-options">
                                    <div className="message-options-list">
                                      {options.map((option) => (
                                        <button
                                          key={option}
                                          type="button"
                                          className="message-option-chip"
                                          onClick={() => submitMessageOption(option, message.content)}
                                        >
                                          {isValidSaintName(option, saintLookup)
                                            ? displaySaintName(option, language)
                                            : option}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                ) : null;
                              })()}
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
                            aria-label={copiedMessageId === message.id ? t("copied") : t("copyMessage")}
                            title={copiedMessageId === message.id ? t("copied") : t("copy")}
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
                <div className="chat-empty-state">{t("startByAsking")}</div>
              ) : null}
            </div>
          ) : activeTab === "catechism" ? (
            <div className="catechism-page-panel">
              <div className="catechism-panel-copy">
                <h2 className="catechism-panel-title">{t("catechismTopics")}</h2>
                <p className="catechism-panel-text">{t("catechismIntro")}</p>
              </div>
              <div className="catechism-topic-list">
                {catechismTopics.map((topic) => (
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
                          onClick={() => {
                            setActiveTab("chat");
                            void handleSendMessage(item.prompt, { mode: "catechism" });
                          }}
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
          ) : (
            <div className="saints-tab-panel">
              {selectedSaint ? (
                <div className="saint-detail-panel">
                  <div className="saint-detail-header">
                    <h2 className="saint-detail-title">{displaySaintName(selectedSaint, language)}</h2>
                    <button
                      type="button"
                      className="saint-detail-close"
                      onClick={() => {
                        setSelectedSaint("");
                        setSaintDetail(null);
                        setSaintDetailError("");
                      }}
                    >
                      {t("close")}
                    </button>
                  </div>
                  {saintDetailLoading ? <div className="chat-empty-state">{t("loading")}...</div> : null}
                  {saintDetailError ? <div className="chat-empty-state">{saintDetailError}</div> : null}
                  {!saintDetailLoading && !saintDetailError && saintDetail?.answer ? (
                    <>
                      <div className="saint-detail-answer" dir="auto">
                        <InteractiveAnswer
                          answer={saintDetail.answer}
                          entities={saintDetail.entities}
                          saintLookup={saintLookup}
                        />
                      </div>
                      {hasSourceBackedSaintDetail(saintDetail) ? (
                        <div className="saint-detail-actions">
                          <button
                            type="button"
                            className="saint-learn-more"
                            onClick={() => {
                              const saintName = selectedSaint.trim();
                              if (!saintName) return;
                              setActiveTab("chat");
                              if (typeof window !== "undefined") {
                                window.history.pushState(null, "", "/chat#chat");
                                window.dispatchEvent(new HashChangeEvent("hashchange"));
                                window.dispatchEvent(new CustomEvent("chat:setMode", { detail: { mode: "chat" } }));
                              }
                              void handleSendMessage(`I want to learn more about ${saintName}`, { mode: "saints" });
                            }}
                          >
                            Learn more
                          </button>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </div>
              ) : null}

              <div className="saints-tab-search">
                <input
                  type="text"
                  className="saints-search-input"
                  value={saintSearch}
                  onChange={(event) => setSaintSearch(event.target.value)}
                  placeholder={t("searchSaints")}
                  dir={language === "ar" ? "rtl" : "ltr"}
                />
              </div>

              <div className="saints-list-shell" ref={saintsListRef}>
                {saintsLoading ? <div className="chat-empty-state">{t("loadingSaints")}</div> : null}
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
                        {displaySaintName(name, language)}
                      </button>
                    ))
                  ) : (
                    <div className="chat-empty-state">{t("noResultsFound")}</div>
                  )
                ) : null}
                {!saintsError && hasMoreSaints ? (
                  <button
                    type="button"
                    className="saints-load-more"
                    onClick={() => void loadSaintsPage({ query: saintSearch, offset: saints.length })}
                    disabled={saintsLoading}
                  >
                    {saintsLoading ? `${t("loading")}...` : `${t("loadMoreSaints")} (${saints.length}/${saintsTotal})`}
                  </button>
                ) : null}
              </div>
            </div>
          )}

          {activeTab === "chat" ? (
            <div className="chat-bottom-bar">
              <ChatShell initialValue={composerInitialValue} onSubmit={handleSendMessage} isSubmitting={isSending} />
            </div>
          ) : null}
        </section>

        <button
          type="button"
          className={`chat-sidebar-overlay ${mobileSidebarOpen ? "chat-sidebar-overlay-visible" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
          aria-label={t("closeChatsPanel")}
        />
        <ChatSidebar
          sessions={conversations}
          activeSessionId={activeConversationId}
          onSelectSession={selectSession}
          onNewChat={() => void startNewChat()}
          onDeleteSession={(conversationId) => void deleteSession(conversationId)}
          activeMode={activeTab}
          onSelectMode={setActiveTab}
          showAppNav
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
