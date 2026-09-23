"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatSidebar from "./ChatSidebar";
import { useLanguage } from "./LanguageProvider";
import { deleteConversationRequest, fetchConversationList } from "../lib/chat-client";
import type { ConversationSummary } from "../lib/chat-types";

/**
 * The phone navigation drawer (sections, past chats) for content pages. Same behaviour as the one
 * built into the credits page; opened by the header's menu button through "chat:openSidebar".
 */
export default function PageDrawer() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { t } = useLanguage();

  useEffect(() => {
    const openDrawer = () => setOpen(true);
    window.addEventListener("chat:openSidebar", openDrawer);
    return () => window.removeEventListener("chat:openSidebar", openDrawer);
  }, []);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    let cancelled = false;
    fetchConversationList()
      .then((list) => {
        if (!cancelled) setConversations(list);
      })
      .catch(() => {
        if (!cancelled) setError(t("unableToLoadChats"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  async function deleteSession(sessionId: string) {
    try {
      await deleteConversationRequest(sessionId);
      setConversations((previous) => previous.filter((conversation) => conversation.id !== sessionId));
    } catch {
      setError(t("unableToDeleteChat"));
    }
  }

  return (
    <div className="credits-mobile-sidebar">
      <button
        type="button"
        className={`chat-sidebar-overlay ${open ? "chat-sidebar-overlay-visible" : ""}`}
        onClick={() => setOpen(false)}
        aria-hidden="true"
        tabIndex={-1}
      />
      <ChatSidebar
        sessions={conversations}
        onSelectSession={(id) => {
          setOpen(false);
          router.push(`/chat?chat=${encodeURIComponent(id)}`);
        }}
        onNewChat={() => {
          setOpen(false);
          router.push("/chat");
        }}
        onDeleteSession={deleteSession}
        showAppNav
        loading={loading}
        error={error}
        isMobileOpen={open}
        onClose={() => setOpen(false)}
      />
    </div>
  );
}
