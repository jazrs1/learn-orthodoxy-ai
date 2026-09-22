/**
 * Plain calendar-date arithmetic on "YYYY-MM-DD" strings, done in UTC so the result never depends
 * on the machine's or the visitor's time zone (CAL-001: both libraries shift a day when handed a
 * local Date). Nothing here reads the clock.
 */

const DAY_MS = 86_400_000;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isIsoDate(value: string): boolean {
  const match = ISO_DATE.exec(value);
  if (!match) return false;
  const [, y, m, d] = match.map(Number);
  const probe = new Date(Date.UTC(y, m - 1, d));
  return probe.getUTCFullYear() === y && probe.getUTCMonth() === m - 1 && probe.getUTCDate() === d;
}

/** Days since 1970-01-01 for an ISO date. */
export function isoToDayNumber(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
}

export function dayNumberToIso(dayNumber: number): string {
  return new Date(dayNumber * DAY_MS).toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
  return dayNumberToIso(isoToDayNumber(iso) + days);
}

export function diffDays(later: string, earlier: string): number {
  return isoToDayNumber(later) - isoToDayNumber(earlier);
}

/** 0 = Sunday … 6 = Saturday. */
export function weekday(iso: string): number {
  return new Date(isoToDayNumber(iso) * DAY_MS).getUTCDay();
}

export function isoFromParts(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** "2026-09" style month key. */
export function monthKey(iso: string): string {
  return iso.slice(0, 7);
}

export function daysInGregorianMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** Julian Day Number of an ISO date (noon-based integer, as coptic-calendar uses). */
export function isoToJdn(iso: string): number {
  return isoToDayNumber(iso) + 2_440_588;
}

export function jdnToIso(jdn: number): string {
  return dayNumberToIso(jdn - 2_440_588);
}
