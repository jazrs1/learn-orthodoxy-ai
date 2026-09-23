// Namesake menu check (RET-010) in a real browser, English and Arabic: the question shows the menu
// (menus captured from the local v2 backend), the menu message has no drop cap, a chip click sends
// the entry's ID (the request body the page posts to /api/chat is recorded), and the sourced answer
// keeps its drop cap (left-to-right only). Every /api/* call is mocked: no backend, database or
// OpenAI. BASE: http://localhost:3217 (see README step 1).
//   CHROME_BIN=/path/to/chrome node saint-menu.mjs ../saint-menu
import { chromium } from "playwright";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const now = new Date().toISOString();

const CASES = {
  en: {
    locale: "en-US",
    question: "search saint: St. Athanasius",
    menu: {
      answer: "I found multiple saints matching 'St. Athanasius'. Choose one option below.",
      options: [
        "St. Athanasius the Apostolic, the 20th Pope of Alexandria",
        "St. Athanasius (The martyr, vol. 1, p. 269)",
        "St. Athanasius, the Saint (vol. 1, p. 269)",
        "St. Athanasius II, the 28th Pope of Alexandria",
        "St. Athanasius III, the 76th Pope of Alexandria",
        "St. Athanasius, Bishop of Qus",
        "St. Athanasius, the Bishop",
      ],
      optionIds: [
        "athanasius-the-apostolic-the-20th-pope-of-alexandria",
        "athanasius",
        "athanasius-the-saint",
        "athanasius-ii-the-28th-pope-of-alexandria",
        "athanasius-iii-the-76th-pope-of-alexandria",
        "athanasius-bishop-of-qus",
        "athanasius-the-bishop",
      ],
    },
    choose: "St. Athanasius (The martyr, vol. 1, p. 269)",
    answer: {
      content: "St. Athanasius the martyr was a Christian put to death for his faith [1].",
      sources: [{ source_type: "pdf", pdf: "saints1.pdf", page: 280, page_end: 280, pages: "269", n: 1,
        entry: "St. Athanasius", chunk_id: "v2:sts1:saint:athanasius:c1", work: "Encyclopedia of the Saints and Fathers of the Church",
        label: "Encyclopedia of the Saints and Fathers of the Church, Vol. 1 — St. Athanasius, p. 269" }],
    },
  },
  ar: {
    locale: "ar-EG",
    question: "من هو القديس أثناسيوس؟",
    menu: {
      answer: "وجدت أكثر من قديس يطابق 'القديس أثناسيوس'. اختر واحدًا من الخيارات أدناه.",
      options: [
        "أثناسيوس الرسولي البابا العشرون", "أثناسيوس الشهيد", "أثناسيوس القديس", "أثناسيوس أسقف قوص",
        "أثناسيوس الأسقف الشهيد", "أثناسيوس الثالث البابا السادس والسبعون", "أثناسيوس الثاني البابا الثامن والعشرون",
      ],
      optionIds: [
        "athanasius-the-apostolic-the-20th-pope-of-alexandria", "athanasius", "athanasius-the-saint", "athanasius-bishop-of-qus",
        "athanasius-the-bishop", "athanasius-iii-the-76th-pope-of-alexandria", "athanasius-ii-the-28th-pope-of-alexandria",
      ],
    },
    choose: "أثناسيوس الشهيد",
    answer: {
      content: "القديس أثناسيوس الشهيد استشهد من أجل إيمانه [1].",
      sources: [{ source_type: "pdf", pdf: "full saints arabic.pdf", page: 40, pages: "37", n: 1, entry: "أثناسيوس الشهيد",
        chunk_id: "v2:ar-sts:e1760:c1", work: "قاموس آباء الكنيسة وقديسيها", label: "قاموس آباء الكنيسة وقديسيها — أثناسيوس الشهيد، ص 37" }],
    },
  },
};

// The drop cap as the browser draws it: ::first-letter of the message's first paragraph.
const dropCap = (locator) =>
  locator.evaluate((el) => {
    const p = el.querySelector(":scope > p");
    if (!p) return null;
    const letter = getComputedStyle(p, "::first-letter");
    return {
      plainClass: el.classList.contains("is-plain"),
      float: letter.float,
      initialLetter: letter.getPropertyValue("initial-letter") || letter.getPropertyValue("-webkit-initial-letter"),
      letterFontSize: letter.fontSize,
      paragraphFontSize: getComputedStyle(p).fontSize,
    };
  });

const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
const report = {};
for (const [language, fx] of Object.entries(CASES)) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: fx.locale });
  await ctx.addCookies([{ name: "lo_lang", value: language, url: BASE }]);
  const page = await ctx.newPage();
  const conversation = { id: "c-new", title: fx.question, createdAt: now, updatedAt: now, messages: [] };
  const chatBodies = [];
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/api/conversations" && req.method() === "GET") return json({ conversations: [] });
    if (path === "/api/conversations" && req.method() === "POST") return json({ conversation: { id: "c-new", title: fx.question, createdAt: now, updatedAt: now } });
    if (path.startsWith("/api/conversations/")) return json({ conversation });
    if (path === "/api/chat") {
      const body = JSON.parse(req.postData() || "{}");
      chatBodies.push(body);
      const n = conversation.messages.length;
      const user = { id: `u${n}`, role: "user", content: body.displayQuestion || body.question };
      // What /api/chat returns after saving the turn: the menu with its IDs, or the chosen entry's answer.
      const assistant = body.saintId
        ? { id: `a${n}`, role: "assistant", entities: [], options: [], optionIds: [], ...fx.answer }
        : { id: `a${n}`, role: "assistant", content: fx.menu.answer, entities: [], sources: [], options: fx.menu.options, optionIds: fx.menu.optionIds };
      conversation.messages.push(user, assistant);
      return json({ conversation: { id: "c-new", title: fx.question, createdAt: now, updatedAt: now }, userMessage: user, assistantMessage: assistant });
    }
    return json({ saints: [], total: 0 });
  });

  await page.goto(BASE + "/chat", { waitUntil: "load" });
  await page.waitForTimeout(800);
  await page.fill(".chat-input", fx.question);
  await page.keyboard.press("Enter");
  await page.locator(".message-option-chip").first().waitFor({ timeout: 10000 });
  const chips = await page.locator(".message-option-chip").allInnerTexts();
  const menuMessage = page.locator(".interactive-answer").last();
  const menuDropCap = await dropCap(menuMessage);
  await page.screenshot({ path: `${OUT}/menu-${language}.png`, fullPage: true });

  await page.locator(".message-option-chip", { hasText: fx.choose }).first().click();
  await page.locator(".answer-sources").first().waitFor({ timeout: 10000 });
  const answerDropCap = await dropCap(page.locator(".interactive-answer").last());
  await page.screenshot({ path: `${OUT}/answer-${language}.png`, fullPage: true });

  report[language] = { chips, menuDropCap, choiceRequest: chatBodies[1] || null, answerDropCap };
  await ctx.close();
}
await browser.close();
fs.writeFileSync(`${OUT}/saint-menu-report.json`, JSON.stringify(report, null, 1));
console.log(JSON.stringify(report, null, 1));
