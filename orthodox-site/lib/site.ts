import type { Metadata } from "next";

// The one place the public domain is defined (UI-010). Used by metadata, sitemap and robots.
export const SITE_URL = "https://learnorthodoxy.net";
export const SITE_NAME = "Learn Orthodoxy";
export const SITE_TAGLINE = "An AI study guide to the Coptic Orthodox faith";
export const SITE_DESCRIPTION =
  "Ask questions about Coptic Orthodox teaching and the lives of the saints. Answers come only from Fr. Tadros Malaty's books and the Coptic Orthodox catechism, with book and page citations, in English and Arabic.";

export const OG_IMAGE = {
  url: "/og-image.png",
  width: 1200,
  height: 630,
  alt: "Learn Orthodoxy — A Coptic Orthodox Study Guide",
};

type PageMetadataInput = {
  /** Page title; the root layout appends " · Learn Orthodoxy". Omit for the home page. */
  title?: string;
  description?: string;
  /** Path starting with "/", used for the canonical URL and og:url. */
  path: string;
};

/**
 * Per-page metadata. Next.js replaces (does not merge) `openGraph` and `twitter` from parent
 * segments, so every page rebuilds them with its own title and URL.
 */
export function pageMetadata({ title, description = SITE_DESCRIPTION, path }: PageMetadataInput): Metadata {
  const socialTitle = title ? `${title} · ${SITE_NAME}` : `${SITE_NAME} — ${SITE_TAGLINE}`;
  return {
    ...(title ? { title } : {}),
    description,
    alternates: { canonical: path },
    openGraph: {
      type: "website",
      siteName: SITE_NAME,
      title: socialTitle,
      description,
      url: path,
      locale: "en_US",
      alternateLocale: ["ar_EG"],
      images: [OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: socialTitle,
      description,
      images: [OG_IMAGE.url],
    },
  };
}
