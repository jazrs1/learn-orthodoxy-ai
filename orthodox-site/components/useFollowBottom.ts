"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { SCROLL_UP_KEYS, nextFollowing } from "../lib/follow-scroll";

/**
 * Keeps the bottom of `container` in view while `active` (an answer is on its way), until the
 * reader scrolls up; then `showJump` offers a way back, and reaching the bottom again resumes
 * following (UI-026). `content` changes whenever the text grows. When the answer completes,
 * the view follows once more, so its Sources list comes into view.
 */
export function useFollowBottom(container: RefObject<HTMLElement | null>, active: boolean, content: unknown) {
  const [following, setFollowingState] = useState(true);
  const followingRef = useRef(true);
  const lastScrollTop = useRef(0);
  const wasActive = useRef(false);

  // A new answer starts: follow again (adjusted while rendering, as React recommends for state
  // that follows a prop; the ref is reset in the layout effect below).
  const [previousActive, setPreviousActive] = useState(active);
  if (active !== previousActive) {
    setPreviousActive(active);
    if (active) setFollowingState(true);
  }

  const setFollowing = useCallback((value: boolean) => {
    if (followingRef.current === value) return;
    followingRef.current = value;
    setFollowingState(value);
  }, []);

  useEffect(() => {
    const element = container.current;
    if (!element || !active) return;
    lastScrollTop.current = element.scrollTop;
    let touchY = 0;
    const onScroll = () => {
      setFollowing(nextFollowing(followingRef.current, lastScrollTop.current, element));
      lastScrollTop.current = element.scrollTop;
    };
    // The reader moving up stops following before the scroll itself begins.
    const onWheel = (event: WheelEvent) => {
      if (event.deltaY < 0) setFollowing(false);
    };
    const onTouchStart = (event: TouchEvent) => {
      touchY = event.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (event: TouchEvent) => {
      if ((event.touches[0]?.clientY ?? 0) > touchY) setFollowing(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (SCROLL_UP_KEYS.has(event.key)) setFollowing(false);
    };
    element.addEventListener("scroll", onScroll, { passive: true });
    element.addEventListener("wheel", onWheel, { passive: true });
    element.addEventListener("touchstart", onTouchStart, { passive: true });
    element.addEventListener("touchmove", onTouchMove, { passive: true });
    element.addEventListener("keydown", onKeyDown);
    return () => {
      element.removeEventListener("scroll", onScroll);
      element.removeEventListener("wheel", onWheel);
      element.removeEventListener("touchstart", onTouchStart);
      element.removeEventListener("touchmove", onTouchMove);
      element.removeEventListener("keydown", onKeyDown);
    };
  }, [active, container, setFollowing]);

  // After the new text is laid out, before it is painted.
  useLayoutEffect(() => {
    const starting = active && !wasActive.current;
    const finishing = !active && wasActive.current;
    wasActive.current = active;
    if (starting) followingRef.current = true;
    const element = container.current;
    if (!element || !(active || finishing) || !followingRef.current) return;
    element.scrollTo({ top: element.scrollHeight, behavior: "instant" });
    lastScrollTop.current = element.scrollTop;
  }, [active, container, content]);

  const jumpToLatest = () => {
    const element = container.current;
    if (!element) return;
    setFollowing(true);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    element.scrollTo({ top: element.scrollHeight, behavior: reduceMotion ? "auto" : "smooth" });
  };

  return { showJump: active && !following, jumpToLatest };
}
