"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { MouseEvent } from "react";
import { ConversationSummary } from "../lib/chat-types";
import { useLanguage } from "./LanguageProvider";

type ChatMode = "chat" | "catechism" | "saints";

type ChatSidebarProps = {
  sessions: ConversationSummary[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession?: (sessionId: string) => void;
  activeMode?: ChatMode;
  onSelectMode?: (mode: ChatMode) => void;
  showAppNav?: boolean;
  loading?: boolean;
  error?: string;
  isMobileOpen?: boolean;
  onClose?: () => void;
};

export default function ChatSidebar({
  sessions,
  activeSessionId = "",
  onSelectSession,
  onNewChat,
  onDeleteSession,
  activeMode = "chat",
  onSelectMode,
  showAppNav = false,
  loading = false,
  error = "",
  isMobileOpen = false,
  onClose,
}: ChatSidebarProps) {
  const { t } = useLanguage();
  const pathname = usePathname();
  const modes: Array<{ id: ChatMode; label: string }> = [
    { id: "chat", label: t("chat") },
    { id: "catechism", label: t("catechism") },
    { id: "saints", label: t("saintsSearch") },
  ];

  function selectMode(mode: ChatMode, event: MouseEvent<HTMLAnchorElement>) {
    if (pathname !== "/chat" || typeof window === "undefined") return;

    event.preventDefault();
    window.history.replaceState(null, "", `/chat#${mode}`);
    window.dispatchEvent(new CustomEvent("chat:setMode", { detail: { mode } }));
    onSelectMode?.(mode);
    onClose?.();
  }

  return (
    <aside className={`chat-sidebar ${isMobileOpen ? "chat-sidebar-mobile-open" : ""}`}>
      <div className="chat-sidebar-details">
        <div className="chat-sidebar-header">
          <div className="chat-sidebar-title">{t("chats")}</div>
          {onClose ? (
            <button type="button" className="chat-sidebar-close-btn" onClick={onClose} aria-label={t("closeChatsPanel")}>
              x
            </button>
          ) : null}
        </div>

        <div className="chat-sidebar-panel">
          {showAppNav ? (
            <nav className="chat-sidebar-nav" aria-label="Learn Orthodoxy modes">
              {modes.map((mode) => (
                <Link
                  key={mode.id}
                  href={`/chat#${mode.id}`}
                  className={`chat-sidebar-nav-btn ${activeMode === mode.id ? "chat-sidebar-nav-btn-active" : ""}`}
                  onClick={(event) => {
                    selectMode(mode.id, event);
                    if (pathname !== "/chat") {
                      onClose?.();
                    }
                  }}
                  aria-current={activeMode === mode.id ? "page" : undefined}
                >
                  {mode.label}
                </Link>
              ))}
              <Link
                className="chat-sidebar-nav-btn"
                href="/contact"
                onClick={() => {
                  if (pathname === "/contact") {
                    onClose?.();
                  }
                }}
              >
                {t("contact")}
              </Link>
            </nav>
          ) : null}

          <button
            type="button"
            className="chat-sidebar-new-btn"
            onClick={() => {
              onNewChat();
              onClose?.();
            }}
          >
            {t("newChat")}
          </button>

          <div className="chat-sidebar-section-label">{t("pastChats")}</div>
          <div className="chat-sidebar-list">
            {loading ? (
              <div className="chat-sidebar-empty">{t("loadingChats")}</div>
            ) : error ? (
              <div className="chat-sidebar-empty">{error}</div>
            ) : sessions.length ? (
              sessions.map((session) => (
                <button
                  key={session.id}
                  type="button"
                  className={`chat-sidebar-item ${
                    session.id === activeSessionId ? "chat-sidebar-item-active" : ""
                  }`}
                  onClick={() => {
                    onSelectSession(session.id);
                    onClose?.();
                  }}
                >
                  <span className="chat-sidebar-item-title">{session.title || t("newChat")}</span>
                  {onDeleteSession ? (
                    <span
                      role="button"
                      tabIndex={0}
                      className="chat-sidebar-item-delete"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          onDeleteSession(session.id);
                        }
                      }}
                      aria-label={`${t("deleteChat")}: ${session.title || t("chat")}`}
                    >
                      x
                    </span>
                  ) : null}
                </button>
              ))
            ) : (
              <div className="chat-sidebar-empty">{t("noSavedChats")}</div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
