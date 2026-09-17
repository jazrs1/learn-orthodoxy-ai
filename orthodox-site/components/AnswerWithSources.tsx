"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SourceRef } from "../lib/chat-types";
import { sourceDetails, sourceDomId, sourceSummary, toDisplaySources } from "../lib/sources";
import InteractiveAnswer, { type CitationTarget } from "./InteractiveAnswer";
import { useLanguage } from "./LanguageProvider";

type AnswerWithSourcesProps = {
  answerId: string;
  answer: string;
  sources?: SourceRef[];
  entities?: string[];
  saintLookup?: Set<string>;
};

const COLLAPSED_COUNT = 5;
const HIGHLIGHT_MS = 2400;

export default function AnswerWithSources({
  answerId,
  answer,
  sources,
  entities,
  saintLookup,
}: AnswerWithSourcesProps) {
  const { language, t } = useLanguage();
  const items = useMemo(() => toDisplaySources(sources), [sources]);
  const [expanded, setExpanded] = useState(false);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const highlightTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(highlightTimer.current), []);

  const canCollapse = items.length > COLLAPSED_COUNT + 1;
  const visibleItems = canCollapse && !expanded ? items.slice(0, COLLAPSED_COUNT) : items;

  const resolveCitation = useCallback(
    (n: number): CitationTarget | null => {
      const source = items.find((item) => item.n === n);
      if (!source) return null;
      return {
        href: `#${sourceDomId(answerId, n)}`,
        label: `${t("sourceLabel")} ${n}: ${sourceSummary(source, language)}`,
      };
    },
    [answerId, items, language, t]
  );

  const showSource = useCallback(
    (n: number) => {
      const index = items.findIndex((item) => item.n === n);
      if (index < 0) return;
      if (canCollapse && index >= COLLAPSED_COUNT) setExpanded(true);
      setHighlighted(n);
      window.clearTimeout(highlightTimer.current);
      highlightTimer.current = window.setTimeout(() => setHighlighted(null), HIGHLIGHT_MS);

      // Wait for the expanded list to render before scrolling to the entry.
      requestAnimationFrame(() => {
        const element = document.getElementById(sourceDomId(answerId, n));
        if (!element) return;
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        element.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
        element.focus({ preventScroll: true });
      });
    },
    [answerId, canCollapse, items]
  );

  return (
    <>
      <InteractiveAnswer
        answer={answer}
        entities={entities}
        saintLookup={saintLookup}
        resolveCitation={resolveCitation}
        onCitationClick={showSource}
        tableLabel={t("tableLabel")}
        citationSeparator={language === "ar" ? "،" : ","}
      />
      {items.length > 0 ? (
        <section className="answer-sources" aria-labelledby={`${sourceDomId(answerId, 0)}-heading`}>
          <h3 className="answer-sources-heading" id={`${sourceDomId(answerId, 0)}-heading`}>
            {t("answerSources")}
          </h3>
          <ol className="answer-sources-list">
            {visibleItems.map((source) => {
              const details = sourceDetails(source, language);
              return (
                <li
                  key={source.n}
                  id={sourceDomId(answerId, source.n)}
                  tabIndex={-1}
                  className={`answer-source ${highlighted === source.n ? "answer-source-highlighted" : ""}`}
                >
                  <span className="answer-source-number" dir="ltr">
                    {source.n}
                  </span>
                  <span className="answer-source-body">
                    {source.entry ? <span className="answer-source-entry">{source.entry}</span> : null}
                    <span className="answer-source-title" dir="auto">
                      {source.kind === "website" && source.url ? (
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          {source.title}
                        </a>
                      ) : (
                        source.title
                      )}
                    </span>
                    {details ? <span className="answer-source-details">{details}</span> : null}
                  </span>
                </li>
              );
            })}
          </ol>
          {canCollapse ? (
            <button
              type="button"
              className="answer-sources-toggle"
              aria-expanded={expanded}
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded
                ? t("showFewerSources")
                : t("showAllSources").replace("{count}", String(items.length))}
            </button>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
