"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ANCHOR_MARGIN_PX,
  SCROLL_KEYS,
  anchorScrollTop,
  latestTextScrollTop,
  spacerHeight,
  textBelowView,
} from "../lib/answer-scroll";

/** Where the messages end (the spacer's top), in the list's content coordinates. */
function contentEnd(element: HTMLElement, spacer: HTMLElement) {
  return spacer.getBoundingClientRect().top - element.getBoundingClientRect().top + element.scrollTop;
}

/**
 * Scrolling around a new answer (UI-028; the rules are in lib/answer-scroll.ts).
 *
 * `anchorId` is the message just sent (the question, or the answer when the question is hidden);
 * when it changes, the list scrolls once to put it near the top. Until the reader scrolls, a
 * resize (a phone keyboard closing after send, a rotation) puts it back there; the growing answer
 * never moves the view. Put `listRef` on the scrolling list (it may be unmounted and mounted
 * again, as when the reader switches tabs) and `<div ref={spacerRef} aria-hidden />` after the
 * last message.
 */
export function useAnswerScroll(anchorId: string, content: unknown) {
  const [element, listRef] = useState<HTMLElement | null>(null);
  const spacerRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);
  // The question stays where the first scroll put it until the reader scrolls themselves.
  const pinned = useRef(false);
  const placedAnchor = useRef("");

  /** Positions in content coordinates, the spacer sized, and (when asked) the question placed. */
  const layout = useCallback(
    (place: "no" | "smooth" | "instant") => {
      const spacer = spacerRef.current;
      if (!element || !spacer) return;
      const top = element.getBoundingClientRect().top - element.scrollTop;
      const anchor = anchorId
        ? element.querySelector<HTMLElement>(`[data-message-id="${CSS.escape(anchorId)}"]`)
        : null;
      const margin = window.matchMedia("(max-width: 720px)").matches ? ANCHOR_MARGIN_PX.narrow : ANCHOR_MARGIN_PX.wide;
      const end = contentEnd(element, spacer);
      if (anchor) {
        const anchorTop = anchor.getBoundingClientRect().top - top;
        spacer.style.height = `${spacerHeight({ anchorTop, contentEnd: end, clientHeight: element.clientHeight, margin })}px`;
        if (place !== "no") {
          const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          element.scrollTo({
            top: anchorScrollTop(anchorTop, margin),
            behavior: place === "smooth" && !reduceMotion ? "smooth" : "instant",
          });
        }
      } else {
        spacer.style.height = "0px";
      }
      setShowJump(textBelowView({ scrollTop: element.scrollTop, clientHeight: element.clientHeight, contentEnd: end }));
    },
    [anchorId, element]
  );

  // New text, a new question, or messages swapped for their saved copies: size the spacer (in the
  // same frame, so the page height doesn't jump) and place a new question once.
  useLayoutEffect(() => {
    const isNew = Boolean(anchorId) && anchorId !== placedAnchor.current;
    if (isNew) pinned.current = true;
    placedAnchor.current = anchorId;
    layout(isNew ? "smooth" : "no");
  }, [anchorId, content, layout]);

  useEffect(() => {
    if (!element) return;
    const onScroll = () => {
      const spacer = spacerRef.current;
      if (!spacer) return;
      const end = contentEnd(element, spacer);
      setShowJump(textBelowView({ scrollTop: element.scrollTop, clientHeight: element.clientHeight, contentEnd: end }));
    };
    const release = () => {
      pinned.current = false;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (SCROLL_KEYS.has(event.key)) release();
    };
    // A resize while the question is still where we put it: put it back (keyboard, rotation).
    const onResize = () => {
      if (pinned.current) layout("instant");
      else layout("no");
    };
    const observer = new ResizeObserver(onResize);
    observer.observe(element);
    window.visualViewport?.addEventListener("resize", onResize);
    element.addEventListener("scroll", onScroll, { passive: true });
    element.addEventListener("wheel", release, { passive: true });
    element.addEventListener("touchmove", release, { passive: true });
    element.addEventListener("keydown", onKeyDown);
    return () => {
      observer.disconnect();
      window.visualViewport?.removeEventListener("resize", onResize);
      element.removeEventListener("scroll", onScroll);
      element.removeEventListener("wheel", release);
      element.removeEventListener("touchmove", release);
      element.removeEventListener("keydown", onKeyDown);
    };
  }, [element, layout]);

  /** Once to the end of the text; the view is not followed afterwards. */
  const jumpToLatest = () => {
    const spacer = spacerRef.current;
    if (!element || !spacer) return;
    pinned.current = false;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    element.scrollTo({
      top: latestTextScrollTop({ contentEnd: contentEnd(element, spacer), clientHeight: element.clientHeight }),
      behavior: reduceMotion ? "auto" : "smooth",
    });
  };

  return { listRef, spacerRef, showJump, jumpToLatest };
}
