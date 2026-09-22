/**
 * Read access to the generated calendar and the saints file (CAL-004). Import this from server
 * code only: the two JSON files are ~250 KB together, and pages send the browser just the days
 * they show (see view.ts).
 */

import calendarJson from "./data/calendar-2026-2027.json" with { type: "json" };
import saintsJson from "./data/saints.katameros.json" with { type: "json" };
import { BANNER_SAINT_ORDER } from "./config.ts";
import { addDays, daysInGregorianMonth, isIsoDate, isoFromParts } from "./dates.ts";
import type { CalendarData, CalendarDay, Commemoration, CopticDateParts, SaintsData } from "./types.ts";

const calendar = calendarJson as CalendarData;
const saints = saintsJson as SaintsData;
const byDate = new Map(calendar.days.map((day) => [day.date, day]));

export const CALENDAR_START = calendar.meta.start;
export const CALENDAR_END = calendar.meta.end;
export const SAINTS_SOURCE = saints.source;

export function isInCalendar(iso: string): boolean {
  return isIsoDate(iso) && iso >= CALENDAR_START && iso <= CALENDAR_END;
}

export function calendarDay(iso: string): CalendarDay | undefined {
  return byDate.get(iso);
}

/** Every day of a Gregorian month that the calendar covers. */
export function monthOfDays(year: number, month: number): CalendarDay[] {
  const days: CalendarDay[] = [];
  for (let day = 1; day <= daysInGregorianMonth(year, month); day++) {
    const found = byDate.get(isoFromParts(year, month, day));
    if (found) days.push(found);
  }
  return days;
}

/** The nearest covered date: before the range → first day, after it → last day. */
export function clampToCalendar(iso: string): string {
  if (iso < CALENDAR_START) return CALENDAR_START;
  if (iso > CALENDAR_END) return CALENDAR_END;
  return iso;
}

export function nextDay(iso: string): string {
  return addDays(iso, 1);
}

/**
 * The synaxarium entries for a Coptic day, without the feasts the calendar already lists.
 * Saints come first, then monthly commemorations and events; within the saints the order is
 * BANNER_SAINT_ORDER (the source's own order by default).
 */
export function commemorationsFor(coptic: CopticDateParts): Commemoration[] {
  const entries = (saints.days[`${coptic.month}-${coptic.day}`] ?? []).filter((entry) => entry.kind !== "feast");
  const rank = (entry: Commemoration) => {
    const group = entry.kind === "saint" ? 0 : entry.kind === "monthly" ? 1 : 2;
    const linked = BANNER_SAINT_ORDER === "linked-first" && entry.kind === "saint" && !entry.index ? 1 : 0;
    return group * 2 + linked;
  };
  return entries
    .map((entry, position) => ({ entry, position }))
    .sort((a, b) => rank(a.entry) - rank(b.entry) || a.position - b.position)
    .map(({ entry }) => entry);
}
