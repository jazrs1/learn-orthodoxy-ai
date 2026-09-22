/**
 * "Today" from the visitor's own clock (CAL-004). The server cannot know the visitor's date, so
 * it renders the few dates that can be today somewhere on Earth, and a tiny inline script picks
 * the right one before the first paint; React then agrees with it after hydration.
 */

import { addDays, isoFromParts } from "./dates.ts";
import { DAY_BOUNDARY, SUNSET_APPROXIMATE_HOUR } from "./config.ts";

export type DayBoundary = "midnight" | "sunset";

/** The calendar date the visitor is living in, from their local clock. */
export function localCalendarDate(now: Date, boundary: DayBoundary = DAY_BOUNDARY): string {
  const civil = isoFromParts(now.getFullYear(), now.getMonth() + 1, now.getDate());
  return boundary === "sunset" && now.getHours() >= SUNSET_APPROXIMATE_HOUR ? addDays(civil, 1) : civil;
}

/**
 * Every date that is "today" for someone at the given instant: UTC−12 to UTC+14 spans three
 * civil dates, and a sunset boundary can push the latest one a day further.
 */
export function possibleTodays(now: Date, boundary: DayBoundary = DAY_BOUNDARY): string[] {
  const utc = now.toISOString().slice(0, 10);
  const days = [addDays(utc, -1), utc, addDays(utc, 1)];
  return boundary === "sunset" ? [...days, addDays(utc, 2)] : days;
}

/** The same rule as localCalendarDate, as a self-contained script for the inline pre-paint pick. */
export function localCalendarDateScript(boundary: DayBoundary = DAY_BOUNDARY): string {
  const sunset = boundary === "sunset" ? SUNSET_APPROXIMATE_HOUR : -1;
  return (
    `function(){var n=new Date();if(${sunset}>=0&&n.getHours()>=${sunset})n=new Date(n.getFullYear(),n.getMonth(),n.getDate()+1);` +
    `var p=function(v){return(v<10?"0":"")+v};return n.getFullYear()+"-"+p(n.getMonth()+1)+"-"+p(n.getDate())}`
  );
}
