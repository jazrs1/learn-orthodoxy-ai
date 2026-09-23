"use client";

import { Fragment, isValidElement, useMemo, type MouseEvent, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkCitations from "../lib/remark-citations";
import { isValidSaintName, normalizeSaintKey } from "./saintNameUtils";

export type CitationTarget = {
  href: string;
  label: string;
};

type InteractiveAnswerProps = {
  answer: string;
  entities?: string[];
  saintLookup?: Set<string>;
  /** Resolves a cited passage number to its entry in the Sources list, if it has one. */
  resolveCitation?: (n: number) => CitationTarget | null;
  onCitationClick?: (n: number) => void;
  tableLabel?: string;
  /** Separator between grouped markers ("," or the Arabic comma). */
  citationSeparator?: string;
  /** Menus, refusals and other messages without sources: no drop cap (RET-010). */
  plain?: boolean;
};

// Answers are Markdown (DECISIONS.md FE-002): paragraphs, lists, bold and GFM tables.
// Raw HTML in the answer is not rendered (react-markdown's default), so model output
// cannot inject markup. Inline [n] markers become links to the Sources list (UI-006).

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
  resolveCitation,
  onCitationClick,
  tableLabel = "Table",
  citationSeparator = ",",
  plain = false,
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
      sup({ node, children }) {
        const raw = String(node?.properties?.dataCites ?? "");
        const numbers = raw
          .split(",")
          .map(Number)
          .filter((number) => Number.isInteger(number) && number > 0);
        if (!numbers.length) return <sup>{children}</sup>;

        return (
          <sup className="cite-group">
            {numbers.map((n, index) => {
              const target = resolveCitation?.(n) ?? null;
              return (
                <Fragment key={n}>
                  {index > 0 ? <span className="cite-sep">{citationSeparator}</span> : null}
                  {target ? (
                    <a
                      className="cite"
                      href={target.href}
                      aria-label={target.label}
                      title={target.label}
                      onClick={(event: MouseEvent<HTMLAnchorElement>) => {
                        event.preventDefault();
                        onCitationClick?.(n);
                      }}
                    >
                      {n}
                    </a>
                  ) : (
                    // A passage the Sources list does not show separately (the backend lists
                    // each page once), so there is nothing to jump to.
                    <span className="cite cite-unlinked">{n}</span>
                  )}
                </Fragment>
              );
            })}
          </sup>
        );
      },
      // Wide tables scroll inside the answer instead of stretching the layout.
      table({ children }) {
        return (
          <div className="answer-table-wrap" role="region" aria-label={tableLabel} tabIndex={0}>
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
    [citationSeparator, clickableNames, onCitationClick, resolveCitation, saintLookup, tableLabel]
  );

  return (
    <div className={plain ? "interactive-answer is-plain" : "interactive-answer"}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]} components={components}>
        {answer}
      </ReactMarkdown>
    </div>
  );
}
