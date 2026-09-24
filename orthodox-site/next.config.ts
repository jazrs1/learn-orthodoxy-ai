import type { NextConfig } from "next";
import { BRAND } from "./lib/brand";

// Link-preview fetchers that need the <meta> tags inside <head>, so they get the page with its
// metadata rendered before streaming (UI-030). Next's default list (next/dist/shared/lib/router/
// utils/html-bots.js in 16.2) already has WhatsApp, facebookexternalhit (iMessage uses it too),
// Twitterbot, Slackbot, LinkedInBot and Discordbot; setting this option replaces that list, so it
// is repeated here with the fetchers it lacks (Telegram, Signal, Viber, Pinterest, Mastodon, …).
const NEXT_DEFAULT_HTML_BOTS =
  "[\w-]+-Google|Google-[\w-]+|Chrome-Lighthouse|Slurp|DuckDuckBot|baiduspider|yandex|sogou|bitlybot|tumblr|vkShare|quora link preview|redditbot|ia_archiver|Bingbot|BingPreview|applebot|facebookexternalhit|facebookcatalog|Twitterbot|LinkedInBot|Slackbot|Discordbot|WhatsApp|SkypeUriPreview|Yeti|googleweblight";
const MORE_PREVIEW_BOTS = "TelegramBot|Signal|Viber|Pinterest|Mastodon|Iframely|Embedly|Snapchat";

const nextConfig: NextConfig = {
  htmlLimitedBots: new RegExp(`${NEXT_DEFAULT_HTML_BOTS}|${MORE_PREVIEW_BOTS}`, "i"),
  async redirects() {
    return [
      // /about was an unstyled, unlinked draft; /sources was the old name of the credits page (UI-010).
      { source: "/about", destination: "/credits", permanent: true },
      { source: "/sources", destination: "/credits", permanent: true },
    ];
  },
  async rewrites() {
    // Browsers and crawlers that ask for /favicon.ico directly get the current brand favicon (UI-014).
    return [{ source: "/favicon.ico", destination: BRAND.favicon }];
  },
};

export default nextConfig;
