import type { CommemorationView, DayView } from "../../lib/calendar/view";
import type { Language } from "../../lib/i18n";

export function calendarHref(date: string): string {
  return `/calendar?d=${date}`;
}

/** Opens the saint's entry in the Saints tab (handled by app/chat/chat-page.tsx). */
export function saintHref(indexName: string): string {
  return `/chat?saint=${encodeURIComponent(indexName)}#saints`;
}

/** Feasts of the day, then its fast or fast-free period: "Nayrouz · Friday fast". */
export function dayHeadline(day: DayView, language: Language): string {
  const parts = day.observances.map((observance) => observance.name[language]);
  if (day.fast) parts.push(day.fast.name[language]);
  else if (day.fastFree) parts.push(day.fastFree.name[language]);
  return parts.join(" · ");
}

/**
 * Props for the element holding a commemoration's title. One source entry has no Arabic title;
 * it is shown in English and marked as such for screen readers and fonts.
 */
export function commemorationTitle(entry: CommemorationView, language: Language, form: "name" | "short" = "name") {
  const text = entry[form];
  const arabic = language === "ar" ? text.ar : undefined;
  return {
    children: arabic ?? text.en,
    ...(language === "ar" && !arabic ? { lang: "en", dir: "ltr" as const } : {}),
  };
}
