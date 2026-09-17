"use client";

import { isValidElement, useMemo, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { isValidSaintName, normalizeSaintKey } from "./saintNameUtils";

type InteractiveAnswerProps = {
  answer: string;
  entities?: string[];
  saintLookup?: Set<string>;
};

// Answers are Markdown (DECISIONS.md FE-002): paragraphs, lists, bold and GFM tables.
// Raw HTML in the answer is not rendered (react-markdown's default), so model output
// cannot inject markup.

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

function handleNameClick(name: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent("chat:insertAndSubmitText", {
      detail: {
        message: `search saint: ${name.trim()}`,
        displayMessage: name.trim(),
      },
    })
  );
}

export default function InteractiveAnswer({
  answer,
  entities = [],
  saintLookup = new Set<string>(),
}: InteractiveAnswerProps) {
  const clickableNames = useMemo(() => {
    return new Set(
      entities
        .filter((entity) => isValidSaintName(entity, saintLookup))
        .map(normalizeSaintKey)
        .filter(Boolean)
    );
  }, [entities, saintLookup]);

  const components = useMemo<Components>(
    () => ({
      // Bold saint names that the backend extracted stay clickable; other bold text is just bold.
      strong({ children }) {
        const text = textOf(children).trim();
        const clickable =
          text && clickableNames.has(normalizeSaintKey(text)) && isValidSaintName(text, saintLookup);
        if (!clickable) return <strong>{children}</strong>;
        return (
          <button type="button" className="answer-name-button" onClick={() => handleNameClick(text)}>
            <strong>{children}</strong>
          </button>
        );
      },
      // Wide tables scroll inside the bubble instead of stretching the layout.
      table({ children }) {
        return (
          <div className="answer-table-wrap" role="region" aria-label="Table" tabIndex={0}>
            <table>{children}</table>
          </div>
        );
      },
      a({ href, children }) {
        return (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        );
      },
    }),
    [clickableNames, saintLookup]
  );

  return (
    <div className="interactive-answer">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {answer}
      </ReactMarkdown>
    </div>
  );
}
