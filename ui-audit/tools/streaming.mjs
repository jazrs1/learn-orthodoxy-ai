// Streamed answers in the chat page (UI-026, GEN-007/008), in a real browser against a running site.
// Writes screenshots, videos (.webm), axe results and report.json to the output folder.
//
//   MODE=fake  (free) against fake_stream_backend.py: a table never shown half-built, Stop (kept on
//              screen, not saved), Jump to latest, an error mid-stream with Retry, the fallback to
//              /api/chat, reduced motion; axe on each state.
//   MODE=real  (about $0.02 with gpt-4.1-mini) against the real backend on v2: an English answer at
//              1440, an Arabic one at 390, a table, a refusal and a saint menu. Time to first token and
//              total time as the reader sees them, the same for /api/chat, and axe. Stops at the first
//              failed request, so a quota or key error costs nothing more.
//
// Site: production build on BASE_URL (default http://localhost:3217) with POSTGRES_URL pointing at
// pg-server.mjs, ORTHODOX_API_URL at the backend and ORTHODOX_API_KEY matching it (README).
//   MODE=fake CHROME_BIN=… node streaming.mjs ../streaming/fake
//   MODE=real CHROME_BIN=… node streaming.mjs ../streaming/real
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const MODE = process.env.MODE || "fake";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
const report = { mode: MODE, base: BASE, at: new Date().toISOString(), axe: {} };
const VIEWPORTS = { 1440: { width: 1440, height: 900 }, 390: { width: 390, height: 844 } };

async function open(width = 1440, language = "en", { video = false, reducedMotion = "no-preference" } = {}) {
  const ctx = await browser.newContext({
    viewport: VIEWPORTS[width],
    locale: language === "ar" ? "ar-EG" : "en-US",
    reducedMotion,
    ...(video ? { recordVideo: { dir: OUT, size: VIEWPORTS[width] } } : {}),
  });
  await ctx.addCookies([{ name: "lo_lang", value: language, url: BASE }]);
  const page = await ctx.newPage();
  await page.goto(BASE + "/chat", { waitUntil: "networkidle" });
  return page;
}

async function axe(page, name) {
  const result = await new AxeBuilder({ page }).analyze();
  report.axe[name] = result.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, target: v.nodes[0]?.target }));
}

async function ask(page, question) {
  await page.locator(".chat-input").fill(question);
  const started = Date.now();
  await page.locator(".chat-submit").click();
  return started;
}

const DONE = ".answer-sources, .message-option-chip, .chat-alert, [data-message-role=assistant] .is-plain";

/** One streamed answer: time until something of the answer shows (its first words, or the table
 * note when it opens with a table) and to the finished answer; screenshots, axe, video. */
async function streamedAnswer(name, question, width, language) {
  const page = await open(width, language, { video: true });
  const started = await ask(page, question);
  const firstShown = await page
    .waitForSelector(`.stream-word, .stream-table-note, ${DONE}`, { timeout: 30000 })
    .then(() => Date.now() - started, () => null);
  const shownWhileStreaming = await page.locator("[aria-busy=true]").count();
  if (firstShown !== null && shownWhileStreaming) {
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}/${name}-${width}-streaming.png` });
    await axe(page, `${name}-${width}-streaming`);
  }
  await page.waitForSelector(DONE, { timeout: 90000 });
  const total = Date.now() - started;
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}-${width}-done.png` });
  await axe(page, `${name}-${width}-done`);
  const result = {
    question,
    width,
    firstShownMs: shownWhileStreaming ? firstShown : null,
    totalMs: total,
    error: await page.locator(".chat-alert").count() ? await page.locator(".chat-alert-text").innerText() : null,
    sources: await page.locator(".answer-source").count(),
    tables: await page.locator(".answer-table-wrap table").count(),
    announced: (await page.locator("[role=status]").first().innerText()).slice(0, 160),
  };
  const video = page.video();
  await page.context().close();
  if (video) fs.renameSync(await video.path(), `${OUT}/${name}-${width}.webm`);
  return result;
}

