/**
 * One Gregorian month of the calendar page, prepared on the server (CAL-006): the days as
 * DayViews, bilingual labels, and the neighbouring months. Only this goes to the browser.
 */

import { CALENDAR_END, CALENDAR_START, clampToCalendar, monthOfDays } from "./calendar.ts";
import { copticMonthName } from "./coptic-months.ts";
import { isIsoDate } from "./dates.ts";
import { arabicDigits, dayView, type Bilingual, type DayView } from "./view.ts";

export type MonthOption = { value: string; label: Bilingual };

export type MonthView = {
  /** "2026-09". */
  month: string;
  label: Bilingual;
  /** The Coptic months the Gregorian month spans: "Thout – Paopi 1743". */
  coptic: Bilingual;
  /** 0 = Sunday: blank cells before the 1st. */
  leadingBlanks: number;
  days: DayView[];
  previous: string | null;
  next: string | null;
};

const monthFormat = {
  en: new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }),
  ar: new Intl.DateTimeFormat("ar-EG", { month: "long", year: "numeric", timeZone: "UTC" }),
};

function monthLabel(month: string): Bilingual {
  const instant = new Date(`${month}-01T00:00:00Z`);
  return { en: monthFormat.en.format(instant), ar: monthFormat.ar.format(instant) };
}

function shiftMonth(month: string, by: number): string {
  const [year, m] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year, m - 1 + by, 1));
  return date.toISOString().slice(0, 7);
}

const FIRST_MONTH = CALENDAR_START.slice(0, 7);
const LAST_MONTH = CALENDAR_END.slice(0, 7);

export function monthOptions(): MonthOption[] {
  const options: MonthOption[] = [];
  for (let month = FIRST_MONTH; month <= LAST_MONTH; month = shiftMonth(month, 1)) {
    options.push({ value: month, label: monthLabel(month) });
  }
  return options;
}

function copticSpan(days: DayView[]): Bilingual {
  const first = days[0].coptic;
  const last = days[days.length - 1].coptic;
  const name = (month: number, language: "en" | "ar") => copticMonthName(month, language);
  const year = (value: number, language: "en" | "ar") => (language === "ar" ? arabicDigits(value) : String(value));
  const span = (language: "en" | "ar") =>
    first.year === last.year
      ? `${name(first.month, language)} – ${name(last.month, language)} ${year(first.year, language)}`
      : `${name(first.month, language)} ${year(first.year, language)} – ${name(last.month, language)} ${year(last.year, language)}`;
  return { en: span("en"), ar: span("ar") };
}

export function monthView(month: string): MonthView {
  const [year, m] = month.split("-").map(Number);
  const days = monthOfDays(year, m)
    .map((day) => dayView(day.date))
    .filter((day): day is DayView => day !== null);
  return {
    month,
    label: monthLabel(month),
    coptic: copticSpan(days),
    leadingBlanks: days[0].weekday,
    days,
    previous: month > FIRST_MONTH ? shiftMonth(month, -1) : null,
    next: month < LAST_MONTH ? shiftMonth(month, 1) : null,
  };
}

/**
 * The day the page opens on, from ?d=YYYY-MM-DD or ?m=YYYY-MM, else the server's date; always
 * inside the calendar. `requested` says whether the URL chose it, `clamped` whether it had to move.
 */
export function resolveSelection(params: { d?: string; m?: string }, serverToday: string) {
  if (params.d && isIsoDate(params.d)) {
    const date = clampToCalendar(params.d);
    return { date, requested: true, clamped: date !== params.d };
  }
  if (params.m && /^\d{4}-\d{2}$/.test(params.m) && isIsoDate(`${params.m}-01`)) {
    const date = clampToCalendar(`${params.m}-01`);
    return { date, requested: true, clamped: date.slice(0, 7) !== params.m };
  }
  return { date: clampToCalendar(serverToday), requested: false, clamped: false };
}
