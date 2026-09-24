// Share links in the browser (UI-032): the Share flow, the shared page, the not-found page, reuse,
// the rate limit, link-preview tags as preview bots see them, and axe. No OpenAI calls.
//
// Run against a production build with the scripted backend and a fresh local Postgres:
//   node pg-server.mjs ../../orthodox-site/migrations/001_create_chat_tables.sql ../../orthodox-site/migrations/002_shared_answers.sql
//   OPENAI_API_KEY=none python ui-audit/tools/fake_stream_backend.py
//   POSTGRES_URL=postgres://postgres:postgres@localhost:5433/postgres ORTHODOX_API_URL=http://127.0.0.1:8001 \
//     ORTHODOX_API_KEY=localkey npx next start -p 3217
//   CHROME_BIN=… node share.mjs ../share
// Needs playwright, @axe-core/playwright and open-graph-scraper next to this script. The rate-limit
// check expects the database to be fresh (no share requests in the last 10 minutes).
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import ogs from "open-graph-scraper";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const OUT = process.argv[2] || "share-out";
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
const report = { base: BASE, at: new Date().toISOString(), flows: {}, pages: {}, notFound: {}, previews: {}, axe: {}, shareStatuses: [] };

const QUESTIONS = { en: "Show me a table of the fasts", ar: "اعرض جدولًا بأصوام الكنيسة" };

async function newContext(lang, width) {
  const phone = width < 600;
  const context = await browser.newContext({
    viewport: { width, height: phone ? 844 : 900 },
    isMobile: phone,
    hasTouch: phone,
    deviceScaleFactor: phone ? 2 : 1,
  });
  await context.addCookies([{ name: "lo_lang", value: lang, url: BASE }]);
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  // Headless Chrome has no share sheet: record what the page hands it instead.
  if (phone) {
    await context.addInitScript(() => {
      window.__shared = [];
      navigator.share = async (data) => {
        window.__shared.push(data);
      };
    });
  }
  context.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/share") report.shareStatuses.push(response.status());
  });
  return context;
}

async function axe(page, name) {
  const result = await new AxeBuilder({ page }).analyze();
  report.axe[name] = result.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, target: v.nodes[0]?.target }));
  if (result.violations.length) {
    report.axe[`${name}-context`] = await page.evaluate(() => ({
      url: location.href,
      title: document.title,
      titleTags: [...document.querySelectorAll("title")].map((t) => `${t.parentElement?.tagName}:${t.textContent}`),
    }));
  }
}

const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
const shot = (page, name, fullPage = false) => page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage });

async function ask(page, question) {
  await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });
  await page.locator(".chat-input").fill(question);
  await page.locator(".chat-submit").click();
  await page.waitForURL(/\?chat=/, { timeout: 60000 });
}

/** Presses Share on the last answer; returns the link and how it was handed over. */
async function share(page, phone, name) {
  const row = page.locator(".assistant-row").last();
  const button = row.locator(".message-actions button").nth(1);
  await button.waitFor();
  await button.scrollIntoViewIfNeeded();
  await shot(page, `${name}-1-button`);
  if (phone) await button.tap();
  else await button.click();
  const outcome = await Promise.race([
    page.waitForSelector(".chat-alert-text", { timeout: 15000 }).then(() => "alert"),
    phone
      ? page.waitForFunction(() => window.__shared.length > 0, null, { timeout: 15000 }).then(() => "sheet")
      : page.waitForSelector(".message-action-note", { timeout: 15000 }).then(() => "copied"),
  ]);
  if (outcome === "alert") throw new Error(`share failed: ${await page.locator(".chat-alert-text").innerText()}`);
  await shot(page, `${name}-2-after`);
  const result = { label: await button.getAttribute("aria-label") };
  if (phone) {
    const [data] = await page.evaluate(() => window.__shared);
    Object.assign(result, { via: "share sheet", title: data.title, url: data.url });
  } else {
    Object.assign(result, {
      via: "clipboard",
      note: await row.locator(".message-action-note").innerText(),
      url: await page.evaluate(() => navigator.clipboard.readText()),
    });
  }
  result.messageId = await row.getAttribute("data-message-id");
  return result;
}

