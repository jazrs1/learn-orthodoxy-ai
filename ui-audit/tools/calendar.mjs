// Calendar verification (CAL-007): screenshots, axe and a layout report for the Today strip and
// /calendar, in English and Arabic at 1440 and 390 px. Every /api/* call is mocked in the browser,
// so nothing reaches the backend, Postgres or OpenAI.
//   BASE_URL=http://localhost:3217 CHROME_BIN=/path/to/chrome node calendar.mjs ../calendar
// Lighthouse for /calendar: add ["calendar", "/calendar"] to PAGES in lighthouse.mjs, or run
//   PAGES=calendar node lighthouse.mjs ../calendar 2
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });

const SAINTS = { saints: ["St. George, the Capaducian"], total: 1 };

async function mock(page) {
  await page.route("**/api/**", (route) => {
    const { pathname } = new URL(route.request().url());
    const body = pathname === "/api/saints" ? SAINTS : { conversations: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

// [name, path, what to do before the capture]
const STATES = [
  ["home-today-strip", "/", null],
  ["calendar-this-month", "/calendar", null],
  ["calendar-holy-week-2026", "/calendar?d=2026-04-07", null],
  ["calendar-st-george-2027", "/calendar?d=2027-05-01", null],
  ["calendar-nativity-2027", "/calendar?d=2027-01-07", null],
  ["calendar-keyboard-focus", "/calendar?d=2026-09-29", async (page) => {
    await page.locator('[aria-selected="true"] button').focus();
    await page.keyboard.press("ArrowRight");
  }],
  ["calendar-out-of-range", "/calendar?d=2030-01-01", null],
];

const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
const report = [];
try {
  for (const language of ["en", "ar"]) {
    for (const width of [1440, 390]) {
      for (const [name, url, act] of STATES) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, timezoneId: "America/Toronto" });
        await context.addCookies([{ name: "lo_lang", value: language, url: BASE }]);
        const page = await context.newPage();
        const errors = [];
        page.on("console", (message) => message.type() === "error" && errors.push(message.text().slice(0, 200)));
        page.on("pageerror", (error) => errors.push(String(error).slice(0, 200)));
        await mock(page);
        await page.goto(BASE + url, { waitUntil: "load" });
        await page.waitForTimeout(1000);
        if (act) await act(page);
        const file = `${name}-${language}-${width}.png`;
        await page.screenshot({ path: path.join(OUT, file), fullPage: name !== "home-today-strip" });
        const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
        const layout = await page.evaluate(() => {
          const small = [...document.querySelectorAll("main a, main button, main select")]
            .filter((element) => {
              const box = element.getBoundingClientRect();
              const inline = getComputedStyle(element).display === "inline";
              return box.width > 0 && !inline && (box.height < 44 || box.width < 44);
            })
            .map((element) => `${element.className || element.tagName}: ${Math.round(element.getBoundingClientRect().width)}×${Math.round(element.getBoundingClientRect().height)}`);
          return { horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth, under44: [...new Set(small)] };
        });
        report.push({
          state: name,
          language,
          width,
          file,
          axeViolations: axe.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
          ...layout,
          consoleErrors: errors,
        });
        console.log(name, language, width, `axe ${axe.violations.length}`, layout.horizontalOverflow ? "OVERFLOW" : "", errors.length ? `errors ${errors.length}` : "");
        await context.close();
      }
    }
  }
} finally {
  fs.writeFileSync(path.join(OUT, "_calendar-report.json"), JSON.stringify(report, null, 1));
  await browser.close();
}
