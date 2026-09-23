/** Words used by the Today banner and the /calendar page, in both languages (CAL-005, CAL-006). */

import type { Language } from "../i18n.ts";

export const CALENDAR_STRINGS = {
  en: {
    bannerLabel: "Today in the Coptic calendar",
    today: "Today",
    openDay: "Open this day in the calendar",
    askAboutSaint: "Ask about this saint",
    saintQuestion: "Tell me about {name}.",
    pageTitle: "Coptic Calendar",
    pageLead:
      "Feasts, fasts and the saints the Church remembers each day, from January 2026 to December 2027, with the Coptic date beside each day.",
    previousMonth: "Previous month",
    nextMonth: "Next month",
    jumpToMonth: "Go to month",
    go: "Go",
    goToToday: "Today",
    monthGridLabel: "{month}, days",
    weekdays: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    weekdaysShort: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    feasts: "Feasts",
    fast: "Fast",
    fastFree: "No fasting",
    commemorations: "Commemorations",
    noCommemorations: "The source lists no commemoration for this day.",
    notCelebrated: "{feast} is not celebrated this year: it falls in Holy Week.",
    selectedDay: "Selected day",
    todayMarker: "today",
    legendFeast: "Feast",
    legendFast: "Fast day",
    legendFastFree: "Fast-free",
    saintInIndex: "Read about this saint",
    attributionTitle: "Sources",
    attributionDates:
      "Dates are calculated from the rules of the Coptic calendar and checked against the calendar of the Coptic Orthodox Metropolis of the Southern United States.",
    attributionSaints: "Saint commemorations are from Katameros",
    outOfRange: "The calendar covers January 2026 to December 2027.",
  },
  ar: {
    bannerLabel: "اليوم في التقويم القبطي",
    today: "اليوم",
    openDay: "افتح هذا اليوم في التقويم",
    askAboutSaint: "اسأل عن هذه السيرة",
    saintQuestion: "حدثني عن {name}.",
    pageTitle: "التقويم القبطي",
    pageLead: "الأعياد والأصوام والقديسون الذين تذكرهم الكنيسة كل يوم، من يناير ٢٠٢٦ إلى ديسمبر ٢٠٢٧، مع التاريخ القبطي لكل يوم.",
    previousMonth: "الشهر السابق",
    nextMonth: "الشهر التالي",
    jumpToMonth: "انتقل إلى شهر",
    go: "انتقل",
    goToToday: "اليوم",
    monthGridLabel: "أيام {month}",
    weekdays: ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"],
    weekdaysShort: ["أحد", "اثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت"],
    feasts: "الأعياد",
    fast: "الصوم",
    fastFree: "لا صوم",
    commemorations: "التذكارات",
    noCommemorations: "لا يذكر المصدر تذكارًا لهذا اليوم.",
    notCelebrated: "لا يُحتفل بـ{feast} هذا العام لأنه يقع في أسبوع الآلام.",
    selectedDay: "اليوم المختار",
    todayMarker: "اليوم",
    legendFeast: "عيد",
    legendFast: "يوم صوم",
    legendFastFree: "بلا صوم",
    saintInIndex: "اقرأ عن هذا القديس",
    attributionTitle: "المصادر",
    attributionDates:
      "حُسبت التواريخ بحسب قواعد التقويم القبطي، وقوبلت بتقويم إيبارشية الكنيسة القبطية الأرثوذكسية في جنوب الولايات المتحدة.",
    attributionSaints: "تذكارات القديسين من كاتاميروس",
    outOfRange: "يغطي التقويم الفترة من يناير ٢٠٢٦ إلى ديسمبر ٢٠٢٧.",
  },
} as const;

export type CalendarStrings = (typeof CALENDAR_STRINGS)["en"];

export function calendarStrings(language: Language) {
  return CALENDAR_STRINGS[language];
}

/** "and 3 more" / Arabic with its dual and plural forms. */
export function moreCommemorations(count: number, language: Language): string {
  if (language === "en") return `and ${count} more`;
  const n = new Intl.NumberFormat("ar-EG").format(count);
  if (count === 1) return "وتذكار آخر";
  if (count === 2) return "وتذكاران آخران";
  if (count <= 10) return `و${n} تذكارات أخرى`;
  return `و${n} تذكارًا آخر`;
}

export function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => values[key] ?? "");
}
