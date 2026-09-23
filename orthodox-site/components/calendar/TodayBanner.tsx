import { connection } from "next/server";
import { isInCalendar } from "../../lib/calendar/calendar";
import { possibleTodays } from "../../lib/calendar/today";
import { dayView } from "../../lib/calendar/view";
import TodayBannerStrip from "./TodayBannerStrip";

/**
 * The home page's Today strip (CAL-005). The server doesn't know the visitor's date, so it sends
 * the two or three dates that are "today" somewhere right now; the strip shows the visitor's own.
 */
export default async function TodayBanner() {
  await connection();
  const now = new Date();
  const days = possibleTodays(now)
    .filter(isInCalendar)
    .map(dayView)
    .filter((day) => day !== null);
  if (!days.length) return null;
  return <TodayBannerStrip days={days} serverToday={now.toISOString().slice(0, 10)} />;
}