/** A request through /api/chat/stream and through /api/chat from inside the page: total time each. */
async function bothRoutes(page, body) {
  return page.evaluate(async (payload) => {
    const time = async (path) => {
      const started = performance.now();
      const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const type = response.headers.get("content-type") || "";
      const text = await response.text();
      const data = type.includes("json") ? JSON.parse(text) : null;
      return {
        status: response.status,
        type: type.split(";")[0],
        ms: Math.round(performance.now() - started),
        answer: data?.assistantMessage?.content?.slice(0, 100) ?? null,
        options: data?.assistantMessage?.options?.length ?? 0,
      };
    };
    return { stream: await time("/api/chat/stream"), chat: await time("/api/chat") };
  }, body);
}

function stopIfFailed(label, result) {
  const failed = result.error || [result.stream, result.chat].some((r) => r && r.status !== 200);
  if (failed) {
    report.stoppedAt = label;
    fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
    console.error(`Stopped: ${label} failed`, JSON.stringify(result));
    process.exit(1);
  }
}

// CASES=table,menu … runs only those (real mode).
const CASES = (process.env.CASES || "english,arabic,table,refusal,menu,nostream").split(",");

if (MODE === "real") {
  if (CASES.includes("english")) {
    report.english = await streamedAnswer("english", "What is prayer?", 1440, "en");
    stopIfFailed("english", report.english);
  }
  if (CASES.includes("arabic")) {
    report.arabic = await streamedAnswer("arabic", "ما هي الصلاة؟", 390, "ar");
    stopIfFailed("arabic", report.arabic);
  }
  if (CASES.includes("table")) {
    report.table = await streamedAnswer("table", "Make a table of the fasts of the Coptic Orthodox Church and how long each one lasts.", 1440, "en");
    stopIfFailed("table", report.table);
  }

  const page = await open(1440, "en");
  if (CASES.includes("refusal")) {
    report.refusal = await bothRoutes(page, { question: "Who won the 2018 FIFA World Cup?", mode: "chat", language: "en" });
    stopIfFailed("refusal", report.refusal);
  }
  if (CASES.includes("menu")) {
    report.menu = await bothRoutes(page, { question: "search saint: St. Gregory", mode: "saints", language: "en" });
    stopIfFailed("menu", report.menu);
  }
  // The same English question without streaming: the total time a reader waits today.
  if (CASES.includes("nostream")) report.englishWithoutStreaming = await page.evaluate(async () => {
    const started = performance.now();
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "What is prayer?", mode: "chat", language: "en" }),
    });
    const data = await response.json();
    return { status: response.status, ms: Math.round(performance.now() - started), chars: data.assistantMessage?.content?.length };
  });
  await page.context().close();
} else {
  // 1. A table is never on screen half-built.
  {
    const page = await open(1440, "en");
    await ask(page, "the fasts as a table");
    const samples = [];
    for (const started = Date.now(); Date.now() - started < 30000; ) {
      const state = await page.evaluate(() => ({
        note: !!document.querySelector(".stream-table-note"),
        rows: document.querySelectorAll("[aria-busy] table tr").length,
        done: !!document.querySelector(".answer-sources"),
      }));
      samples.push(state);
      if (state.note && !report.tableHeldShot) {
        await page.screenshot({ path: `${OUT}/table-held-1440.png` });
        await axe(page, "table-held-1440");
        report.tableHeldShot = true;
      }
      if (state.done) break;
      await page.waitForTimeout(40);
    }
    await page.screenshot({ path: `${OUT}/table-done-1440.png` });
    const finalRows = await page.locator(".answer-table-wrap table tr").count();
    report.table = {
      samples: samples.length,
      heldSamples: samples.filter((s) => s.note).length,
      // Shown while streaming with fewer rows than the finished table (the finished table may show
      // while the text after it still arrives).
      partialTableSamples: samples.filter((s) => s.rows > 0 && s.rows < finalRows).length,
      completeTableWhileStreamingSamples: samples.filter((s) => s.rows === finalRows).length,
      finalRows,
    };
    await page.context().close();
  }

  // 2. Stop mid-answer: the text stays, marked stopped; nothing is saved.
  {
    const page = await open(1440, "en");
    await ask(page, "What is prayer?");
    await page.waitForSelector(".stream-word");
    await page.waitForTimeout(1200);
    await axe(page, "streaming-with-stop-1440");
    await page.locator(".chat-stop").click();
    await page.waitForSelector(".answer-stopped-note");
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/stopped-1440.png` });
    await axe(page, "stopped-1440");
    const conversations = await page.evaluate(async () => (await (await fetch("/api/conversations")).json()).conversations);
    const savedMessages = await page.evaluate(
      async (id) => (await (await fetch(`/api/conversations/${id}`)).json()).conversation.messages.length,
      conversations[0].id
    );
    report.stop = {
      shownChars: (await page.locator("[data-message-role=assistant]").last().innerText()).length,
      announced: await page.locator("[role=status]").first().innerText(),
      sendButtonBack: (await page.locator(".chat-submit:not(.chat-stop)").count()) === 1,
      savedMessages,
    };
    await page.context().close();
  }

  // 3. Jump to latest (phone): scrolling up mid-answer holds the view; the button brings it back.
  for (const language of ["en", "ar"]) {
    const page = await open(390, language);
    await ask(page, language === "ar" ? "ما هي الصلاة؟" : "What is prayer?");
    // Once the answer is well past the bottom of the view, so there is somewhere to scroll up to.
    await page.waitForFunction(() => {
      const el = document.querySelector(".chat-messages");
      return el.scrollHeight > el.clientHeight + 400;
    });
    const box = await page.locator(".chat-messages").boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -600);
    await page.waitForTimeout(400);
    const scrollTop = () => page.evaluate(() => document.querySelector(".chat-messages").scrollTop);
    const before = await scrollTop();
    await page.waitForTimeout(1200);
    const after = await scrollTop();
    const jumpVisible = await page.locator(".jump-to-latest").isVisible();
    if (!jumpVisible) {
      console.error(`jump (${language}): not shown; still streaming: ${await page.locator("[aria-busy=true]").count()}`);
    }
    await page.screenshot({ path: `${OUT}/jump-${language}-390.png` });
    await axe(page, `jump-${language}-390`);
    await page.locator(".jump-to-latest").click();
    await page.waitForTimeout(1500);
    report[`jump-${language}`] = {
      viewHeldWhileScrolledUp: Math.abs(after - before) < 2,
      jumpVisible,
      distanceFromBottomAfterJump: await page.evaluate(() => {
        const el = document.querySelector(".chat-messages");
        return el.scrollHeight - el.clientHeight - el.scrollTop;
      }),
      jumpHiddenAfter: (await page.locator(".jump-to-latest").count()) === 0,
    };
    await page.waitForSelector(".answer-sources", { timeout: 60000 });
    await page.context().close();
  }

  // 4. An error mid-answer: the partial text goes, the alert offers Retry.
  {
    const page = await open(1440, "en");
    await ask(page, "this will fail");
    await page.waitForSelector(".chat-alert", { timeout: 30000 });
    await page.screenshot({ path: `${OUT}/error-1440.png` });
    await axe(page, "error-1440");
    report.error = {
      alert: await page.locator(".chat-alert-text").innerText(),
      retryButtons: await page.locator(".chat-alert button").count(),
      partialLeft: await page.locator("[aria-busy], .stream-word").count(),
    };
    await page.context().close();
  }

  // 5. The stream route missing: the same question through /api/chat.
  {
    const page = await open(1440, "en");
    const calls = [];
    page.on("request", (r) => r.url().includes("/api/chat") && calls.push(new URL(r.url()).pathname));
    await page.route("**/api/chat/stream", (route) => route.fulfill({ status: 404, body: "not found" }));
    await ask(page, "What is prayer?");
    await page.waitForSelector(".answer-sources", { timeout: 30000 });
    report.fallback = { calls, sources: await page.locator(".answer-source").count() };
    await page.context().close();
  }

  // 6. Reduced motion: words appear without animation.
  {
    const page = await open(1440, "en", { reducedMotion: "reduce" });
    await ask(page, "What is prayer?");
    await page.waitForSelector(".stream-word");
    report.reducedMotion = {
      animationName: await page.locator(".stream-word").last().evaluate((el) => getComputedStyle(el).animationName),
    };
    await page.waitForSelector(".answer-sources", { timeout: 60000 });
    await page.context().close();
  }
}

// axe opens a blank helper page per scan, which a recording context films too.
for (const file of fs.readdirSync(OUT)) if (/^page@.*\.webm$/.test(file)) fs.rmSync(`${OUT}/${file}`);
report.axeViolations = Object.values(report.axe).reduce((sum, list) => sum + list.length, 0);
fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 1));
await browser.close();
