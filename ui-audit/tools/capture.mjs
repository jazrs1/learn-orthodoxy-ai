// UI audit capture: screenshots every page/state with all /api/* calls mocked in the browser.
// No request reaches the backend, Postgres, or OpenAI.
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://localhost:3217";
const OUT = process.argv[2];
const FX = JSON.parse(fs.readFileSync(new URL("./fixtures.json", import.meta.url), "utf-8"));
fs.mkdirSync(OUT, { recursive: true });

FX["OOC-10"].answer = "لم أجد معلومات كافية عن عاصمة فرنسا في المصادر العربية المتاحة.";
FX["OOC-10"].sources = [];
FX["OOC-10"].options = [];

// Synthetic Arabic table (no real Arabic table answer exists in eval results).
const AR_TABLE = {
  question: "اعمل جدول بالفرق بين المعمودية والميرون",
  answer:
    "فيما يلي مقارنة مختصرة بين السرّين كما وردت في كتب التعليم الكنسي:\n\n" +
    "| الجانب | المعمودية | الميرون |\n|---|---|---|\n" +
    "| المعنى | الولادة الجديدة من الماء والروح [1] | مسحة الروح القدس وختم العطية [2] |\n" +
    "| التوقيت | يُمنح أولاً وبعده مباشرة الميرون [1] | يُمنح بعد المعمودية مباشرة [2] |\n" +
    "| التكرار | لا يُعاد | لا يُعاد |\n" +
    "| الخادم | الأسقف أو الكاهن | الأسقف أو الكاهن بالميرون المقدس |\n\n" +
    "**ملاحظة:** هذا الجدول ملخّص، ويمكنك طلب مزيد من التفاصيل عن أيّ سرّ.",
  options: ["هل تريد أن تعرف كيف يستعد الموعوظ للمعمودية؟"],
  sources: [{ source_type: "pdf", pdf: "full arabic catechism.pdf", page: 212 }],
  entities: [],
};

const ERROR_TEXT = "The Orthodox AI backend is unreachable right now. Please try again in a moment.";
const now = new Date().toISOString();

function conv(id, title, turns) {
  const messages = [];
  turns.forEach((fx, i) => {
    messages.push({ id: `${id}-u${i}`, role: "user", content: fx.question, entities: [], options: [], sources: [] });
    messages.push({
      id: `${id}-a${i}`, role: "assistant", content: fx.answer,
      entities: fx.entities || [], options: fx.options || [], sources: fx.sources || [],
    });
  });
  return { id, title, createdAt: now, updatedAt: now, messages };
}

const SEEDS = {
  en: {
    long: conv("c-long", "How does the death of Christ save us?", [FX["CAT-06"]]),
    table: conv("c-table", "Catholic vs Coptic table", [FX["PRD-03"]]),
    table2: conv("c-table2", "Tunes table", [FX["TSK-09"]]),
    refusal: conv("c-refusal", "Capital of France", [{ ...FX["OOC-03"], question: "What is the capital of France?" }]),
    saint: conv("c-saint", "St. Moses the Black", [FX["KW-03"]]),
  },
  ar: {
    long: conv("c-long", FX["AR-08"].question, [FX["AR-08"]]),
    table: conv("c-table", AR_TABLE.question, [AR_TABLE]),
    refusal: conv("c-refusal", FX["OOC-10"].question, [FX["OOC-10"]]),
    saint: conv("c-saint", FX["AR-02"].question, [FX["AR-02"]]),
  },
};

