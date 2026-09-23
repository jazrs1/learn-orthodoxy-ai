// Where the time goes between a click and the first word on screen (RET-018), hop by hop, for a new
// chat's first question and a follow-up. The page's fetch is wrapped to time each request's start,
// response headers and first streamed chunk; the site's routes and the backend each write a timing
// line with a wall-clock start (RET-018), joined here by request ID. Run everything on one machine,
// so the clocks agree. Costs one answer per question (real backend).
//
//   ROUTE_LOG=next.log BACKEND_LOG=backend.log BASE_URL=http://localhost:3217 \
//     node hops.mjs ../hops/after [label]
import { chromium } from "playwright";
import fs from "node:fs";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const OUT = process.argv[2];
const LABEL = process.argv[3] || "run";
fs.mkdirSync(OUT, { recursive: true });

// A new chat and a follow-up each; distinct questions, so no cache answers them.
const RUNS = [
  { language: "en", questions: ["What is prayer?", "How often should we pray?"] },
  { language: "en", questions: ["What does the Church teach about fasting?", "Why is it joined with prayer?"] },
  { language: "ar", questions: ["ما هي التوبة؟", "وكيف نمارسها؟"] },
];
if (process.env.EXAMPLE_TWICE) {
  // A home-page example question asked in two new chats: generated, then from the cache (RET-017).
  RUNS.push({ language: "en", questions: ["Why is prayer essential in the Coptic Orthodox life?"] });
  RUNS.push({ language: "en", questions: ["Why is prayer essential in the Coptic Orthodox life?"] });
}

const INSTRUMENT = () => {
  window.__hops = [];
  const originalFetch = window.fetch.bind(window);
  const epoch = () => performance.timeOrigin + performance.now();
  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const entry = { path: new URL(url, location.href).pathname, method: init.method || "GET", start: epoch() };
    window.__hops.push(entry);
    const response = await originalFetch(input, init);
    entry.headers = epoch();
    entry.status = response.status;
    entry.serverTiming = response.headers.get("server-timing");
    entry.requestId = response.headers.get("x-request-id");
    if (response.body && (response.headers.get("content-type") || "").includes("event-stream")) {
      const reader = response.body.getReader();
      const body = new ReadableStream({
        async pull(controller) {
          const { value, done } = await reader.read();
          if (done) {
            entry.end = epoch();
            controller.close();
            return;
          }
          entry.firstChunk ??= epoch();
          controller.enqueue(value);
        },
        cancel(reason) {
          return reader.cancel(reason);
        },
      });
      return new Response(body, { status: response.status, headers: response.headers });
    }
    return response;
  };
  // When the first streamed word is painted, and when the finished answer's sources appear.
  new MutationObserver(() => {
    const turn = window.__turn;
    if (!turn) return;
    if (!turn.firstWord && document.querySelector("[aria-busy=true] .stream-word")) turn.firstWord = epoch();
    const sources = document.querySelectorAll(".answer-sources").length;
    if (!turn.done && sources > turn.sourcesBefore) turn.done = epoch();
  }).observe(document, { childList: true, subtree: true });
};

function jsonLines(path, event) {
  if (!path || !fs.existsSync(path)) return [];
  return fs
    .readFileSync(path, "utf8")
    .split(/\r?\n/)
    .map((line) => line.slice(line.indexOf("{")))
    .filter((line) => line.startsWith("{") && line.includes(`"${event}"`))
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
const turns = [];
for (const run of RUNS) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addCookies([{ name: "lo_lang", value: run.language, url: BASE }]);
  await context.addInitScript(INSTRUMENT);
  const page = await context.newPage();
  await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });
  for (const [index, question] of run.questions.entries()) {
    await page.locator(".chat-input").fill(question);
    await page.evaluate(() => {
      window.__hops.length = 0;
      window.__turn = { click: performance.timeOrigin + performance.now(), sourcesBefore: document.querySelectorAll(".answer-sources").length };
    });
    await page.locator(".chat-submit").click();
    await page.waitForFunction(() => window.__turn.done, null, { timeout: 90000 });
    await page.waitForTimeout(300);
    const measured = await page.evaluate(() => ({ turn: window.__turn, hops: window.__hops }));
    turns.push({ language: run.language, kind: index === 0 ? "new chat" : "follow-up", question, ...measured });
  }
  await context.close();
}
await browser.close();

