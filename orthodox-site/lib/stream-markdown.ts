// What of a half-written answer can be shown (UI-026). The model writes Markdown; mid-stream it
// is incomplete in ways that would flash on screen: a table without its last rows, a citation
// marker cut in half ("[1"), bold still open ("**St. Anthony"). Only complete parts are shown.

export type StreamView = {
  /** Markdown to render now. */
  text: string;
  /** A table is being written and is not shown yet. */
  tableHeld: boolean;
};

const isTableLine = (line: string) => line.trimStart().startsWith("|");

/**
 * A table at the end of the text is still being written until a line that isn't a table row
 * follows it (a blank line or text), or the stream ends. Until then, it is cut off.
 */
function holdOpenTable(text: string): { text: string; held: boolean } {
  const lines = text.split("\n");
  // "…| row |\n" ends with an empty line: the next row may still come.
  let last = lines.length - 1;
  if (lines[last] === "" && last > 0) last -= 1;
  if (!isTableLine(lines[last])) return { text, held: false };
  let start = last;
  while (start > 0 && isTableLine(lines[start - 1])) start -= 1;
  return { text: lines.slice(0, start).join("\n").replace(/\s+$/, ""), held: true };
}

// "[", "[1", "[1," or "[1, 2" at the very end: a citation marker still being written.
const PARTIAL_CITATION = /\[(?:\d{1,3}(?:\s*[,;،]\s*\d{0,3})*)?$/;
// A list item or heading whose text hasn't arrived yet ("2.", "-", "##"): it would show as an empty bullet.
const EMPTY_LAST_LINE_MARKER = /\n[ \t]*(?:\d{1,3}[.)]|[-*+]|#{1,6})[ \t]*$/;

export function streamView(raw: string, complete = false): StreamView {
  if (complete) return { text: raw, tableHeld: false };
  const table = holdOpenTable(raw);
  let text = table.text.replace(PARTIAL_CITATION, "").replace(EMPTY_LAST_LINE_MARKER, "").replace(/\s+$/, "");
  // Close bold that is still open, so "**St. Anth" shows as bold rather than asterisks.
  if ((text.match(/\*\*/g) || []).length % 2 === 1) {
    text = text.endsWith("**") ? text.slice(0, -2).replace(/[ \t]+$/, "") : `${text}**`;
  }
  return { text, tableHeld: table.held };
}

/**
 * The answer as plain text, for the one screen-reader announcement made when it is complete:
 * no citation numbers, Markdown marks or table rules.
 */
export function plainAnswerText(markdown: string): string {
  return markdown
    .replace(/\s*\[\d{1,3}(?:\s*[,;،]\s*\d{1,3})*\]/g, "")
    .replace(/^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$/gm, "")
    .replace(/\|/g, " ")
    .replace(/^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])\s+/gm, "")
    .replace(/[*_`]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
