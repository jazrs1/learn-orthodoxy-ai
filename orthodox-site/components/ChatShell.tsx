"use client";

import { KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { IconSend, IconStop } from "./Icons";
import { useLanguage } from "./LanguageProvider";

type ChatShellProps = {
  initialValue?: string;
  onSubmit?: (message: string, options?: { displayMessage?: string }) => void | Promise<void>;
  isSubmitting?: boolean;
  /** While an answer is on its way, the send button becomes Stop and calls this (UI-026). */
  onStop?: () => void;
};

type ChatSubmitDetail = string | {
  message?: string;
  displayMessage?: string;
};

function normalizeSubmitDetail(detail: ChatSubmitDetail) {
  if (typeof detail === "string") {
    return {
      message: detail.trim(),
      displayMessage: "",
    };
  }

  return {
    message: (detail.message || "").trim(),
    displayMessage: (detail.displayMessage || "").trim(),
  };
}

export default function ChatShell({ initialValue = "", onSubmit, isSubmitting = false, onStop }: ChatShellProps) {
  const [message, setMessage] = useState(initialValue);
  const pathname = usePathname();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { dir, t } = useLanguage();

  useEffect(() => {
    setMessage(initialValue);
  }, [initialValue]);

  // Grow with the text up to the CSS max-height, then scroll inside (UI-008).
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [message]);

  useEffect(() => {
    function handleInsertText(event: Event) {
      const customEvent = event as CustomEvent<string>;
      const nextText = (customEvent.detail || "").trim();
      if (!nextText) return;

      setMessage(nextText);
      requestAnimationFrame(() => {
        textareaRef.current?.focus();
      });
    }

    function handleInsertAndSubmitText(event: Event) {
      if (isSubmitting) return;
      const customEvent = event as CustomEvent<ChatSubmitDetail>;
      const { message: nextText, displayMessage } = normalizeSubmitDetail(customEvent.detail || "");
      if (!nextText) return;

      setMessage("");
      if (onSubmit) {
        void onSubmit(nextText, displayMessage ? { displayMessage } : undefined);
      }
    }

    window.addEventListener("chat:insertText", handleInsertText);
    window.addEventListener("chat:insertAndSubmitText", handleInsertAndSubmitText);
    return () => {
      window.removeEventListener("chat:insertText", handleInsertText);
      window.removeEventListener("chat:insertAndSubmitText", handleInsertAndSubmitText);
    };
  }, [isSubmitting, onSubmit]);

  function submitMessage() {
    if (isSubmitting) return;
    const trimmed = message.trim();
    if (!trimmed) return;

    setMessage("");
    if (onSubmit) {
      void onSubmit(trimmed);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (isSubmitting) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
      }
      return;
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  }

  return (
    <div className={`chat-shell ${pathname === "/chat" ? "chat-shell-chat-page" : ""}`}>
      <div className="chat-shell-inner">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("askPlaceholder")}
          aria-label={t("questionLabel")}
          rows={1}
          disabled={isSubmitting}
          // An empty field follows the page direction so the placeholder reads correctly;
          // typed text picks its own direction.
          dir={message ? "auto" : dir}
        />
        {/* One button, so focus stays on it when Send turns into Stop and back. */}
        {isSubmitting && onStop ? (
          <button
            type="button"
            className="chat-submit chat-stop"
            onClick={onStop}
            aria-label={t("stopAnswer")}
            title={t("stopAnswer")}
          >
            <IconStop size={20} />
          </button>
        ) : (
          <button
            type="button"
            className="chat-submit"
            onClick={submitMessage}
            disabled={isSubmitting || !message.trim()}
            aria-label={t("sendMessage")}
            title={t("sendMessage")}
          >
            <IconSend size={20} />
          </button>
        )}
      </div>
    </div>
  );
}
