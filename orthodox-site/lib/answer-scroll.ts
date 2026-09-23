// Scrolling around a new answer (UI-028). When a question is sent, the list scrolls once so the
// question sits near the top, and then leaves the scroll position alone while the answer streams
// in below it: the reader reads from the beginning at their own pace. A spacer after the last
// message makes room for that first scroll when the answer is still short; it shrinks as the
// answer grows, so the page height (and the reader's place) never jumps. A small "↓" button
// appears while the end of the text is below the view, and scrolls to it once when pressed.
//
// All positions are in the scrolled content's coordinates (0 = top of the list's content).

/** Space kept above the question when it is scrolled to the top (phones use less). */
export const ANCHOR_MARGIN_PX = { wide: 96, narrow: 72 };

/** The end of the text counts as "in view" within this distance of the bottom edge. */
export const JUMP_THRESHOLD_PX = 48;

/** The scrollTop that puts the question `margin` px below the top of the view. */
export function anchorScrollTop(anchorTop: number, margin: number) {
  return Math.max(0, anchorTop - margin);
}

/**
 * The spacer height that lets the question reach the top of the view: the content must reach at
 * least one view height below the question's scroll position. `contentEnd` is where the messages
 * end (the spacer's own top).
 */
export function spacerHeight({
  anchorTop,
  contentEnd,
  clientHeight,
  margin,
}: {
  anchorTop: number;
  contentEnd: number;
  clientHeight: number;
  margin: number;
}) {
  return Math.max(0, Math.ceil(anchorScrollTop(anchorTop, margin) + clientHeight - contentEnd));
}

/** Whether the end of the text is below the view, so the "↓" button is worth showing. */
export function textBelowView({
  scrollTop,
  clientHeight,
  contentEnd,
}: {
  scrollTop: number;
  clientHeight: number;
  contentEnd: number;
}) {
  return contentEnd - (scrollTop + clientHeight) > JUMP_THRESHOLD_PX;
}

/** The scrollTop that brings the end of the text to the bottom of the view. */
export function latestTextScrollTop({ contentEnd, clientHeight }: { contentEnd: number; clientHeight: number }) {
  return Math.max(0, contentEnd - clientHeight);
}

/** Keys that scroll the list: the reader taking over from the first scroll. */
export const SCROLL_KEYS = new Set(["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "]);
