"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatShell from "../components/ChatShell";
import ChatSidebar from "../components/ChatSidebar";
import ExampleQuestions from "../components/ExampleQuestions";
import { IconArrowForward, IconBook, IconUsers } from "../components/Icons";
import { useLanguage } from "../components/LanguageProvider";
import { fetchConversationList, deleteConversationRequest } from "../lib/chat-client";
import { ConversationSummary } from "../lib/chat-types";
import { HOME_CONTENT } from "../lib/home-content";

const PENDING_CHAT_MESSAGE_KEY = "orthodox:pending-chat-message";
const PENDING_CHAT_TOKEN_KEY = "orthodox:pending-chat-token";

export default function HomePage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const router = useRouter();
  const { language, t } = useLanguage();
  const content = HOME_CONTENT[language];
  // First-time visitors get the full-width landing page; the chat history column only
  // appears on desktop once there is history to show (UI-009).
  const hasHistory = !loading && conversations.length > 0;

  useEffect(() => {
    function handleOpenSidebar() {
      setMobileSidebarOpen(true);
    }

    window.addEventListener("chat:openSidebar", handleOpenSidebar);
    return () => {
      window.removeEventListener("chat:openSidebar", handleOpenSidebar);
    };
  }, []);

  useEffect(() => {
    if (!mobileSidebarOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileSidebarOpen]);

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
    <main className="home-page">
      <div className={`home-layout ${hasHistory ? "home-layout-with-sidebar" : ""}`}>
        <div className="home-content">
          <section className="hero" aria-labelledby="home-title">
            <Image
              src="/cross-mark.png"
              alt=""
              width={96}
              height={96}
              className="hero-cross"
              loading="eager"
              fetchPriority="high"
            />
            <p className="hero-eyebrow">{content.eyebrow}</p>
            <h1 className="hero-title" id="home-title">
              {t("appName")}
            </h1>
            <p className="hero-subtitle">{content.lead}</p>

            <div className="hero-chat-wrap">
              <ChatShell onSubmit={startChatFromHome} />
            </div>

            <ExampleQuestions onPick={startChatFromHome} />
          </section>

          <section className="home-section" aria-labelledby="home-explore">
            <h2 className="section-title" id="home-explore">
              {content.exploreTitle}
            </h2>
            <div className="explore-grid">
              <Link href="/chat#catechism" className="explore-card">
                <span className="explore-card-icon">
                  <IconBook size={22} />
                </span>
                <span className="explore-card-title">{content.catechismCard.title}</span>
                <span className="explore-card-text">{content.catechismCard.text}</span>
                <span className="explore-card-cta">
                  {content.catechismCard.cta}
                  <IconArrowForward size={16} />
                </span>
              </Link>
              <Link href="/chat#saints" className="explore-card">
                <span className="explore-card-icon">
                  <IconUsers size={22} />
                </span>
                <span className="explore-card-title">{content.saintsCard.title}</span>
                <span className="explore-card-text">{content.saintsCard.text}</span>
                <span className="explore-card-cta">
                  {content.saintsCard.cta}
                  <IconArrowForward size={16} />
                </span>
              </Link>
            </div>
          </section>

          <section className="home-section" aria-labelledby="home-how">
            <h2 className="section-title" id="home-how">
              {content.howTitle}
            </h2>
            <ol className="how-steps">
              {content.howSteps.map((step, index) => (
                <li key={step.title} className="how-step">
                  <span className="how-step-number" aria-hidden="true">
                    {index + 1}
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
            <Link href="/credits" className="home-note-link">
              {content.noteLink}
              <IconArrowForward size={16} />
            </Link>
          </section>
        </div>
      </div>

      <button
        type="button"
        className={`chat-sidebar-overlay ${mobileSidebarOpen ? "chat-sidebar-overlay-visible" : ""}`}
        onClick={() => setMobileSidebarOpen(false)}
        aria-hidden="true"
        tabIndex={-1}
      />
      <ChatSidebar
        sessions={conversations}
        onSelectSession={openSession}
        onNewChat={startNewChat}
        onDeleteSession={deleteSession}
        showAppNav
        loading={loading}
        error={error}
        isMobileOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
        desktopHidden={!hasHistory}
      />
    </main>
  );
}
