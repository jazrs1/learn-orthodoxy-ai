"use client";

import { ConversationSummary } from "../lib/chat-types";

type ChatSidebarProps = {
  sessions: ConversationSummary[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession?: (sessionId: string) => void;
  loading?: boolean;
  error?: string;
};

export default function ChatSidebar({
  sessions,
  activeSessionId = "",
  onSelectSession,
  onNewChat,
  onDeleteSession,
  loading = false,
  error = "",
}: ChatSidebarProps) {
  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar-details">
        <div className="chat-sidebar-header">
          <div className="chat-sidebar-title">Chats</div>
        </div>

        <div className="chat-sidebar-panel">
          <button type="button" className="chat-sidebar-new-btn" onClick={onNewChat}>
            New Chat
          </button>

          <div className="chat-sidebar-section-label">Past Chats</div>
          <div className="chat-sidebar-list">
            {loading ? (
              <div className="chat-sidebar-empty">Loading chats...</div>
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
                  onClick={() => onSelectSession(session.id)}
                >
                  <span className="chat-sidebar-item-title">{session.title || "New Chat"}</span>
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
                      aria-label={`Delete ${session.title || "chat"}`}
                    >
                      ×
                    </span>
                  ) : null}
                </button>
              ))
            ) : (
              <div className="chat-sidebar-empty">No saved chats yet.</div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
