/** Retrying a failed save (RET-021). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { withRetry } from "./retry.ts";

const noSleep = async () => undefined;

describe("withRetry", () => {
  test("a step that succeeds at once runs once", async () => {
    let calls = 0;
    assert.equal(await withRetry(async () => ++calls, { delaysMs: [10, 20], sleep: noSleep }), 1);
    assert.equal(calls, 1);
  });

  test("a step that fails twice then succeeds is retried with the given pauses", async () => {
    const pauses: number[] = [];
    let calls = 0;
    const result = await withRetry(
      async () => {
        calls += 1;
        if (calls < 3) throw new Error("Connection terminated unexpectedly");
        return "saved";
      },
      { delaysMs: [400, 1200], sleep: async (ms) => void pauses.push(ms) }
    );
    assert.equal(result, "saved");
    assert.deepEqual(pauses, [400, 1200]);
  });

  test("after the last attempt the error is thrown", async () => {
    let calls = 0;
    await assert.rejects(
      withRetry(async () => {
        calls += 1;
        throw new Error("down");
      }, { delaysMs: [1, 1], sleep: noSleep }),
      /down/
    );
    assert.equal(calls, 3);
  });

  test("an error that waiting can't cure fails at once", async () => {
    let calls = 0;
    await assert.rejects(
      withRetry(async () => {
        calls += 1;
        throw new Error("Set POSTGRES_URL");
      }, { delaysMs: [1, 1], sleep: noSleep, shouldRetry: (e) => !String(e).includes("POSTGRES_URL") })
    );
    assert.equal(calls, 1);
  });
});
