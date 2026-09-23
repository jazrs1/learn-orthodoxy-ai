/** Past chats listed once per title (UI-020). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { titleKey, uniqueByTitle } from "./chat-sessions.ts";

const chats = [
  { id: "c0", title: "What is prayer?" },
  { id: "c1", title: "What is prayer?" },
  { id: "c2", title: "Who was St. Moses the Black?" },
  { id: "c3", title: "what is prayer" },
  { id: "c4", title: "Why do we fast?" },
  { id: "c5", title: "Who was St. Moses the Black?" },
];

describe("past chats by title", () => {
  test("keeps the newest chat of each title, in order", () => {
    assert.deepEqual(uniqueByTitle(chats).map((c) => c.id), ["c0", "c2", "c4"]);
  });

  test("shows the open chat even when it is an older one of its title", () => {
    assert.deepEqual(uniqueByTitle(chats, "c3").map((c) => c.id), ["c3", "c2", "c4"]);
  });

  test("Arabic titles and the Arabic question mark", () => {
    const arabic = [{ id: "a", title: "ما هي الصلاة؟" }, { id: "b", title: "ما هي  الصلاة" }, { id: "c", title: "لماذا نصوم؟" }];
    assert.deepEqual(uniqueByTitle(arabic).map((c) => c.id), ["a", "c"]);
    assert.equal(titleKey(" ما هي الصلاة؟ "), "ما هي الصلاة");
  });

  test("untitled chats are not merged", () => {
    assert.equal(uniqueByTitle([{ id: "x", title: "" }, { id: "y", title: "" }]).length, 2);
  });
});
