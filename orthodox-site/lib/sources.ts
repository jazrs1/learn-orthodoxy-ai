import type { SourceRef } from "./chat-types";
import type { Language } from "./i18n";

// Human-readable titles for the indexed books, keyed by the file name the backend returns
// (mirrors SOURCE_TITLES in api.py, split into title and volume). The PDFs themselves are
// not linked (UI-006): citations are shown as text only.
const BOOKS: Record<string, { title: string; volume?: number }> = {
  "catechism1.pdf": { title: "Catechism of the Coptic Orthodox Church", volume: 1 },
  "catechism2.pdf": { title: "Catechism of the Coptic Orthodox Church", volume: 2 },
  "saints1.pdf": { title: "Encyclopedia of the Saints and Fathers of the Church", volume: 1 },
  "saints2.pdf": { title: "Encyclopedia of the Saints and Fathers of the Church", volume: 2 },
  "saints3.pdf": { title: "Encyclopedia of the Saints and Fathers of the Church", volume: 3 },
  "saints4.pdf": { title: "Encyclopedia of the Saints and Fathers of the Church", volume: 4 },
  "full arabic catechism.pdf": { title: "كاتيكيزم الكنيسة القبطية الأرثوذكسية" },
  "full saints arabic.pdf": { title: "قاموس آباء الكنيسة وقديسيها" },
};

const LTR_ISOLATE = String.fromCharCode(0x2066);
const POP_ISOLATE = String.fromCharCode(0x2069);

export type DisplaySource = {
  /** The passage number the answer cites as [n]. */
  n: number;
  kind: "book" | "website";
  title: string;
  volume?: number;
  page?: number;
  /** Printed page or range ("33–35"); shown instead of `page`, the PDF page, when present. */
  pages?: string;
  /** Saint entry or article name, when the backend provides one. */
  entry?: string;
  url?: string;
};

function titleFromLabel(label: string | undefined) {
  // Backend labels look like "Encyclopedia of the Saints ..., Volume 2, p. 406".
  return (label || "").replace(/,\s*(?:Volume\s+\d+\s*,\s*)?p\.\s*\d+\s*$/i, "").trim();
}

function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function toDisplaySources(sources: SourceRef[] | undefined): DisplaySource[] {
  const result: DisplaySource[] = [];
  const seen = new Set<number>();

  (sources || []).forEach((source, index) => {
    if (!source) return;
    // Sources saved before numbered citations existed have no `n`; number them in order.
    const n = typeof source.n === "number" && source.n > 0 ? source.n : index + 1;
    if (seen.has(n)) return;
    seen.add(n);

    if (source.source_type === "website" || (!source.pdf && source.url)) {
      const url = source.url || "";
      result.push({
        n,
        kind: "website",
        title: source.title?.trim() || hostOf(url) || "Website",
        url: /^https?:\/\//i.test(url) ? url : undefined,
        entry: source.entry?.trim() || undefined,
      });
      return;
    }

    const file = source.pdf || "";
    const book = BOOKS[file];
    result.push({
      n,
      kind: "book",
      title: book?.title || titleFromLabel(source.label) || file.replace(/\.pdf$/i, ""),
      volume: book?.volume,
      page: typeof source.page === "number" && source.page > 0 ? source.page : undefined,
      pages: source.pages?.trim() || undefined,
      entry: source.entry?.trim() || source.title?.trim() || undefined,
    });
  });

  return result;
}

export function sourceDetails(source: DisplaySource, language: Language) {
  const parts: string[] = [];
  if (source.volume) parts.push(language === "ar" ? `المجلد ${source.volume}` : `Vol. ${source.volume}`);
  if (source.pages) {
    const marker = /[–-]/.test(source.pages) ? "pp." : "p.";
    // In right-to-left text a range such as "118–119" is laid out as "119–118"; an LTR isolate keeps
    // it in reading order (checked in Chrome, ING-007).
    parts.push(language === "ar" ? `ص ${LTR_ISOLATE}${source.pages}${POP_ISOLATE}` : `${marker} ${source.pages}`);
  } else if (source.page) {
    parts.push(language === "ar" ? `ص ${source.page}` : `p. ${source.page}`);
  }
  if (source.kind === "website" && source.url) parts.push(hostOf(source.url));
  return parts.join(" · ");
}

/** One-line description used for the citation marker's accessible name and tooltip. */
export function sourceSummary(source: DisplaySource, language: Language) {
  const details = sourceDetails(source, language);
  return [source.entry, source.title, details].filter(Boolean).join(language === "ar" ? "، " : ", ");
}

export function sourceDomId(answerId: string, n: number) {
  return `src-${answerId.replace(/[^a-zA-Z0-9_-]/g, "")}-${n}`;
}