// Join with the servers' timing lines.
await new Promise((resolve) => setTimeout(resolve, 1500)); // the last lines reach the logs
const routeLines = jsonLines(process.env.ROUTE_LOG, "route_timing");
const backendLines = jsonLines(process.env.BACKEND_LOG, "request");
const r = (value) => (value == null || Number.isNaN(value) ? null : Math.round(value));

const report = turns.map((t) => {
  const create = t.hops.find((h) => h.path === "/api/conversations" && h.method === "POST");
  const stream = t.hops.find((h) => h.path === "/api/chat/stream");
  const createLine = create
    ? routeLines.filter((l) => l.route === "conversation_create").sort((a, b) => Math.abs(a.start_epoch_ms - create.start) - Math.abs(b.start_epoch_ms - create.start))[0]
    : null;
  const route = routeLines.find((l) => l.route === "chat_stream" && l.request_id === stream?.requestId);
  const backend = backendLines.find((l) => l.request_id === stream?.requestId);
  const stages = backend?.stages_ms || {};
  const routeStart = route?.start_epoch_ms;
  const backendRequestAt = routeStart != null ? routeStart + (route.ms.backend_request ?? 0) : null;
  const backendHeadersAt = backendRequestAt != null ? backendRequestAt + route.ms.backend_headers : null;
  const backendFirstToken = backend?.ttft_ms != null ? backend.start_epoch_ms + backend.ttft_ms : null;
  const routeFirstDelta = route?.ms.first_delta != null ? routeStart + route.ms.first_delta : null;
  return {
    language: t.language,
    kind: t.kind,
    question: t.question,
    request_id: stream?.requestId,
    click_to_first_word_ms: r(t.turn.firstWord - t.turn.click),
    click_to_done_ms: r(t.turn.done - t.turn.click),
    hops_ms: {
      "page: click → first request": r((create || stream).start - t.turn.click),
      "conversation create (browser round trip)": create ? r(create.headers - create.start) : null,
      "  of which the database insert": createLine ? createLine.ms.db : null,
      "page: conversation created → stream request": create ? r(stream.start - create.headers) : null,
      "browser → site route starts": r(routeStart - stream?.start),
      "history read (database)": route?.ms.history ?? null,
      "site → backend request arrives": r(backend?.start_epoch_ms - backendRequestAt),
      "backend: analysis": stages.analysis ?? null,
      "backend: retrieval": stages.retrieval ?? null,
      "  of which embedding": stages.embedding ?? null,
      "backend: until headers sent": backend?.headers_ms ?? null,
      "backend: headers → model's first token": r(backend?.ttft_ms - backend?.headers_ms),
      "backend headers → site receives them": r(backendHeadersAt - (backend?.start_epoch_ms + backend?.headers_ms)),
      "backend first token → site relays it": r(routeFirstDelta - backendFirstToken),
      "site relays → browser receives first chunk": r(stream?.firstChunk - routeFirstDelta),
      "first chunk → first word painted": r(t.turn.firstWord - stream?.firstChunk),
      "save (database, after the answer)": route?.ms.save ?? null,
    },
    backend: backend
      ? {
          ttft_ms: backend.ttft_ms,
          total_ms: backend.total_ms,
          analysis_cached: backend.analysis_cached ?? false,
          embedding_prefetch: backend.embedding_prefetch ?? null,
          answer_cache: backend.answer_cache ?? null,
          prompt_tokens: backend.prompt_tokens,
          completion_tokens: backend.completion_tokens,
          analysis_tokens: backend.analysis_tokens,
        }
      : null,
  };
});

fs.writeFileSync(`${OUT}/hops-${LABEL}.json`, JSON.stringify(report, null, 1));
for (const row of report) {
  console.log(`\n${row.language} ${row.kind}: "${row.question}"  first word ${row.click_to_first_word_ms} ms, done ${row.click_to_done_ms} ms`);
  for (const [name, ms] of Object.entries(row.hops_ms)) if (ms != null) console.log(`   ${String(ms).padStart(6)}  ${name}`);
  if (row.backend) console.log(`   backend: ${JSON.stringify(row.backend)}`);
}
