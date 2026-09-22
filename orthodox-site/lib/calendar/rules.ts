/**
 * The Coptic calendar rules that produce lib/calendar/data/calendar-2026-2027.json (CAL-002).
 * Build-time only: imported by scripts/calendar/generate-calendar.ts and the tests, never by the
 * site, so coptic-calendar stays a dev dependency.
 *
 * coptic-calendar supplies the Gregorian ↔ Coptic conversion and the Alexandrian computus.
 * Everything else is spelled out here so it can be read and checked against the Church's tables.
 */

import { CopticDate } from "coptic-calendar";
import { getEasterForCopticYear } from "coptic-calendar/plugins/occasions";
import { addDays, diffDays, isoToJdn, jdnToIso, weekday } from "./dates.ts";
import { compareObservances, type ObservanceId } from "./observances.ts";
import type { CalendarDay, CopticDateParts } from "./types.ts";

/** Always a plain "YYYY-MM-DD" string: coptic-calendar reads a Date's UTC fields (CAL-001). */
export function toCoptic(iso: string): CopticDateParts {
  const date = CopticDate.from(iso);
  return { year: date.year, month: date.month, day: date.day };
}

export function fromCoptic(year: number, month: number, day: number): string {
  return jdnToIso(CopticDate.from({ year, month, day }).jdn);
}

/** Pascha (Resurrection Sunday) of a Gregorian year. The spring of year Y is in Coptic year Y − 284. */
export function paschaOf(gregorianYear: number): string {
  return jdnToIso(getEasterForCopticYear(gregorianYear - 284).jdn);
}

/** Fixed feasts on Coptic dates. The Nativity is handled separately (rule 4). */
const FIXED_FEASTS: Array<[month: number, day: number, id: ObservanceId]> = [
  [1, 1, "nayrouz"],
  // SUS lists the Feast of the Cross as three days, Thout 17–19.
  [1, 17, "feast-of-the-cross"],
  [1, 18, "feast-of-the-cross"],
  [1, 19, "feast-of-the-cross"],
  [5, 6, "circumcision"],
  [5, 11, "theophany"],
  [5, 13, "cana"],
  [6, 8, "presentation"],
  [7, 10, "appearance-of-the-cross"],
  [7, 29, "annunciation"],
  [8, 30, "st-mark"],
  [9, 24, "entry-into-egypt"],
  [11, 5, "apostles-feast"],
  [12, 13, "transfiguration"],
  [12, 16, "assumption"],
];

/** Days counted from Pascha. */
const PASCHA_DAYS: Array<[offset: number, id: ObservanceId]> = [
  [-66, "jonah-feast"],
  [-8, "lazarus-saturday"],
  [-7, "palm-sunday"],
  [-6, "holy-monday"],
  [-5, "holy-tuesday"],
  [-4, "holy-wednesday"],
  [-3, "covenant-thursday"],
  [-2, "good-friday"],
  [-1, "joyous-saturday"],
  [0, "resurrection"],
  [7, "thomas-sunday"],
  [39, "ascension"],
  [49, "pentecost"],
];

export const RULES = [
  "Rule 1: Great Lent runs from Pascha − 55 to Pascha − 9, the Friday before Lazarus Saturday; Lazarus Saturday to Holy Saturday is the Holy Week fast.",
  "Rule 2: Lazarus Saturday, the Monday, Tuesday and Wednesday of Holy Pascha, Covenant Thursday, Good Friday and Joyous Saturday are listed.",
  "Rule 3: the Annunciation (Paremhat 29) is not celebrated when it falls between Palm Sunday and Holy Saturday.",
  "Rule 4: the Nativity is kept on January 7; when Kiahk 29 falls on January 8 (the year after a Coptic leap year) both days are marked, and the Nativity Fast still ends on January 6.",
  "Wednesday and Friday are fast days, except in the Holy Fifty, from the Nativity to Theophany, on a major feast of the Lord, and inside a longer fast.",
];

export function buildDay(iso: string): CalendarDay {
  const coptic = toCoptic(iso);
  const year = Number(iso.slice(0, 4));
  const pascha = paschaOf(year);
  const fromPascha = diffDays(iso, pascha);

  const observances: ObservanceId[] = [];
  const suppressed: ObservanceId[] = [];

  for (const [month, day, id] of FIXED_FEASTS) {
    if (coptic.month === month && coptic.day === day) observances.push(id);
  }

  // Rule 4: January 7 always; Kiahk 29 as well when it falls on January 8.
  if (iso.slice(5) === "01-07" || (coptic.month === 4 && coptic.day === 29)) observances.push("nativity");

  for (const [offset, id] of PASCHA_DAYS) {
    if (fromPascha === offset) observances.push(id);
  }

  // Rule 3.
  const annunciationIndex = observances.indexOf("annunciation");
  if (annunciationIndex >= 0 && fromPascha >= -7 && fromPascha <= -1) {
    observances.splice(annunciationIndex, 1);
    suppressed.push("annunciation");
  }

  // Seasonal fasts (at most one applies on any day).
  let fast: ObservanceId | null = null;
  if (fromPascha >= -69 && fromPascha <= -67) fast = "jonah-fast";
  else if (fromPascha >= -55 && fromPascha <= -9) fast = "great-lent"; // Rule 1
  else if (fromPascha >= -8 && fromPascha <= -1) fast = "holy-week-fast";
  // The Apostles' Fast ends on Epip 4, the eve of the Feast of the Apostles, in Pascha's Coptic year.
  else if (fromPascha >= 50 && iso <= fromCoptic(year - 284, 11, 4)) fast = "apostles-fast";
  else if (coptic.month === 12 && coptic.day <= 15) fast = "st-mary-fast";
  else {
    // Hathor 16 up to January 6, the eve of the Nativity (rule 4).
    const fastStart = fromCoptic(coptic.year, 3, 16);
    const fastEnd = `${Number(fastStart.slice(0, 4)) + 1}-01-06`;
    if (iso >= fastStart && iso <= fastEnd) fast = "nativity-fast";
  }

  let fastFree: ObservanceId | null = null;
  if (fromPascha >= 0 && fromPascha <= 49) fastFree = "holy-fifty";
  else if (iso >= `${year}-01-07` && iso <= fromCoptic(toCoptic(`${year}-01-07`).year, 5, 11)) {
    fastFree = "nativity-to-theophany";
  }

  const day = weekday(iso);
  const onMajorFeast = observances.some((id) =>
    ["annunciation", "nativity", "theophany", "palm-sunday", "resurrection", "ascension", "pentecost"].includes(id)
  );
  if (!fast && !fastFree && !onMajorFeast && (day === 3 || day === 5)) fast = "wednesday-friday";

  observances.sort(compareObservances);
  return { date: iso, coptic, observances, fast, fastFree, suppressed };
}

export function buildRange(start: string, end: string): CalendarDay[] {
  const days: CalendarDay[] = [];
  for (let iso = start; iso <= end; iso = addDays(iso, 1)) days.push(buildDay(iso));
  return days;
}

/** Julian Day Number helper kept for tests of the conversion edge cases. */
export function jdnOf(iso: string): number {
  return isoToJdn(iso);
}