async function installMocks(page, lang, opts = {}) {
  const convs = { ...(opts.convs || {}) };
  const list = () => Object.values(convs).map(({ messages, ...s }) => s);
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname;
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (p === "/api/conversations" && req.method() === "GET") return json({ conversations: list() });
    if (p === "/api/conversations" && req.method() === "POST") {
      const c = { id: "c-new", title: lang === "ar" ? "محادثة جديدة" : "New Chat", createdAt: now, updatedAt: now, messages: [] };
      convs[c.id] = c;
      const { messages, ...s } = c;
      return json({ conversation: s });
    }
    if (p.startsWith("/api/conversations/")) {
      const id = decodeURIComponent(p.split("/").pop());
      if (req.method() === "DELETE") return json({ success: true });
      return convs[id] ? json({ conversation: convs[id] }) : json({ error: "Not found" }, 404);
    }
    if (p === "/api/saints") {
      const q = (url.searchParams.get("q") || "").toLowerCase();
      const all = FX.saints[url.searchParams.get("language") === "ar" ? "ar" : "en"].filter((n) => n.toLowerCase().includes(q));
      const off = +url.searchParams.get("offset") || 0;
      const lim = +url.searchParams.get("limit") || 200;
      return json({ saints: all.slice(off, off + lim), total: all.length });
    }
    if (p === "/api/saint-detail") {
      if (opts.saintDelay) await new Promise((r) => setTimeout(r, opts.saintDelay));
      const fx = lang === "ar" ? FX["AR-02"] : FX["SNT-08"];
      return json({ answer: fx.answer, entities: [], options: [], sources: fx.sources, canLearnMore: true });
    }
    if (p === "/api/chat") {
      if (opts.chatDelay) await new Promise((r) => setTimeout(r, opts.chatDelay));
      if (opts.chatError) return json({ error: ERROR_TEXT }, 500);
      const body = req.postDataJSON();
      const fx = lang === "ar" ? FX["AR-08"] : FX["CAT-06"];
      const c = convs["c-new"] || { id: "c-new", title: body.question, createdAt: now, updatedAt: now, messages: [] };
      const u = { id: "u-x", role: "user", content: body.displayQuestion || body.question };
      const a = { id: "a-x", role: "assistant", content: fx.answer, entities: [], options: fx.options, sources: fx.sources };
      c.messages.push(u, a);
      convs[c.id] = c;
      const { messages, ...s } = c;
      return json({ conversation: s, userMessage: u, assistantMessage: a });
    }
    return json({ error: "unmocked" }, 404);
  });
}

const VIEWPORTS = {
  desktop: { viewport: { width: 1440, height: 900 } },
  mobile: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};

const report = { console: {}, overflow: {}, axe: {}, titles: {}, tapTargets: {} };
let browser;

async function newPage(vp, lang, mockOpts, colorScheme = "light") {
  const ctx = await browser.newContext({ ...VIEWPORTS[vp], colorScheme, locale: lang === "ar" ? "ar-EG" : "en-US" });
  await ctx.addInitScript((l) => {
    try { localStorage.setItem("learn-orthodoxy-language", l); } catch {}
  }, lang);
  // The site reads the language from a cookie on the server since UI-008; older builds use localStorage.
  await ctx.addCookies([{ name: "lo_lang", value: lang, url: BASE }]);
  const page = await ctx.newPage();
  const logs = [];
  page.on("console", (m) => logs.push(`[${m.type()}] ${m.text().slice(0, 300)}`));
  page.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
  page._logs = logs;
  await installMocks(page, lang, mockOpts);
  return page;
}

async function shot(page, name, { full = false } = {}) {
  await page.waitForTimeout(350);
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: full });
  const m = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
    title: document.title,
  }));
  if (m.scrollW > m.clientW) report.overflow[name] = m;
  report.titles[name] = m.title;
  report.console[name] = [...page._logs];
  page._logs.length = 0;
}

async function axe(page, name) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "best-practice"]).analyze();
  report.axe[name] = r.violations.map((v) => ({ id: v.id, impact: v.impact, count: v.nodes.length, help: v.help, sample: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) }));
}

async function smallTargets(page, name) {
  report.tapTargets[name] = await page.evaluate(() =>
    [...document.querySelectorAll("button, a, input, textarea, [role=button]")]
      .filter((el) => el.offsetParent !== null)
      .map((el) => { const r = el.getBoundingClientRect(); return { t: (el.getAttribute("aria-label") || el.textContent || el.tagName).trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }; })
      .filter((x) => x.w > 0 && (x.w < 44 || x.h < 44))
  );
}

async function scrollChatTo(page, where) {
  await page.evaluate((w) => {
    const el = document.querySelector(".chat-messages");
    if (el) el.scrollTop = w === "bottom" ? el.scrollHeight : 0;
  }, where);
}

