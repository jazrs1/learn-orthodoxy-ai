// What the Copy button puts on the clipboard for an answer (UI-031): the question, the answer as
// plain text with its [n] citations kept, and the numbered sources, so a pasted answer still says
// what it was asked and where each point comes from.

import type { SourceRef } from "./chat-types.ts";
import type { Language } from "./i18n.ts";
import { sourceSummary, toDisplaySources } from "./sources.ts";

const TABLE_RULE = /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$/;

/** Markdown to plain text, line by line: lists, tables and paragraphs keep their shape. */
export function markdownToPlainText(markdown: string): string {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const out: string[] = [];
  for (const raw of lines) {
    if (TABLE_RULE.test(raw)) continue;
    let line = raw.replace(/\s+$/, "");
    if (/^\s*\|.*\|\s*$/.test(line)) {
      // A table row: its cells, separated by a spaced bar.
      line = line
        .trim()
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((cell) => cell.trim())
        .join(" | ");
    }
    line = line
      .replace(/^\s{0,3}#{1,6}\s+/, "") // headings
      .replace(/^\s{0,3}>\s?/, "") // quotes
      .replace(/^(\s*)[*+]\s+/, "$1- ") // bullets as "-"
      .replace(/!?\[([^\]]+)\]\((https?:[^)\s]+)\)/g, "$1 ($2)") // links; [n] citations stay
      .replace(/(\*\*|__)(?=\S)(.+?)(?<=\S)\1/g, "$2") // bold
      .replace(/(^|[^\w*])[*_](?=\S)(.+?)(?<=\S)[*_](?=[^\w*]|$)/g, "$1$2") // italics
      .replace(/`+/g, "")
      .replace(/\\([\\`*_[\]()#+\-.!|])/g, "$1"); // Markdown escapes
    out.push(line);
  }
  return out
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function answerCopyText({
  question,
  answer,
  sources,
  language,
  sourcesLabel,
}: {
  question: string;
  answer: string;
  sources?: SourceRef[];
  language: Language;
  sourcesLabel: string;
}): string {
  const parts: string[] = [];
  if (question.trim()) parts.push(question.trim());
  parts.push(markdownToPlainText(answer));
  const items = toDisplaySources(sources);
  if (items.length > 0) {
    const lines = items.map((source) => `${source.n}. ${sourceSummary(source, language)}`);
    parts.push(`${sourcesLabel}:\n${lines.join("\n")}`);
  }
  return parts.join("\n\n");
}
