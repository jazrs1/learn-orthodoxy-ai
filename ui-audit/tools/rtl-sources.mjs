// RTL citation check (ING-007): renders a real v2 Arabic answer (AR-14, eval run 20260923-000307) with
// its sources, every /api/* call mocked, and checks each page range reads in order ("118–119", not
// "119–118") and the labels are right-to-left. BASE: http://localhost:3217 (see README step 1).
//   CHROME_BIN=/path/to/chrome node rtl-sources.mjs ../rtl
import { chromium } from "playwright";
import fs from "node:fs";
const BASE = "http://localhost:3217";
const OUT = process.argv[2];
const FX = JSON.parse(fs.readFileSync(new URL("./rtl-sources.fixture.json", import.meta.url), "utf-8"));
fs.mkdirSync(OUT, { recursive: true });
const now = new Date().toISOString();
const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
const results = {};
for (const [name, viewport] of [["desktop", { width: 1440, height: 900 }], ["mobile", { width: 390, height: 844 }]]) {
  const ctx = await browser.newContext({ viewport, locale: "ar-EG" });
  await ctx.addCookies([{ name: "lo_lang", value: "ar", url: BASE }]);
  const page = await ctx.newPage();
  const convs = {};
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname;
    const json = (b, s = 200) => route.fulfill({ status: s, contentType: "application/json", body: JSON.stringify(b) });
    if (p === "/api/conversations" && req.method() === "GET") return json({ conversations: [] });
    if (p === "/api/conversations" && req.method() === "POST") { convs.c = { id: "c-new", title: FX.question, createdAt: now, updatedAt: now, messages: [] }; return json({ conversation: { id: "c-new", title: FX.question, createdAt: now, updatedAt: now } }); }
    if (p.startsWith("/api/conversations/")) return convs.c ? json({ conversation: convs.c }) : json({ error: "nf" }, 404);
    if (p === "/api/chat") {
      const u = { id: "u1", role: "user", content: FX.question };
      const a = { id: "a1", role: "assistant", content: FX.answer, entities: [], options: FX.options || [], sources: FX.sources };
      convs.c = convs.c || { id: "c-new", title: FX.question, createdAt: now, updatedAt: now, messages: [] };
      convs.c.messages.push(u, a);
      return json({ conversation: { id: "c-new", title: FX.question, createdAt: now, updatedAt: now }, userMessage: u, assistantMessage: a });
    }
    return json({ saints: [], total: 0 });
  });
  await page.goto(BASE + "/chat", { waitUntil: "load" });
  await page.waitForTimeout(800);
  await page.fill(".chat-input", FX.question);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(1500);
  // expand the sources list if it is collapsed
  const toggle = page.locator("button", { hasText: /المصادر|مصادر/ }).first();
  if (await toggle.count()) { await toggle.click().catch(() => {}); await page.waitForTimeout(400); }
  await page.screenshot({ path: `${OUT}/ar-answer-${name}.png`, fullPage: true });
  const item = page.locator("[id^=src-]").nth(1);
  if (await item.count()) {
    await item.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const box = await item.evaluate((el) => { const s = (el.closest("section, aside, ol, ul") || el.parentElement).getBoundingClientRect(); return { x: s.x, y: s.y, width: s.width, height: Math.min(s.height, 700) }; });
    await page.screenshot({ path: `${OUT}/ar-sources-${name}.png`, clip: box });
    const para = page.locator(".answer-body p, article p").first();
    await para.scrollIntoViewIfNeeded().catch(() => {});
  }
  results[name] = await page.evaluate(() => {
    const items = [...document.querySelectorAll("[id^=src-]")].map((el) => ({
      text: el.innerText.replace(/\s+/g, " ").trim(),
      direction: getComputedStyle(el).direction,
      unicodeBidi: getComputedStyle(el).unicodeBidi,
      dirAttr: el.closest("[dir]")?.getAttribute("dir"),
    }));
    const markers = [...document.querySelectorAll("a[href^='#src-'], button[aria-label]")].map((el) => el.getAttribute("aria-label") || el.title).filter((t) => t && /ص|المجلد|قاموس|كاتيكيزم/.test(t)).slice(0, 4);
    // on-screen order of the two page numbers in each range ("118–119"): the first must be left of the second
    const order = [...document.querySelectorAll("[id^=src-]")].flatMap((el) => {
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      const out = [];
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const m = n.textContent.match(/(\d+)–(\d+)/);
        if (!m) continue;
        const at = (i, len) => { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + len); return r.getBoundingClientRect().x; };
        const i1 = n.textContent.indexOf(m[1]); const i2 = n.textContent.indexOf(m[2], i1 + m[1].length);
        out.push({ range: m[0], firstLeftOfSecond: at(i1, m[1].length) < at(i2, m[2].length) });
      }
      return out;
    });
    return { htmlDir: document.documentElement.dir, lang: document.documentElement.lang, items, markers, order };
  });
  await ctx.close();
}
await browser.close();
fs.writeFileSync(`${OUT}/rtl-report.json`, JSON.stringify(results, null, 1));
console.log(JSON.stringify(results, null, 1));
