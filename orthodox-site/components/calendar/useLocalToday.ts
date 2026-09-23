"use client";

import { useCallback, useSyncExternalStore } from "react";
import { localCalendarDate } from "../../lib/calendar/today";

/** Re-read the clock every minute so an open page rolls over to the next day. */
function subscribeToClock(onChange: () => void) {
  const timer = window.setInterval(onChange, 60_000);
  return () => window.clearInterval(timer);
}

/**
 * The visitor's calendar date (CAL-004). During hydration it returns the server's guess, so the
 * first render matches the HTML; right after, the visitor's own date.
 */
export function useLocalToday(serverToday: string): string {
  const getSnapshot = useCallback(() => localCalendarDate(new Date()), []);
  const getServerSnapshot = useCallback(() => serverToday, [serverToday]);
  return useSyncExternalStore(subscribeToClock, getSnapshot, getServerSnapshot);
}
