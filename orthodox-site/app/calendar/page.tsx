import type { Metadata } from "next";
import { connection } from "next/server";
import { SAINTS_SOURCE } from "../../lib/calendar/calendar";
import { monthOptions, monthView, resolveSelection } from "../../lib/calendar/month";
import { pageMetadata } from "../../lib/site";
import CalendarPage from "./calendar-page";

export const metadata: Metadata = pageMetadata({
  title: "Coptic Calendar",
  description:
    "The Coptic Orthodox calendar for 2026 and 2027: feasts, fasts and the saints commemorated each day, with the Coptic date, in English and Arabic.",
  path: "/calendar",
});

type SearchParams = Promise<{ d?: string | string[]; m?: string | string[] }>;

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

/** /calendar?d=YYYY-MM-DD opens a day, ?m=YYYY-MM a month (CAL-006). Only that month is sent. */
export default async function Page({ searchParams }: { searchParams: SearchParams }) {
  await connection();
  const params = await searchParams;
  const serverToday = new Date().toISOString().slice(0, 10);
  const selection = resolveSelection({ d: first(params.d), m: first(params.m) }, serverToday);
  const month = selection.date.slice(0, 7);

  return (
    <CalendarPage
      key={month}
      month={monthView(month)}
      months={monthOptions()}
      initialDate={selection.date}
      dateFromUrl={selection.requested}
      clamped={selection.clamped}
      serverToday={serverToday}
      saintsSource={{ name: SAINTS_SOURCE.name, url: SAINTS_SOURCE.url }}
    />
  );
}
