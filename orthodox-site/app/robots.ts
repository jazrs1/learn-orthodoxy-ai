import type { MetadataRoute } from "next";
import { SITE_URL } from "../lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Shared answers (/s/) stay allowed: link-preview bots honour robots.txt, and search
      // engines must fetch a page to see its noindex (UI-030). They are not in the sitemap.
      disallow: "/api/",
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
