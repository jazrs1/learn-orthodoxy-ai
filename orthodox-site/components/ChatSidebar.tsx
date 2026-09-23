"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import type { MouseEvent } from "react";
import { BRAND } from "../lib/brand";
import { ConversationSummary } from "../lib/chat-types";
import { IconClose, IconPlus, IconTrash } from "./Icons";
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
  /** Hide the column on desktop (landing page with no history); the mobile drawer still works. */
  desktopHidden?: boolean;
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
  desktopHidden = false,
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
    <aside
      className={`chat-sidebar ${isMobileOpen ? "chat-sidebar-mobile-open" : ""} ${
        desktopHidden ? "chat-sidebar-desktop-hidden" : ""
      }`}
      aria-label={t("chats")}
    >
      <div className="chat-sidebar-details">
        <div className="chat-sidebar-header">
          <Link href="/" className="chat-sidebar-home-link" onClick={onClose} aria-label={t("home")}>
            <Image
              src={BRAND.lettermark.src}
              alt=""
              width={BRAND.lettermark.width}
              height={BRAND.lettermark.height}
              className="chat-sidebar-home-mark"
            />
          </Link>
          <div className="chat-sidebar-title">{t("chats")}</div>
          {onClose ? (
            <button
              type="button"
              className="icon-button chat-sidebar-close-btn"
              onClick={onClose}
              aria-label={t("closeChatsPanel")}
            >
              <IconClose size={22} />
            </button>
          ) : null}
        </div>

        <div className="chat-sidebar-panel">
          {showAppNav ? (
            <nav className="chat-sidebar-nav" aria-label={t("sectionsNavigation")}>
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
                href="/calendar"
                onClick={() => {
                  if (pathname === "/calendar") {
                    onClose?.();
                  }
                }}
              >
                {t("calendar")}
              </Link>
              <Link
                className="chat-sidebar-nav-btn"
                href="/credits"
                onClick={() => {
                  if (pathname === "/credits") {
                    onClose?.();
                  }
                }}
              >
                {t("credits")}
              </Link>
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
            <IconPlus size={18} />
            <span>{t("newChat")}</span>
          </button>

          <div className="chat-sidebar-section-label">{t("pastChats")}</div>
          <div className="chat-sidebar-list">
            {loading ? (
              <div className="chat-sidebar-empty">{t("loadingChats")}</div>
            ) : error ? (
              <div className="chat-sidebar-empty">{error}</div>
            ) : sessions.length ? (
              <ul className="chat-sidebar-items">
                {sessions.map((session) => {
                  const title = session.title || t("newChat");
                  const active = session.id === activeSessionId;
                  // Open and delete are sibling buttons: a button inside a button is invalid
                  // and unreachable for many screen readers (UI-008).
                  return (
                    <li key={session.id} className={`chat-sidebar-item ${active ? "chat-sidebar-item-active" : ""}`}>
                      <button
                        type="button"
                        className="chat-sidebar-item-open"
                        aria-current={active ? "true" : undefined}
                        onClick={() => {
                          onSelectSession(session.id);
                          onClose?.();
                        }}
                      >
                        <span className="chat-sidebar-item-title" dir="auto">
                          {title}
                        </span>
                      </button>
                      {onDeleteSession ? (
                        <button
                          type="button"
                          className="icon-button chat-sidebar-item-delete"
                          onClick={() => onDeleteSession(session.id)}
                          aria-label={`${t("deleteChat")}: ${title}`}
                          title={t("deleteChat")}
                        >
                          <IconTrash size={17} />
                        </button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="chat-sidebar-empty">{t("noSavedChats")}</div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
