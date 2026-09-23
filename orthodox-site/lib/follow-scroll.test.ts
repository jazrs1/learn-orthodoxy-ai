/** Auto-scroll while an answer streams (UI-026). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { FOLLOW_THRESHOLD_PX, distanceFromBottom, nextFollowing } from "./follow-scroll.ts";

// A 600 px tall list scrolled inside a 400 px window: the bottom is at scrollTop 200.
const at = (scrollTop: number, scrollHeight = 600) => ({ scrollTop, scrollHeight, clientHeight: 400 });

describe("follow the bottom while streaming", () => {
  test("distance from the bottom", () => {
    assert.equal(distanceFromBottom(at(200)), 0);
    assert.equal(distanceFromBottom(at(50)), 150);
  });

  test("scrolling up away from the bottom stops following", () => {
    assert.equal(nextFollowing(true, 200, at(120)), false);
  });

  test("a small step up near the bottom keeps the current choice", () => {
    // Still following if nothing said otherwise…
    assert.equal(nextFollowing(true, 200, at(200 - FOLLOW_THRESHOLD_PX)), true);
    // …but once upward input (wheel, touch, keys) has stopped following, the first small
    // animated step of that scroll must not turn it back on.
    assert.equal(nextFollowing(false, 200, at(190)), false);
  });

  test("coming back down to the bottom resumes following", () => {
    assert.equal(nextFollowing(false, 100, at(190)), true);
    assert.equal(nextFollowing(false, 100, at(200)), true);
  });

  test("scrolling down but not yet to the bottom leaves the choice as it was", () => {
    assert.equal(nextFollowing(false, 50, at(100)), false);
    // Our own scroll to the (then) bottom, or a smooth scroll to the question, only moves down.
    assert.equal(nextFollowing(true, 50, at(100, 900)), true);
  });

  test("content growing below doesn't stop following (there is no scroll event; the next one moves down)", () => {
    assert.equal(nextFollowing(true, 200, at(500, 900)), true);
  });
});
