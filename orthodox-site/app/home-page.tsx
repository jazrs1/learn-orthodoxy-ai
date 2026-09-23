"use client";

import Image from "next/image";
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatShell from "../components/ChatShell";
import ChatSidebar from "../components/ChatSidebar";
import ExampleQuestions from "../components/ExampleQuestions";
import { IconArrowForward } from "../components/Icons";
import { useLanguage } from "../components/LanguageProvider";
import Ornament from "../components/Ornament";
import SiteFooter from "../components/SiteFooter";
import { useChatSidebar } from "../components/useChatSidebar";
import { BRAND } from "../lib/brand";
import { fetchConversationList, deleteConversationRequest } from "../lib/chat-client";
import { ConversationSummary } from "../lib/chat-types";
import { HOME_CONTENT } from "../lib/home-content";

const PENDING_CHAT_MESSAGE_KEY = "orthodox:pending-chat-message";
const PENDING_CHAT_TOKEN_KEY = "orthodox:pending-chat-token";
const ROMAN = ["I", "II", "III", "IV", "V"];

/**
 * `banner` is the server-rendered Today banner (CAL-005): a full-width band right under the header
 * (UI-024). Then hero (wordmark, description, question box, AI note) → example questions → Explore
 * (UI-017).
 */
export default function HomePage({ banner }: { banner?: ReactNode }) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const router = useRouter();
  const { language, t } = useLanguage();
  const content = HOME_CONTENT[language];
  // The past-chats sidebar, shared with the chat page (UI-025): shown once there are chats, open
  // by default on desktop and hidden from the header's toggle; a drawer on phones.
  const hasHistory = !loading && conversations.length > 0;
  const sidebar = useChatSidebar(hasHistory);
  const setMobileSidebarOpen = sidebar.setMobileOpen;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const nextConversations = await fetchConversationList();
        if (!cancelled) {
          setConversations(nextConversations);
        }
      } catch {
        if (!cancelled) {
          setError(t("unableToLoadChats"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [t]);

  function openSession(sessionId: string) {
    setMobileSidebarOpen(false);
    router.push(`/chat?chat=${encodeURIComponent(sessionId)}`);
  }

  function startNewChat() {
    setMobileSidebarOpen(false);
    router.push("/chat");
  }

  function startChatFromHome(message: string) {
    sessionStorage.setItem(PENDING_CHAT_MESSAGE_KEY, message);
    sessionStorage.setItem(PENDING_CHAT_TOKEN_KEY, `${Date.now()}`);
    router.push("/chat");
  }

  async function deleteSession(sessionId: string) {
    try {
      await deleteConversationRequest(sessionId);
      setConversations((prev) => prev.filter((conversation) => conversation.id !== sessionId));
    } catch {
      setError(t("unableToDeleteChat"));
    }
  }

  return (
    <>
      <main className="home-page">
        {banner}
        <div className={`home-layout ${sidebar.visible ? "home-layout-with-sidebar" : ""}`}>
          <ChatSidebar
            sessions={conversations}
            onSelectSession={openSession}
            onNewChat={startNewChat}
            onDeleteSession={deleteSession}
            showAppNav
            loading={loading}
            error={error}
            isMobileOpen={sidebar.mobileOpen}
            onClose={() => setMobileSidebarOpen(false)}
            desktopHidden={!sidebar.visible}
            inflow
          />
          <div className="home-content">
            <section className="hero" aria-labelledby="home-title">
              {/* The wordmark is the page title. Arabic pages add the Arabic name as text; the
                  English wordmark is then decorative. */}
              <h1 className="hero-title" id="home-title">
                <Image
                  src={BRAND.wordmarkShort.src}
                  alt={language === "ar" ? "" : t("appName")}
                  width={BRAND.wordmarkShort.width}
                  height={BRAND.wordmarkShort.height}
                  className="hero-wordmark"
                  loading="eager"
                  fetchPriority="high"
                />
                {language === "ar" ? <span className="hero-title-text">{t("appName")}</span> : null}
              </h1>
              <p className="hero-tagline">{content.tagline}</p>
              <p className="hero-subtitle">{content.lead}</p>

              <div className="hero-chat-wrap">
                <ChatShell onSubmit={startChatFromHome} />
                <p className="hero-note">{content.aiNote}</p>
              </div>
            </section>

            <ExampleQuestions onPick={startChatFromHome} limit={4} />

            <Ornament />

            <section className="home-section" aria-labelledby="home-explore">
              <h2 className="section-title" id="home-explore">
                {content.exploreTitle}
              </h2>
              <div className="explore-columns">
                {[
                  { href: "/chat#catechism", card: content.catechismCard },
                  { href: "/chat#saints", card: content.saintsCard },
                ].map(({ href, card }) => (
                  <div key={href} className="explore-column">
                    <h3 className="explore-heading">{card.title}</h3>
                    <p className="explore-text">{card.text}</p>
                    <Link href={href} className="text-link">
                      {card.cta}
                      <IconArrowForward size={15} />
                    </Link>
                  </div>
                ))}
              </div>
            </section>

            <Ornament />

            <section className="home-section" aria-labelledby="home-how">
              <h2 className="section-title" id="home-how">
                {content.howTitle}
              </h2>
              <ol className="how-steps">
                {content.howSteps.map((step, index) => (
                  <li key={step.title} className="how-step">
                    <span className="how-step-number" aria-hidden="true">
                      {language === "ar" ? (index + 1).toLocaleString("ar-EG") : ROMAN[index]}
                    </span>
                    <span className="how-step-body">
                      <span className="how-step-title">{step.title}</span>
                      <span className="how-step-text">{step.text}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </section>

            <section className="home-section home-note" aria-labelledby="home-note">
              <h2 className="section-title" id="home-note">
                {content.noteTitle}
              </h2>
              <ul className="home-note-list">
                {content.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
              <Link href="/credits" className="text-link">
                {content.noteLink}
                <IconArrowForward size={15} />
              </Link>
            </section>
          </div>
        </div>

        <button
          type="button"
          className={`chat-sidebar-overlay ${sidebar.mobileOpen ? "chat-sidebar-overlay-visible" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
          tabIndex={-1}
        />
      </main>
      <SiteFooter />
    </>
  );
}
