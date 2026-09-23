/** The Server-Sent Events parser (GEN-007). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { SseParser, formatSseEvent, type SseEvent } from "./sse.ts";

function parse(chunks: (string | Uint8Array)[], end = true) {
  const events: SseEvent[] = [];
  const parser = new SseParser((event) => events.push(event));
  for (const chunk of chunks) parser.push(chunk);
  if (end) parser.end();
  return events;
}

describe("SSE parser", () => {
  test("named events with JSON data, as the backend sends them", () => {
    const body = formatSseEvent("delta", { t: "Prayer " }) + formatSseEvent("done", { answer: "Prayer is…" });
    assert.deepEqual(parse([body]), [
      { event: "delta", data: '{"t":"Prayer "}' },
      { event: "done", data: '{"answer":"Prayer is…"}' },
    ]);
  });

  test("an event split across chunks at every possible point is still one event", () => {
    const body = formatSseEvent("delta", { t: "a\nb" }) + formatSseEvent("delta", { t: "c" });
    for (let cut = 1; cut < body.length; cut += 1) {
      const events = parse([body.slice(0, cut), body.slice(cut)]);
      assert.deepEqual(events.map((e) => JSON.parse(e.data).t), ["a\nb", "c"], `cut at ${cut}`);
    }
  });

  test("a multi-byte character split between two byte chunks is decoded whole (Arabic)", () => {
    const bytes = new TextEncoder().encode(formatSseEvent("delta", { t: "الصلاة" }));
    const events = parse([bytes.slice(0, 27), bytes.slice(27)]);
    assert.equal(JSON.parse(events[0].data).t, "الصلاة");
  });

  test("CRLF and CR line endings, comments, multi-line data and the default event name", () => {
    const events = parse([": keep-alive\r\nevent: delta\r\ndata: one\r", "\ndata: two\r\n\r\ndata: plain\r\r"]);
    assert.deepEqual(events, [
      { event: "delta", data: "one\ntwo" },
      { event: "message", data: "plain" },
    ]);
  });

  test("nothing is emitted before the blank line, and end() flushes a final event without one", () => {
    assert.deepEqual(parse(["event: done\ndata: {}\n"], false), []);
    assert.deepEqual(parse(["event: done\ndata: {}"]), [{ event: "done", data: "{}" }]);
  });
});
