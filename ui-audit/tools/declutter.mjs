// Home page declutter check (UI-017…): the home page in English and Arabic at 1440 and 390 px,
// the first screen and the full page, the past-chats drawer open, and the chat page (whose
// sidebar stays), with axe on every state. Every /api/* call is mocked, with past chats that
// repeat a title; no backend, database or OpenAI. BASE: http://localhost:3217 (README step 1).
//   CHROME_BIN=/path/to/chrome node declutter.mjs ../declutter/after
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const now = new Date().toISOString();
const TITLES = {
  en: ["What is prayer?", "What is prayer?", "Who was St. Moses the Black?", "What is prayer?", "Why do we fast?", "Who was St. Moses the Black?"],
  ar: ["ما هي الصلاة؟", "ما هي الصلاة؟", "من هو الأنبا موسى الأسود؟", "لماذا نصوم؟", "ما هي الصلاة؟"],
};
const VIEWPORTS = [["1440", { width: 1440, height: 900 }], ["390", { width: 390, height: 844 }]];

const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
const report = {};

async function axe(page) {
  const result = await new AxeBuilder({ page }).analyze();
  return result.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, target: v.nodes[0]?.target }));
}

for (const language of ["en", "ar"]) {
  for (const [width, viewport] of VIEWPORTS) {
    const ctx = await browser.newContext({ viewport, locale: language === "ar" ? "ar-EG" : "en-US" });
    await ctx.addCookies([{ name: "lo_lang", value: language, url: BASE }]);
    const page = await ctx.newPage();
    await page.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
      if (path === "/api/conversations") {
        return json({ conversations: TITLES[language].map((title, i) => ({ id: `c${i}`, title, createdAt: now, updatedAt: now })) });
      }
      if (path.startsWith("/api/conversations/")) return json({ error: "not found" }, 404);
      return json({ saints: [], total: 0, suggestions: [] });
    });
    const tag = `${language}-${width}`;
    const states = {};

    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/home-${tag}-first-screen.png` });
    await page.screenshot({ path: `${OUT}/home-${tag}-full.png`, fullPage: true });
    states.home = {
      axe: await axe(page),
      order: await page.evaluate(() =>
        [...document.querySelectorAll("main > * , main .home-content > *, footer")]
          .map((el) => el.className || el.tagName.toLowerCase())
          .filter((name) => typeof name === "string" && name.trim())
          .slice(0, 14)
      ),
      navLinks: await page.locator(".site-header a, .site-header button").allInnerTexts(),
      sidebarVisible: await page.locator(".chat-sidebar").first().isVisible(),
      horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1),
    };

    // Past chats as a drawer: the new button, else the header menu's event.
    const button = page.locator(".past-chats-button");
    if (await button.count()) await button.first().click();
    else await page.evaluate(() => window.dispatchEvent(new CustomEvent("chat:openSidebar")));
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/home-${tag}-drawer.png` });
    states.drawer = {
      axe: await axe(page),
      titles: await page.locator(".chat-sidebar-mobile-open .chat-sidebar-item-title").allInnerTexts(),
    };

    if (width === "1440") {
      await page.goto(BASE + "/chat", { waitUntil: "networkidle" });
      await page.waitForTimeout(600);
      await page.screenshot({ path: `${OUT}/chat-${tag}.png` });
      states.chat = {
        axe: await axe(page),
        sidebarVisible: await page.locator(".chat-sidebar").first().isVisible(),
        titles: await page.locator(".chat-sidebar-item-title").allInnerTexts(),
      };
    }
    report[tag] = states;
    await ctx.close();
  }
}
await browser.close();
fs.writeFileSync(`${OUT}/declutter-report.json`, JSON.stringify(report, null, 1));
const violations = Object.entries(report).flatMap(([tag, states]) =>
  Object.entries(states).flatMap(([state, s]) => s.axe.map((v) => `${tag} ${state}: ${v.id} (${v.impact}, ${v.nodes})`))
);
console.log(violations.length ? violations.join("\n") : "axe: 0 violations in every state");
