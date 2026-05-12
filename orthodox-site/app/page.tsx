"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatShell from "../components/ChatShell";
import ChatSidebar from "../components/ChatSidebar";
import LogoWordmark from "../components/LogoWordmark";
import { fetchConversationList, deleteConversationRequest } from "../lib/chat-client";
import { ConversationSummary } from "../lib/chat-types";

const PENDING_CHAT_MESSAGE_KEY = "orthodox:pending-chat-message";
const PENDING_CHAT_TOKEN_KEY = "orthodox:pending-chat-token";

export default function HomePage() {
  const [mounted, setMounted] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
  }, []);

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
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load chats.");
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
  }, []);

  function openSession(sessionId: string) {
    setMobileSidebarOpen(false);
    router.push(`/chat?chat=${encodeURIComponent(sessionId)}`);
  }

  function startNewChat() {
    setMobileSidebarOpen(false);
    router.push("/chat");
  }

  function startChatFromHome(message: string) {
    if (typeof window !== "undefined") {
      sessionStorage.setItem(PENDING_CHAT_MESSAGE_KEY, message);
      sessionStorage.setItem(PENDING_CHAT_TOKEN_KEY, `${Date.now()}`);
    }
    router.push("/chat");
  }

  async function deleteSession(sessionId: string) {
    try {
      await deleteConversationRequest(sessionId);
      setConversations((prev) => prev.filter((conversation) => conversation.id !== sessionId));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete chat.");
    }
  }

  return (
    <main className="home-page">
      <div className="home-layout">
        <section className="hero">
          <h1 className="hero-title">
            <LogoWordmark variant="hero" />
          </h1>

          <p className="hero-subtitle">
            Ask questions about Orthodox saints and Coptic Orthodox catechism.
          </p>

          <div className="hero-chat-wrap">
            <ChatShell onSubmit={startChatFromHome} />
          </div>
        </section>

        <button
          type="button"
          className={`chat-sidebar-overlay ${mobileSidebarOpen ? "chat-sidebar-overlay-visible" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
          aria-label="Close chats panel"
        />

        {mounted ? (
          <ChatSidebar
            sessions={conversations}
            onSelectSession={openSession}
            onNewChat={startNewChat}
            onDeleteSession={deleteSession}
            loading={loading}
            error={error}
            isMobileOpen={mobileSidebarOpen}
            onClose={() => setMobileSidebarOpen(false)}
          />
        ) : null}
      </div>
    </main>
  );
}
