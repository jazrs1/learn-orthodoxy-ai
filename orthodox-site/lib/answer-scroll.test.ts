/** Scrolling around a new answer (UI-028). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  JUMP_THRESHOLD_PX,
  anchorScrollTop,
  latestTextScrollTop,
  spacerHeight,
  textBelowView,
} from "./answer-scroll.ts";

// A 700 px tall view; the new question starts 1,000 px into the conversation.
const view = { clientHeight: 700, margin: 96 };

describe("the question is scrolled near the top once", () => {
  test("its scroll position leaves the margin above it", () => {
    assert.equal(anchorScrollTop(1000, 96), 904);
    assert.equal(anchorScrollTop(40, 96), 0);
  });

  test("a short answer gets a spacer so the question can reach the top", () => {
    // Question at 1,000, messages end at 1,150 (question + "Searching the books…").
    assert.equal(spacerHeight({ anchorTop: 1000, contentEnd: 1150, ...view }), 454);
    // With the spacer, the furthest the list can scroll is exactly the question's position.
    assert.equal(1150 + 454 - view.clientHeight, anchorScrollTop(1000, view.margin));
  });

  test("as the answer grows the spacer shrinks by the same amount, so the page height stays put", () => {
    const before = 1150 + spacerHeight({ anchorTop: 1000, contentEnd: 1150, ...view });
    const after = 1400 + spacerHeight({ anchorTop: 1000, contentEnd: 1400, ...view });
    assert.equal(after, before);
  });

  test("an answer longer than the view needs no spacer", () => {
    assert.equal(spacerHeight({ anchorTop: 1000, contentEnd: 2200, ...view }), 0);
  });

  test("a phone keyboard closing makes the view taller: the spacer grows so the question can stay at the top", () => {
    const withKeyboard = spacerHeight({ anchorTop: 1000, contentEnd: 1150, clientHeight: 420, margin: 72 });
    const withoutKeyboard = spacerHeight({ anchorTop: 1000, contentEnd: 1150, clientHeight: 700, margin: 72 });
    assert.equal(withoutKeyboard - withKeyboard, 280);
  });
});

describe("the ↓ button", () => {
  test("shows while the end of the text is below the view, and not within the threshold", () => {
    assert.equal(textBelowView({ scrollTop: 904, clientHeight: 700, contentEnd: 2200 }), true);
    assert.equal(textBelowView({ scrollTop: 904, clientHeight: 700, contentEnd: 1604 + JUMP_THRESHOLD_PX }), false);
    assert.equal(textBelowView({ scrollTop: 904, clientHeight: 700, contentEnd: 1400 }), false);
  });

  test("scrolls to put the end of the text at the bottom of the view", () => {
    assert.equal(latestTextScrollTop({ contentEnd: 2200, clientHeight: 700 }), 1500);
    assert.equal(latestTextScrollTop({ contentEnd: 300, clientHeight: 700 }), 0);
  });
});