// 1. The Share flow: English and Arabic, desktop (copy) and phone (share sheet).
const links = {};
for (const lang of ["en", "ar"]) {
  for (const width of [1440, 390]) {
    const name = `flow-${lang}-${width}`;
    const context = await newContext(lang, width);
    const page = await context.newPage();
    await ask(page, QUESTIONS[lang]);
    const result = await share(page, width < 600, name);
    // Let the chat's own URL change (?chat=…, RET-021) finish first: axe run during it has twice
    // found the document title missing for a moment, though it was there straight after (UI-033).
    await page.waitForLoadState("networkidle");
    await axe(page, name);
    // The same answer shared again gets the same link.
    result.again = await page.evaluate(
      async (id) => (await fetch("/api/share", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messageId: id }) })).json(),
      result.messageId
    );
    report.flows[name] = result;
    links[lang] ??= result.url;
    await context.close();
  }
}
report.sameLinkAcrossSessions = {
  en: report.flows["flow-en-1440"].url === report.flows["flow-en-390"].url,
  ar: report.flows["flow-ar-1440"].url === report.flows["flow-ar-390"].url,
};

// 2. The shared page, in its own language and on a page in the other language.
const PAGE_CASES = [
  ["en", "en", 1440],
  ["en", "en", 390],
  ["ar", "ar", 1440],
  ["ar", "ar", 390],
  ["ar", "en", 390],
  ["en", "ar", 1440],
];
for (const [snapshotLang, pageLang, width] of PAGE_CASES) {
  const name = `page-${snapshotLang}-on-${pageLang}-${width}`;
  const context = await newContext(pageLang, width);
  const page = await context.newPage();
  const response = await page.goto(links[snapshotLang], { waitUntil: "networkidle" });
  await shot(page, name, true);
  await axe(page, name);
  report.pages[name] = await page.evaluate(() => {
    const article = document.querySelector(".shared-answer");
    const ask = [...document.querySelectorAll(".shared-answer a")].find((a) => a.closest(".shared-answer-actions"));
    return {
      lang: article?.getAttribute("lang"),
      dir: article?.getAttribute("dir"),
      h1: document.querySelector("h1")?.textContent,
      tables: article?.querySelectorAll("table").length,
      tableRows: article?.querySelectorAll("tbody tr").length,
      sources: article?.querySelectorAll(".answer-source").length,
      sourceLine: article?.querySelector(".answer-source")?.textContent,
      footer: document.querySelector(".shared-answer-footer")?.textContent,
      ask: ask ? { text: ask.textContent, href: ask.getAttribute("href") } : null,
      robots: document.querySelector('meta[name="robots"]')?.getAttribute("content"),
      title: document.title,
    };
  });
  Object.assign(report.pages[name], { status: response.status(), overflowPx: await overflow(page) });
  await context.close();
}

// 3. Not found: an ID of the right shape that doesn't exist, and a malformed one.
for (const [id, width] of [["AAAAAAAAAAAAAAAA", 1440], ["not-a-real-link", 390]]) {
  const name = `notfound-${width}`;
  const context = await newContext("en", width);
  const page = await context.newPage();
  const response = await page.goto(`${BASE}/s/${id}`, { waitUntil: "networkidle" });
  await shot(page, name, true);
  await axe(page, name);
  report.notFound[name] = {
    id,
    status: response.status(),
    h1: await page.locator("h1").innerText(),
    robots: await page.locator('meta[name="robots"]').first().getAttribute("content"),
    overflowPx: await overflow(page),
  };
  await context.close();
}