async function run(vp, lang) {
  const pre = `${lang}-${vp}`;
  const seeds = SEEDS[lang];
  const isMobile = vp === "mobile";

  // Home
  let page = await newPage(vp, lang, {});
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await shot(page, `${pre}-01-home`);
  await axe(page, `${pre}-home`);
  if (isMobile) {
    await smallTargets(page, `${pre}-home`);
    await page.click(".navbar-sidebar-toggle");
    await shot(page, `${pre}-02-home-menu-open`);
  }
  await page.context().close();

  // Chat empty
  page = await newPage(vp, lang, {});
  await page.goto(BASE + "/chat", { waitUntil: "networkidle" });
  await shot(page, `${pre}-03-chat-empty`);
  await axe(page, `${pre}-chat-empty`);
  if (isMobile) await smallTargets(page, `${pre}-chat-empty`);

  // Loading (question typed, response delayed)
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await installMocks(page, lang, { chatDelay: 4000 });
  const q = lang === "ar" ? FX["AR-08"].question : FX["CAT-06"].question;
  await page.fill(".chat-input", q);
  await shot(page, `${pre}-04-chat-typed`);
  await page.click(".chat-submit");
  await page.waitForTimeout(600);
  await shot(page, `${pre}-05-chat-loading`);
  await page.waitForSelector(".interactive-answer", { timeout: 10000 });
  await shot(page, `${pre}-06-chat-answer-arrived`);
  await page.context().close();

  // Error
  page = await newPage(vp, lang, { chatError: true });
  await page.goto(BASE + "/chat", { waitUntil: "networkidle" });
  await page.fill(".chat-input", lang === "ar" ? "ما هو الصوم؟" : "What is fasting?");
  await page.click(".chat-submit");
  await page.waitForTimeout(800);
  await shot(page, `${pre}-07-chat-error`);
  await page.context().close();

  // Seeded conversations
  const seedList = Object.entries(seeds);
  for (const [key, c] of seedList) {
    page = await newPage(vp, lang, { convs: Object.fromEntries(seedList.map(([k, v]) => [v.id, v])) });
    await page.goto(`${BASE}/chat?chat=${c.id}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".interactive-answer");
    await scrollChatTo(page, "top");
    await shot(page, `${pre}-08-chat-${key}-top`);
    await scrollChatTo(page, "bottom");
    await shot(page, `${pre}-09-chat-${key}-bottom`);
    if (key === "long") await axe(page, `${pre}-chat-long`);
    if (key === "table") {
      await axe(page, `${pre}-chat-table`);
      if (isMobile) {
        report.overflow[`${pre}-table-inner`] = await page.evaluate(() => {
          const w = document.querySelector(".answer-table-wrap");
          return w ? { scrollW: w.scrollWidth, clientW: w.clientWidth } : null;
        });
      }
    }
    if (key === "long" && isMobile) {
      await page.click(".navbar-sidebar-toggle");
      await shot(page, `${pre}-10-chat-sidebar-open`);
    }
    await page.context().close();
  }

  // Catechism tab
  page = await newPage(vp, lang, {});
  await page.goto(BASE + "/chat#catechism", { waitUntil: "networkidle" });
  await shot(page, `${pre}-11-catechism`);
  await page.click(".catechism-topic-summary >> nth=0");
  await shot(page, `${pre}-12-catechism-expanded`);
  await page.context().close();

  // Saints
  page = await newPage(vp, lang, { saintDelay: 2500 });
  await page.goto(BASE + "/chat#saints", { waitUntil: "networkidle" });
  await shot(page, `${pre}-13-saints-list`);
  await axe(page, `${pre}-saints`);
  await page.fill(".saints-search-input", lang === "ar" ? "موسى" : "Moses");
  await page.waitForTimeout(800);
  await shot(page, `${pre}-14-saints-search`);
  await page.click(".saints-list-item >> nth=1");
  await page.waitForTimeout(400);
  await shot(page, `${pre}-15-saint-detail-loading`);
  await page.waitForSelector(".saint-detail-answer", { timeout: 10000 });
  await shot(page, `${pre}-16-saint-detail`);
  await page.context().close();

  // Credits, contact, 404
  for (const [slug, url] of [["17-credits", "/credits"], ["18-contact", "/contact"], ["19-404", "/does-not-exist"]]) {
    page = await newPage(vp, lang, {});
    await page.goto(BASE + url, { waitUntil: "networkidle" });
    await shot(page, `${pre}-${slug}`);
    if (slug !== "17-credits" || !isMobile) await shot(page, `${pre}-${slug}-full`, { full: true });
    await axe(page, `${pre}-${slug.slice(3)}`);
    await page.context().close();
  }

  // Keyboard focus visibility (desktop only): tab through the home page
  if (!isMobile && lang === "en") {
    page = await newPage(vp, lang, {});
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    for (let i = 0; i < 4; i++) await page.keyboard.press("Tab");
    await shot(page, `${pre}-20-keyboard-focus`);
    report.focusOrder = [];
    for (let i = 0; i < 14; i++) {
      report.focusOrder.push(await page.evaluate(() => { const a = document.activeElement; return `${a.tagName}.${a.className} "${(a.getAttribute("aria-label") || a.textContent || "").trim().slice(0, 30)}"`; }));
      await page.keyboard.press("Tab");
    }
    await page.context().close();

    page = await newPage(vp, lang, {}, "dark");
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    await shot(page, `${pre}-21-dark-scheme-home`);
    await page.context().close();
  }
}

browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
try {
  for (const vp of ["desktop", "mobile"]) for (const lang of ["en", "ar"]) {
    console.log("capturing", vp, lang);
    await run(vp, lang);
  }
} finally {
  fs.writeFileSync(path.join(OUT, "_report.json"), JSON.stringify(report, null, 1));
  await browser.close();
}
