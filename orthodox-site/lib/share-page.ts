// The shared page's text and link-preview tags (UI-030), kept pure so they can be tested.

import type { Metadata } from "next";
import { OG_IMAGE, SITE_NAME } from "./site.ts";
import { plainAnswerText } from "./stream-markdown.ts";
import type { Snapshot } from "./share-store.ts";

/**
 * A preview's description: the answer's prose as plain text, cut at a word near `limit`
 * characters. Tables are left out (flattened, their cells read as nonsense), unless there is
 * nothing else.
 */
export function shareExcerpt(answer: string, limit = 160): string {
  const prose = answer
    .split("\n")
    .filter((line) => !/^\s*\|/.test(line))
    .join("\n");
  const text = plainAnswerText(prose) || plainAnswerText(answer);
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > limit * 0.6 ? cut.slice(0, lastSpace) : cut).replace(/[\s,;:،؛.]+$/, "")}…`;
}

/** The title a preview shows: the question, shortened if very long. */
export function shareTitle(question: string, limit = 90): string {
  const text = question.replace(/\s+/g, " ").trim();
  return text.length <= limit ? text : `${text.slice(0, limit - 1).trimEnd()}…`;
}

/**
 * The day the answer was given, as the sharer's calendar had it when they shared it (UI-034), so
 * every reader sees the same date. Snapshots without it fall back to the UTC day.
 */
export function shareDate(
  snapshot: Pick<Snapshot, "answeredOn" | "answeredAt" | "createdAt" | "language">
): { iso: string; text: string } {
  const iso = snapshot.answeredOn || (snapshot.answeredAt || snapshot.createdAt).slice(0, 10);
  const text = new Intl.DateTimeFormat(snapshot.language === "ar" ? "ar-EG" : "en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${iso}T00:00:00Z`));
  return { iso, text };
}

/**
 * Open Graph and Twitter tags so WhatsApp, iMessage and others show the question, a short excerpt
 * and the site's card. Shared pages are never indexed (they aren't in the sitemap either).
 */
export function sharedAnswerMetadata(snapshot: Snapshot): Metadata {
  const title = shareTitle(snapshot.question);
  const description = shareExcerpt(snapshot.answer);
  const path = `/s/${snapshot.id}`;
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: path },
    robots: { index: false, follow: false },
    openGraph: {
      type: "article",
      siteName: SITE_NAME,
      title,
      description,
      url: path,
      locale: snapshot.language === "ar" ? "ar_EG" : "en_US",
      publishedTime: snapshot.answeredAt || snapshot.createdAt,
      images: [OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [OG_IMAGE.url],
    },
  };
}
