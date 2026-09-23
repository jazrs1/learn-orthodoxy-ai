// Saving answers (RET-021) in the browser: a new chat without a conversation request and its
// follow-up, Stop on a new chat, and a database that dies mid-answer (the answer stays, marked; the
// next question starts a new conversation). Scripted backend (fake_stream_backend.py) and the local
// database (pg-server.mjs on 5433, restarted by this script), site as in README step 1. Run from the
// folder holding pg-server.mjs and its node_modules:
//   MIGRATION=/path/to/orthodox-site/migrations/001_create_chat_tables.sql node save-failure.mjs ../save-failure
import { chromium } from "playwright";
import { execSync, spawn } from "node:child_process";
import fs from "node:fs";

const BASE = "http://localhost:3217";
const TOOLS = process.cwd();
const OUT = process.argv[2];
const MIGRATION = process.env.MIGRATION;
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const report = {};

async function open() {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const requests = [];
  page.on("request", (r) => {
    const path = new URL(r.url()).pathname;
    if (path.startsWith("/api/c")) requests.push({ path, method: r.method(), body: r.postDataJSON?.() ?? null });
  });
  await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });
  return { page, requests };
}
async function ask(page, question) {
  await page.locator(".chat-input").fill(question);
  await page.locator(".chat-submit").click();
}
const conversations = (page) => page.evaluate(async () => (await (await fetch("/api/conversations")).json()).conversations || []);

function killDb() {
  execSync(`powershell -Command "$p=(Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force }"`);
}
async function startDb() {
  const child = spawn("node", ["pg-server.mjs", MIGRATION], { cwd: TOOLS, detached: true, stdio: "ignore" });
  child.unref();
  for (let i = 0; i < 50; i += 1) {
    try {
      execSync(`powershell -Command "if (-not (Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue)) { exit 1 }"`);
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 200));
    }
  }
}

// 1. A new chat: no conversation request first; the answer, then the saved conversation.
{
  const { page, requests } = await open();
  await ask(page, "What is prayer?");
  await page.waitForSelector(".answer-sources", { timeout: 60000 });
  await page.waitForURL(/\?chat=/, { timeout: 10000 });
  const firstUrl = page.url();
  await ask(page, "Why do we pray?");
  await page.waitForSelector(".answer-sources >> nth=1", { timeout: 60000 });
  const streamBodies = requests.filter((r) => r.path === "/api/chat/stream").map((r) => r.body);
  const saved = await conversations(page);
  const detail = await page.evaluate(async (id) => (await (await fetch(`/api/conversations/${id}`)).json()).conversation, saved[0]?.id);
  report.newChat = {
    conversationCreateRequests: requests.filter((r) => r.path === "/api/conversations" && r.method === "POST").length,
    firstRequestHadConversationId: Boolean(streamBodies[0]?.conversationId),
    urlAfterFirstAnswer: firstUrl.replace(BASE, ""),
    followUpConversationId: streamBodies[1]?.conversationId ?? null,
    sameConversation: streamBodies[1]?.conversationId === new URL(firstUrl).searchParams.get("chat"),
    conversationsSaved: saved.length,
    messagesSaved: detail?.messages?.length ?? 0,
    sidebarEntries: await page.locator(".chat-sidebar-session, .chat-sidebar a, .chat-sidebar button").allInnerTexts().then((t) => t.filter((x) => /prayer/i.test(x)).length),
  };
  await page.close();
}

// 2. Stop on a new chat's first question: nothing is saved, no empty conversation is left.
{
  const { page } = await open();
  await ask(page, "What does the Church teach about fasting?");
  await page.waitForSelector(".stream-word");
  await page.locator(".chat-stop").click();
  await page.waitForSelector(".answer-stopped-note");
  await page.waitForTimeout(800);
  report.stopNewChat = { conversationsSaved: (await conversations(page)).length, url: page.url().replace(BASE, "") };
  await page.close();
}

// 3. The database dies while the answer streams: the answer stays, marked; the next question
//    starts a new conversation instead of silently continuing one that doesn't exist.
{
  const { page, requests } = await open();
  await ask(page, "What is the Jesus Prayer?");
  await page.waitForSelector(".stream-word");
  killDb();
  const started = Date.now();
  await page.waitForSelector(".answer-sources", { timeout: 60000 });
  const sourcesAt = Date.now() - started;
  await page.waitForSelector(".answer-unsaved-note", { timeout: 20000 });
  const noteAt = Date.now() - started;
  await page.screenshot({ path: `${OUT}/unsaved-1440.png` });
  const stopWhileSaving = await page.locator(".chat-stop").count();
  const live = await page.locator("[role=status]").first().innerText();
  await startDb();
  await ask(page, "How often should we pray it?");
  try {
    await page.waitForSelector(".answer-sources >> nth=1", { timeout: 30000 });
    await page.screenshot({ path: `${OUT}/after-unsaved-1440.png` });
  } catch (error) {
    await page.screenshot({ path: `${OUT}/stuck.png` });
    console.log("STUCK", JSON.stringify(requests.slice(-3)), await page.locator(".chat-alert, .answer-unsaved-note, .typing-indicator").allInnerTexts());
    throw error;
  }
  await page.waitForURL(/\?chat=/, { timeout: 10000 });
  const bodies = requests.filter((r) => r.path === "/api/chat/stream").map((r) => r.body);
  report.dbDown = {
    sourcesShownDespiteDbDown: sourcesAt > 0,
    noteShown: true,
    msFromKillToNote: noteAt,
    liveRegionEndsWithNote: /couldn't be saved/.test(live),
    stopButtonAfterAnswer: stopWhileSaving,
    nextQuestionConversationId: bodies[1]?.conversationId ?? null,
    nextQuestionSaved: (await conversations(page)).length === 1,
  };
  await page.close();
}

fs.writeFileSync(`${OUT}/ret021.json`, JSON.stringify(report, null, 1));
console.log(JSON.stringify(report, null, 1));
await browser.close();
