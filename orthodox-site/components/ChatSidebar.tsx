"use client";

import { ConversationSummary } from "../lib/chat-types";
import { useLanguage } from "./LanguageProvider";

type ChatSidebarProps = {
  sessions: ConversationSummary[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession?: (sessionId: string) => void;
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
  loading = false,
  error = "",
  isMobileOpen = false,
  onClose,
}: ChatSidebarProps) {
  const { t } = useLanguage();

  return (
    <aside className={`chat-sidebar ${isMobileOpen ? "chat-sidebar-mobile-open" : ""}`}>
      <div className="chat-sidebar-details">
        <div className="chat-sidebar-header">
          <div className="chat-sidebar-title">{t("chats")}</div>
          {onClose ? (
            <button type="button" className="chat-sidebar-close-btn" onClick={onClose} aria-label={t("closeChatsPanel")}>
              ×
            </button>
          ) : null}
        </div>

        <div className="chat-sidebar-panel">
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
                      ×
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
