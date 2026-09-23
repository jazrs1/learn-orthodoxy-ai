"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ChatShell from "../../components/ChatShell";
import ExampleQuestions from "../../components/ExampleQuestions";
import { IconAlert, IconChevronDown, IconCopy, IconCheck, IconRetry, IconSearch } from "../../components/Icons";
import ChatSidebar from "../../components/ChatSidebar";
import AnswerWithSources from "../../components/AnswerWithSources";
import { useLanguage } from "../../components/LanguageProvider";
import { buildSaintLookup, isValidSaintName } from "../../components/saintNameUtils";
import {
  createConversationRequest,
  deleteConversationRequest,
  fetchConversation,
  fetchConversationList,
  sendChatRequest,
} from "../../lib/chat-client";
import { ChatMessage, ConversationDetail, ConversationSummary, NamesakeLink, SourceRef } from "../../lib/chat-types";
import { chatErrorKey } from "../../lib/errors";
import type { TranslationKey } from "../../lib/i18n";
import { displaySaintName } from "../../lib/saint-display";
import {
  type MessageOption,
  followUpToUserMessage,
  namesakesRequest,
  normalizeOptionText,
  saintSelectionRequest,
  visibleMessageOptions,
} from "../../lib/message-options";

type SaintsListResponse = {
  saints?: string[];
  total?: number;
};

type SaintDetailResponse = {
  answer?: string;
  entities?: string[];
  options?: string[];
  optionIds?: string[];
  namesakes?: NamesakeLink | null;
  sources?: SourceRef[];
  canLearnMore?: boolean;
  error?: string;
};

type ChatMode = "chat" | "saints" | "catechism";

type SendOptions = {
  displayMessage?: string;
  mode?: ChatMode;
  hideUserMessage?: boolean;
  /** Id of a failed user message this send replaces (Retry). */
  retryOf?: string;
  /** A namesake-menu choice: the backend selects this entry by ID (RET-010). */
  saintId?: string;
  /** A saint named exactly (saints pane, or a menu saved before RET-010). */
  saintName?: string;
  /** "Looking for a different St. X?": the menu of that name's other saints (RET-011). */
  namesakesOf?: string;
};

