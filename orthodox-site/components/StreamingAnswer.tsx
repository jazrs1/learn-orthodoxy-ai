"use client";

import { useRef } from "react";
import { streamView } from "../lib/stream-markdown";
import type { StreamWordsOptions } from "../lib/rehype-stream-words";
import InteractiveAnswer from "./InteractiveAnswer";
import { useLanguage } from "./LanguageProvider";

// A word fades in over the CSS animation's length; this is a little longer, so its class stays
// until the fade has finished (UI-026).
const FRESH_MS = 450;

/**
 * The answer while it is being written (UI-026): Markdown rendered as it arrives, new words
 * fading in (no animation with reduced motion), a table shown only once its rows are complete,
 * and citation numbers not yet linked. When the answer is complete it is replaced by the full
 * answer with its Sources list. A stopped answer keeps what was complete, without the table note.
 */
export default function StreamingAnswer({ text, stopped = false }: { text: string; stopped?: boolean }) {
  const { language, t } = useLanguage();
  const view = streamView(text);
  // When each word (by position in reading order) first appeared.
  const firstSeen = useRef<number[]>([]);
  const now = performance.now();
  const streamWords: StreamWordsOptions = {
    isFresh: (index) => {
      const seen = (firstSeen.current[index] ??= now);
      return now - seen < FRESH_MS;
    },
  };

  return (
    <>
      <InteractiveAnswer
        answer={view.text}
        tableLabel={t("tableLabel")}
        citationSeparator={language === "ar" ? "،" : ","}
        streamWords={streamWords}
      />
      {view.tableHeld && !stopped ? <p className="stream-table-note">{t("preparingTable")}</p> : null}
    </>
  );
}