// 4. The rate limit: keep asking for links until refused, then press Share.
{
  const context = await newContext("en", 1440);
  const page = await context.newPage();
  await ask(page, "What is prayer?");
  const button = page.locator(".assistant-row").last().locator(".message-actions button").nth(1);
  await button.waitFor();
  const messageId = await page.locator(".assistant-row").last().getAttribute("data-message-id");
  const before = report.shareStatuses.length;
  const statuses = await page.evaluate(async (id) => {
    const out = [];
    for (let i = 0; i < 25; i += 1) {
      const r = await fetch("/api/share", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messageId: id }) });
      out.push(r.status);
      if (r.status === 429) break;
    }
    return out;
  }, messageId);
  await button.click();
  await page.waitForSelector(".chat-alert-text");
  await shot(page, "ratelimit-1440");
  report.rateLimit = {
    requestsBeforeThisCheck: before,
    statuses,
    firstRefusalAtRequest: before + statuses.indexOf(429) + 1,
    alert: await page.locator(".chat-alert-text").innerText(),
  };
  await context.close();
}

// 5. Link previews, as the preview fetchers see the page.
const AGENTS = {
  WhatsApp: "WhatsApp/2.23.20.0",
  iMessage: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/601.2.4 (KHTML, like Gecko) Version/9.0.1 Safari/601.2.4 facebookexternalhit/1.1 Facebot Twitterbot/1.0",
  Facebook: "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
  Twitter: "Twitterbot/1.0",
  Telegram: "TelegramBot (like TwitterBot)",
  Slack: "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
  Discord: "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
  LinkedIn: "LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)",
  Signal: "Signal-Android/7.0",
  Browser: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
};
const REQUIRED = ["og:title", "og:description", "og:image", "og:url", "og:type", "twitter:card", "twitter:image"];
for (const lang of ["en", "ar"]) {
  for (const [agent, ua] of Object.entries(AGENTS)) {
    const html = await (await fetch(links[lang], { headers: { "user-agent": ua } })).text();
    const head = html.slice(0, html.indexOf("</head>"));
    const inHead = Object.fromEntries(REQUIRED.map((key) => [key, new RegExp(`(property|name)="${key}"`).test(head)]));
    // The validator won't fetch localhost itself, so it parses the page this agent was served.
    const { result, error } = await ogs({ html }).catch((failure) => ({ error: failure }));
    report.previews[`${lang}-${agent}`] = {
      allTagsInHead: Object.values(inHead).every(Boolean),
      missingFromHead: Object.keys(inHead).filter((k) => !inHead[k]),
      robots: /<meta name="robots" content="([^"]+)"/.exec(head)?.[1] ?? null,
      validator: error
        ? { error: true }
        : {
            ogTitle: result.ogTitle,
            ogDescription: result.ogDescription,
            ogImage: result.ogImage?.[0]?.url,
            ogImageSize: result.ogImage?.[0] ? `${result.ogImage[0].width}x${result.ogImage[0].height}` : null,
            ogUrl: result.ogUrl,
            ogType: result.ogType,
            ogLocale: result.ogLocale,
            twitterCard: result.twitterCard,
          },
    };
  }
}
// The card image: served locally, and live at the address the tags give.
const png = Buffer.from(await (await fetch(`${BASE}/og-image.png`)).arrayBuffer());
const live = await fetch("https://learnorthodoxy.net/og-image.png", { method: "HEAD" }).catch(() => null);
report.ogImage = {
  localStatus: 200,
  localSize: `${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`,
  liveStatus: live?.status ?? "unreachable",
  liveType: live?.headers.get("content-type") ?? null,
};
const sitemap = await (await fetch(`${BASE}/sitemap.xml`)).text();
const robots = await (await fetch(`${BASE}/robots.txt`)).text();
report.search = { sitemapHasShared: sitemap.includes("/s/"), robotsDisallowsShared: /Disallow: \/s\//.test(robots) };

await browser.close();
fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
const violations = Object.values(report.axe).reduce((n, list) => n + list.length, 0);
console.log(JSON.stringify({ ...report, axe: `${violations} violations in ${Object.keys(report.axe).length} states` }, null, 2));
