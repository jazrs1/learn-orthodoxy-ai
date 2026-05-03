"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

type ChatShellProps = {
  initialValue?: string;
  onSubmit?: (message: string) => void | Promise<void>;
  isSubmitting?: boolean;
};

export default function ChatShell({ initialValue = "", onSubmit, isSubmitting = false }: ChatShellProps) {
  const [message, setMessage] = useState(initialValue);
  const router = useRouter();
  const pathname = usePathname();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
      const customEvent = event as CustomEvent<string>;
      const nextText = (customEvent.detail || "").trim();
      if (!nextText) return;

      setMessage("");
      if (onSubmit) {
        void onSubmit(nextText);
      } else {
        router.push(`/chat?q=${encodeURIComponent(nextText)}`);
      }
    }

    window.addEventListener("chat:insertText", handleInsertText);
    window.addEventListener("chat:insertAndSubmitText", handleInsertAndSubmitText);
    return () => {
      window.removeEventListener("chat:insertText", handleInsertText);
      window.removeEventListener("chat:insertAndSubmitText", handleInsertAndSubmitText);
    };
  }, [isSubmitting, onSubmit, router]);

  function submitMessage() {
    if (isSubmitting) return;
    const trimmed = message.trim();
    if (!trimmed) return;

    setMessage("");
    if (onSubmit) {
      void onSubmit(trimmed);
      return;
    }

    router.push(`/chat?q=${encodeURIComponent(trimmed)}`);
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
          placeholder="Ask about a saint or catechism..."
          rows={1}
          disabled={isSubmitting}
        />
        <button
          type="button"
          className="chat-submit"
          onClick={submitMessage}
          disabled={isSubmitting || !message.trim()}
          aria-label="Send message"
        >
          →
        </button>
      </div>
    </div>
  );
}
