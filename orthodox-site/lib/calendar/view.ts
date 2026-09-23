/**
 * What the calendar UI receives for one day: plain, serialisable, and already in both languages,
 * so switching language in the browser needs no new data (CAL-004). Built on the server.
 */

import { calendarDay, commemorationsFor } from "./calendar.ts";
import { copticMonthName } from "./coptic-months.ts";
import { weekday } from "./dates.ts";
import { OBSERVANCES, type ObservanceId, type ObservanceKind } from "./observances.ts";
import type { CommemorationKind } from "./types.ts";

export type Bilingual = { en: string; ar: string };

export type ObservanceView = { id: ObservanceId; kind: ObservanceKind; name: Bilingual };

export type CommemorationView = {
  id: number;
  kind: CommemorationKind;
  /** Arabic is missing for one source entry; the UI then shows the English title. */
  name: { en: string; ar?: string };
  /** The title without "The Departure of" / "نياحة" and similar, for the small day cells. */
  short: { en: string; ar?: string };
  index?: { en?: string; ar?: string };
};

export type DayView = {
  date: string;
  weekday: number;
  /** "Tuesday, 22 September 2026" in each language. */
  label: Bilingual;
  /** "22" / "٢٢". */
  dayNumber: Bilingual;
  coptic: {
    year: number;
    month: number;
    day: number;
    /** "12 Thout 1743". */
    label: Bilingual;
    /** "12 Thout". */
    short: Bilingual;
    /** "12" / "١٢". */
    dayNumber: Bilingual;
  };
  observances: ObservanceView[];
  fast: ObservanceView | null;
  fastFree: ObservanceView | null;
  suppressed: ObservanceView[];
  commemorations: CommemorationView[];
};

const arabicNumber = new Intl.NumberFormat("ar-EG", { useGrouping: false });
const englishDate = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});
const arabicDate = new Intl.DateTimeFormat("ar-EG", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export function arabicDigits(value: number): string {
  return arabicNumber.format(value);
}

function observance(id: ObservanceId): ObservanceView {
  const { kind, en, ar } = OBSERVANCES[id];
  return { id, kind, name: { en, ar } };
}

const TITLE_EVENT = /^(the )?(departure|martyrdom|repose|commemoration) of (the )?|^(نياحة|استشهاد|إستشهاد|أستشهاد|شهادة|تذكار) +/i;

function shortTitle(title: string): string {
  const short = title.replace(TITLE_EVENT, "");
  return short.charAt(0).toUpperCase() + short.slice(1);
}

/** "Wednesday fast" reads better on a Wednesday than the rule's name. */
function weeklyFast(day: number): ObservanceView {
  return {
    id: "wednesday-friday",
    kind: "fast",
    name: day === 3 ? { en: "Wednesday fast", ar: "صوم الأربعاء" } : { en: "Friday fast", ar: "صوم الجمعة" },
  };
}

export function dayView(iso: string): DayView | null {
  const day = calendarDay(iso);
  if (!day) return null;
  const instant = new Date(`${iso}T00:00:00Z`);
  const { year, month, day: copticDay } = day.coptic;
  const monthEn = copticMonthName(month, "en");
  const monthAr = copticMonthName(month, "ar");
  return {
    date: iso,
    weekday: weekday(iso),
    label: { en: englishDate.format(instant), ar: arabicDate.format(instant) },
    dayNumber: { en: String(instant.getUTCDate()), ar: arabicDigits(instant.getUTCDate()) },
    coptic: {
      year,
      month,
      day: copticDay,
      label: {
        en: `${copticDay} ${monthEn} ${year}`,
        ar: `${arabicDigits(copticDay)} ${monthAr} ${arabicDigits(year)}`,
      },
      short: { en: `${copticDay} ${monthEn}`, ar: `${arabicDigits(copticDay)} ${monthAr}` },
      dayNumber: { en: String(copticDay), ar: arabicDigits(copticDay) },
    },
    observances: day.observances.map(observance),
    fast: day.fast === "wednesday-friday" ? weeklyFast(weekday(iso)) : day.fast ? observance(day.fast) : null,
    fastFree: day.fastFree ? observance(day.fastFree) : null,
    suppressed: day.suppressed.map(observance),
    commemorations: commemorationsFor(day.coptic).map((entry) => ({
      id: entry.id,
      kind: entry.kind,
      name: { en: entry.en, ...(entry.ar ? { ar: entry.ar } : {}) },
      short: { en: shortTitle(entry.en), ...(entry.ar ? { ar: shortTitle(entry.ar) } : {}) },
      ...(entry.index ? { index: entry.index } : {}),
    })),
  };
}
