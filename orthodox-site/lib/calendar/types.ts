import type { ObservanceId } from "./observances.ts";

export type CopticDateParts = {
  year: number;
  /** 1 = Thout … 13 = Nasie. */
  month: number;
  day: number;
};

/** One day of the generated calendar (lib/calendar/data/calendar-2026-2027.json). */
export type CalendarDay = {
  /** Gregorian date, "YYYY-MM-DD". */
  date: string;
  coptic: CopticDateParts;
  /** Feasts and Holy Week days, most important first. Fasts are in `fast`. */
  observances: ObservanceId[];
  /** The fast kept that day, if any (a seasonal fast, or the Wednesday/Friday fast). */
  fast: ObservanceId | null;
  /** The fast-free period the day falls in, if any. */
  fastFree: ObservanceId | null;
  /** Feasts that would fall on this day but are not celebrated this year (CAL-002, rule 3). */
  suppressed: ObservanceId[];
};

export type CalendarData = {
  meta: {
    generatedBy: string;
    library: string;
    start: string;
    end: string;
    rules: string[];
  };
  days: CalendarDay[];
};

/** "saint" entries can be today's saint; "event" and "feast" entries cannot (CAL-002). */
export type CommemorationKind = "saint" | "event" | "monthly" | "feast";

export type Commemoration = {
  /** The source's own id for this entry (Katameros story id). */
  id: number;
  kind: CommemorationKind;
  en: string;
  /** Missing for the one Katameros entry that has no Arabic title. */
  ar?: string;
  /** Name of the matching entry in our saints index, per language, when there is one. */
  index?: { en?: string; ar?: string };
};

export type SaintsData = {
  source: {
    name: string;
    url: string;
    repository: string;
    commit: string;
    file: string;
    table: string;
    extracted: string;
    license: string;
    permission: string;
    content: string;
    indexSnapshot: string;
  };
  /** Keyed "month-day" of the Coptic calendar, e.g. "3-12". */
  days: Record<string, Commemoration[]>;
};
