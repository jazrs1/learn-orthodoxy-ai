// Auto-scroll while an answer streams (UI-026). The view follows the bottom until the reader
// scrolls up, then stays where they put it (a "Jump to latest" button is shown) until they come
// back down to the bottom. Growing content never fires a scroll event, and our own scrolling
// only ever moves down, so upward movement is the reader's.
//
// Upward input (wheel, touch, keys) stops following at once: a wheel or trackpad scrolls in small
// animated steps, and waiting for the view to leave the bottom zone would let the next piece of
// text pull it back down every time.

export type ScrollMetrics = { scrollTop: number; scrollHeight: number; clientHeight: number };

/** Within this distance of the bottom counts as "at the bottom". */
export const FOLLOW_THRESHOLD_PX = 48;

/** Keys that scroll the list up. */
export const SCROLL_UP_KEYS = new Set(["ArrowUp", "PageUp", "Home"]);

export function distanceFromBottom({ scrollTop, scrollHeight, clientHeight }: ScrollMetrics) {
  return Math.max(0, scrollHeight - clientHeight - scrollTop);
}

/** Whether to keep following after a scroll event, given the scroll position before it. */
export function nextFollowing(following: boolean, previousScrollTop: number, metrics: ScrollMetrics) {
  const atBottom = distanceFromBottom(metrics) <= FOLLOW_THRESHOLD_PX;
  if (metrics.scrollTop < previousScrollTop) return atBottom ? following : false;
  return atBottom ? true : following;
}
