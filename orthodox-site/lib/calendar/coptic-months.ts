/**
 * Coptic month names as coptic-calendar spells them (a test keeps them in step), except the
 * Arabic 13th month, written نسيء rather than the library's نسيئ (CAL-004).
 */
export const COPTIC_MONTHS: Record<"en" | "ar", readonly string[]> = {
  en: ["Thout", "Paopi", "Hathor", "Kiahk", "Tobi", "Meshir", "Paremhat", "Paremoude", "Pashons", "Paoni", "Epip", "Mesori", "Nasie"],
  ar: ["توت", "بابة", "هاتور", "كيهك", "طوبة", "أمشير", "برمهات", "برمودة", "بشنس", "بؤونة", "أبيب", "مسرى", "نسيء"],
};

export function copticMonthName(month: number, language: "en" | "ar"): string {
  return COPTIC_MONTHS[language][month - 1] ?? "";
}