// A failed send: shown once as an alert under the thread with a Retry button (UI-008).
type SendFailure = {
  messageKey: TranslationKey;
  question: string;
  options?: SendOptions;
  failedUserMessageId: string;
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

function hasSourceBackedSaintDetail(detail: SaintDetailResponse | null) {
  const answer = detail?.answer?.trim() || "";
  if (!answer) return false;
  if (detail?.canLearnMore !== true) return false;
  if (!Array.isArray(detail?.sources) || detail.sources.length === 0) return false;

  const lowerAnswer = answer.toLowerCase();
  return !(
    lowerAnswer.includes("i don't have enough information") ||
    lowerAnswer.includes("i could not find enough information") ||
    lowerAnswer.includes("i could not find enough about") ||
    lowerAnswer.includes("could not find a dedicated saint entry") ||
    lowerAnswer.includes("i found multiple saints") ||
    lowerAnswer.includes("choose one option") ||
    answer.includes("لم أجد معلومات كافية") ||
    answer.includes("اختر")
  );
}

function saintDetailOptions(detail: SaintDetailResponse | null): MessageOption[] {
  const seen = new Set<string>();
  const options: MessageOption[] = [];

  (detail?.options || []).forEach((option, index) => {
    const label = normalizeOptionText(option);
    if (!label) return;
    const saintId = detail?.optionIds?.[index] || "";
    const key = saintId ? `id:${saintId}` : label.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    options.push(saintId ? { label, saintId } : { label });
  });

  return options;
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
  const [sendFailure, setSendFailure] = useState<SendFailure | null>(null);
  // Polite screen-reader announcement for the chat ("Searching…", "Answer ready.").
  const [liveMessage, setLiveMessage] = useState("");
  const [isDraftChat, setIsDraftChat] = useState(false);
  const [composerInitialValue, setComposerInitialValue] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState("");
  const [activeTab, setActiveTab] = useState<ChatMode>("chat");
  // Mode of the most recent request in this conversation. Follow-up chips reuse it so a
  // catechism thread stays in catechism mode and a saints thread in saints mode.
  const [conversationMode, setConversationMode] = useState<ChatMode>("chat");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [pendingAutoSubmitText, setPendingAutoSubmitText] = useState("");
  const [saints, setSaints] = useState<string[]>([]);
  const [saintsTotal, setSaintsTotal] = useState(0);
  const [saintsLoading, setSaintsLoading] = useState(false);
  const [saintsError, setSaintsError] = useState("");
  const [saintSearch, setSaintSearch] = useState("");
  const [selectedSaint, setSelectedSaint] = useState("");
  // The entry behind the saints pane when it was opened from a menu choice (RET-010).
  const [selectedSaintId, setSelectedSaintId] = useState("");
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
  // Opening the most recent chat is attempted once; a failed load must not retry in a loop.
  const autoOpenAttemptedRef = useRef(false);

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

  useEffect(() => {
  }, [language]);

  useEffect(() => {
  }, [activeTab]);

  const loadConversationList = useCallback(async () => {
    try {
      setConversationsLoading(true);
      setConversationsError("");
      const nextConversations = await fetchConversationList();
      setConversations(nextConversations);
      return nextConversations;
    } catch {
      setConversationsError(t("unableToLoadChats"));
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
    } catch {
      setConversationError(t("unableToLoadChat"));
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
        const saintsEndpoint = `/api/saints?${params.toString()}`;

        const response = await fetch(saintsEndpoint, {
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
      } catch {
        if (requestId !== saintsRequestIdRef.current) return;
        setSaintsError(t("unableToLoadSaints"));
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
      } catch {
        setConversationsError(t("unableToDeleteChat"));
      }
    },
    [activeConversationId, t]
  );

  const handleSendMessage = useCallback(
    async (rawQuestion: string, options?: SendOptions) => {
      // The user's own wording is kept as typed, question mark included (UI-008).
      const question = rawQuestion.trim();
      if (!question || submittingRef.current) return;
      const displayQuestion = options?.displayMessage?.trim() || question;
      const hideUserMessage = Boolean(options?.hideUserMessage);

      let conversationId = activeConversationId;
      if (!conversationId && createdConversationRef.current) {
        return;
      }

      const localConversationId = conversationId || `draft-${crypto.randomUUID()}`;

      const optimisticUserId = crypto.randomUUID();
      const optimisticAssistantId = crypto.randomUUID();
      const nextMessages = [
        ...((currentConversation?.id === localConversationId ? currentConversation.messages : []) || []).filter(
          (message) => message.id !== options?.retryOf
        ),
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
      setSendFailure(null);
      setLiveMessage(t("searchingSources"));
      submittingRef.current = true;
      setIsSending(true);
      const requestMode = options?.mode || activeTab;
      setConversationMode(requestMode);
      if (activeTab !== "chat") {
        setActiveTab("chat");
      }

      try {
        if (!conversationId) {
          createdConversationRef.current = true;
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
        }

        const result = await sendChatRequest({
          question,
          displayQuestion,
          conversationId,
          mode: requestMode,
          language,
          hideUserMessage,
          saintId: options?.saintId,
          saintName: options?.saintName,
          namesakesOf: options?.namesakesOf,
        });
        handledChatRef.current = result.conversation.id;
        setIsDraftChat(false);
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
        setLiveMessage(t("answerReady"));
        router.replace(`/chat?chat=${encodeURIComponent(result.conversation.id)}`, { scroll: false });
      } catch (error) {
        const messageKey = chatErrorKey(error);
        setSendFailure({
          messageKey,
          question,
          options,
          failedUserMessageId: hideUserMessage ? "" : optimisticUserId,
        });
        setLiveMessage("");
        // Drop the typing placeholder; the question stays visible above the alert.
        setCurrentConversation((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.filter((entry) => entry.id !== optimisticAssistantId),
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

    if (
      !chatId &&
      !hasPendingDraft &&
      conversations.length > 0 &&
      !activeConversationId &&
      !conversationLoading &&
      !isDraftChat &&
      !autoOpenAttemptedRef.current
    ) {
      autoOpenAttemptedRef.current = true;
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

  const loadSaintDetail = useCallback(async (name: string, saintId = "", namesakesOf = "") => {
    const trimmed = name.trim();
    if (!trimmed) return;

    setSelectedSaint(trimmed);
    setSelectedSaintId(saintId);
    setSaintDetail(null);
    setSaintDetailError("");
    setSaintDetailLoading(true);

    try {
      const response = await fetch("/api/saint-detail", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmed,
          language,
          ...(saintId ? { saintId } : {}),
          ...(namesakesOf ? { namesakesOf } : {}),
        }),
      });
      const data = (await response.json().catch(() => ({}))) as SaintDetailResponse;
      if (!response.ok) throw new Error("saint detail failed");
      setSaintDetail(data);
    } catch {
      setSaintDetailError(t("unableToLoadSaint"));
    } finally {
      setSaintDetailLoading(false);
    }
  }, [language, t]);

  // A saint choice is sent with its entry ID, so the backend selects exactly that entry and
  // never matches the chip text against the saints index again (RET-010).
  const submitSaintLookup = useCallback((option: MessageOption) => {
    if (!option.label.trim()) return;
    const { question, ...selection } = saintSelectionRequest(option, language);
    void handleSendMessage(question, {
      displayMessage: displaySaintName(option.label.trim(), language),
      ...selection,
    });
  }, [handleSendMessage, language]);

  // "Looking for a different St. X?" asks for the menu of that name's other saints (RET-011).
  const submitNamesakes = useCallback((link: NamesakeLink) => {
    const { question, ...selection } = namesakesRequest(link);
    void handleSendMessage(question, { displayMessage: link.label, ...selection });
  }, [handleSendMessage]);

  const submitMessageOption = useCallback(
    (option: MessageOption) => {
      if (option.saintId || isValidSaintName(option.label, saintLookup)) {
        submitSaintLookup(option);
        return;
      }
      // The chip text becomes an ordinary user turn: it is stored in the conversation and the
      // backend receives it with the server-side history, so "it"/"this" resolve from the
      // previous turns. No answer text is pasted into the question any more (AUDIT C14/C31),
      // and the request keeps the mode the conversation is already in.
      void handleSendMessage(followUpToUserMessage(option.label), { mode: conversationMode });
    },
    [conversationMode, handleSendMessage, saintLookup, submitSaintLookup]
  );

  const selectSaint = useCallback(
    (name: string) => {
      if (!isValidSaintName(name, saintLookup)) return;
      void loadSaintDetail(name);
    },
    [loadSaintDetail, saintLookup]
  );

  // /chat?saint=<index name>#saints opens that saint's entry; the calendar links here (CAL-005).
  // The name comes from the saints index snapshot, so it is not checked against the loaded list.
  const handledSaintParamRef = useRef("");
  useEffect(() => {
    const name = searchParams.get("saint")?.trim() || "";
    if (!name || name === handledSaintParamRef.current) return;
    handledSaintParamRef.current = name;
    void loadSaintDetail(name);
  }, [loadSaintDetail, searchParams]);

  const retryFailedSend = useCallback(() => {
    if (!sendFailure) return;
    void handleSendMessage(sendFailure.question, {
      ...sendFailure.options,
      retryOf: sendFailure.failedUserMessageId || undefined,
    });
  }, [handleSendMessage, sendFailure]);

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
      <h1 className="sr-only">{t(activeTab === "catechism" ? "catechism" : activeTab === "saints" ? "saintsSearch" : "chat")}</h1>
      <div className="sr-only" role="status" aria-live="polite">
        {liveMessage}
      </div>
      <div className="chat-layout">
        <section className="chat-window">
          {activeTab === "chat" ? (
            <div className="chat-messages" ref={chatMessagesRef}>
              {conversationError ? (
                <div className="chat-alert" role="alert">
                  <IconAlert className="chat-alert-icon" size={20} />
                  <div className="chat-alert-body">
                    <p className="chat-alert-text">{conversationError}</p>
                  </div>
                </div>
              ) : null}
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
                            <div className="typing-indicator">
                              <span className="typing-dots" aria-hidden="true">
                                <span />
                                <span />
                                <span />
                              </span>
                              <span>{t("searchingSources")}</span>
                            </div>
                          ) : (
                            <>
                              <AnswerWithSources
                                answerId={message.id}
                                answer={message.content}
                                sources={message.sources}
                                entities={message.entities}
                                saintLookup={saintLookup}
                                afterAnswer={
                                  message.namesakes ? (
                                    <button
                                      type="button"
                                      className="namesake-link"
                                      onClick={() => message.namesakes && submitNamesakes(message.namesakes)}
                                    >
                                      {message.namesakes.label}
                                    </button>
                                  ) : null
                                }
                              />
                              {(() => {
                                const options = visibleMessageOptions(message.options, message.optionIds, (label) =>
                                  isValidSaintName(label, saintLookup)
                                );
                                return options.length > 0 ? (
                                  <div className="message-options">
                                    <div className="message-options-list">
                                      {options.map((option) => (
                                        <button
                                          key={option.saintId || option.label}
                                          type="button"
                                          className="message-option-chip"
                                          onClick={() => submitMessageOption(option)}
                                        >
                                          {option.saintId || isValidSaintName(option.label, saintLookup)
                                            ? displaySaintName(option.label, language)
                                            : option.label}
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
                            className="icon-button message-action-btn"
                            onClick={() => void copyMessage(message.id, message.content)}
                            aria-label={copiedMessageId === message.id ? t("copied") : t("copyMessage")}
                            title={copiedMessageId === message.id ? t("copied") : t("copy")}
                          >
                            {copiedMessageId === message.id ? <IconCheck size={18} /> : <IconCopy size={18} />}
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))
              ) : !conversationLoading && !conversationError && !sendFailure ? (
                <div className="chat-welcome">
                  <h2 className="chat-welcome-title">{t("chatWelcomeTitle")}</h2>
                  <p className="chat-welcome-text">{t("chatWelcomeText")}</p>
                  <ExampleQuestions onPick={(question) => void handleSendMessage(question)} disabled={isSending} limit={4} />
                </div>
              ) : null}
              {sendFailure ? (
                <div className="chat-alert" role="alert">
                  <IconAlert className="chat-alert-icon" size={20} />
                  <div className="chat-alert-body">
                    <p className="chat-alert-text">{t(sendFailure.messageKey)}</p>
                    <div className="chat-alert-actions">
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={retryFailedSend}
                        disabled={isSending}
                      >
                        <IconRetry size={16} />
                        <span>{t("retry")}</span>
                      </button>
                    </div>
                  </div>
                </div>
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
                      <IconChevronDown className="catechism-topic-chevron" size={20} />
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
                      className="button button-secondary saint-detail-close"
                      onClick={() => {
                        setSelectedSaint("");
                        setSaintDetail(null);
                        setSaintDetailError("");
                      }}
                    >
                      {t("close")}
                    </button>
                  </div>
                  {saintDetailLoading ? (
                    <div className="chat-empty-state">
                      <div className="typing-indicator" role="status">
                        <span className="typing-dots" aria-hidden="true">
                          <span />
                          <span />
                          <span />
                        </span>
                        <span>{t("loading")}…</span>
                      </div>
                    </div>
                  ) : null}
                  {saintDetailError ? <div className="chat-empty-state">{saintDetailError}</div> : null}
                  {!saintDetailLoading && !saintDetailError && saintDetail?.answer ? (
                    <>
                      <div className="saint-detail-answer" dir="auto">
                        <AnswerWithSources
                          answerId="saint-detail"
                          headingLevel={3}
                          answer={saintDetail.answer}
                          sources={saintDetail.sources}
                          entities={saintDetail.entities}
                          saintLookup={saintLookup}
                          afterAnswer={
                            saintDetail.namesakes ? (
                              <button
                                type="button"
                                className="namesake-link"
                                onClick={() =>
                                  saintDetail.namesakes &&
                                  void loadSaintDetail(saintDetail.namesakes.name, "", saintDetail.namesakes.name)
                                }
                              >
                                {saintDetail.namesakes.label}
                              </button>
                            ) : null
                          }
                        />
                      </div>
                      {(() => {
                        const options = saintDetailOptions(saintDetail);
                        return options.length > 0 ? (
                          <div className="saint-detail-options">
                            <div className="message-options-list">
                              {options.map((option) => (
                                <button
                                  key={option.saintId || option.label}
                                  type="button"
                                  className="message-option-chip"
                                  onClick={() => void loadSaintDetail(option.label, option.saintId)}
                                >
                                  {displaySaintName(option.label, language)}
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : null;
                      })()}
                      {hasSourceBackedSaintDetail(saintDetail) ? (
                        <div className="saint-detail-actions">
                          <button
                            type="button"
                            className="button button-primary saint-learn-more"
                            onClick={() => {
                              const saintName = selectedSaint.trim();
                              if (!saintName) return;
                              setActiveTab("chat");
                              if (typeof window !== "undefined") {
                                window.history.pushState(null, "", "/chat#chat");
                                window.dispatchEvent(new HashChangeEvent("hashchange"));
                                window.dispatchEvent(new CustomEvent("chat:setMode", { detail: { mode: "chat" } }));
                              }
                              const question =
                                language === "ar"
                                  ? `أريد أن أعرف المزيد عن ${saintName}`
                                  : `Tell me more about ${saintName}`;
                              void handleSendMessage(question, {
                                mode: "saints",
                                ...(selectedSaintId ? { saintId: selectedSaintId } : { saintName }),
                              });
                            }}
                          >
                            {t("learnMore")}
                          </button>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </div>
              ) : null}

              <div className="saints-tab-search">
                <IconSearch className="saints-search-icon" size={18} />
                <input
                  type="search"
                  aria-label={t("searchSaints")}
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
                    className="button button-secondary saints-load-more"
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
          aria-hidden="true"
          tabIndex={-1}
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
