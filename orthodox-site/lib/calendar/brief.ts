import type { Language } from "../i18n";

/**
 * A commemoration's name as one short phrase, for the home page's Today line (UI-018). Takes the
 * short title (the event word already gone) and keeps the name: parentheses and everything after
 * the first comma go, and in Arabic the patriarchal numbering after "البطريرك".
 *
 *   "Pope Mettaos II (Matthew II), 90th Patriarch of the See of St. Mark" → "Pope Mettaos II"
 *   "البابا متاؤس الثانى البطريرك التسعين من بطاركة الكرازة المرقسية" → "البابا متاؤس الثانى"
 */
export function briefName(short: string, language: Language): string {
  let text = short.replace(/\s*\([^)]*\)/g, "");
  text = text.split(language === "ar" ? /[،,]/ : /,/)[0];
  if (language === "ar") text = text.split(/\s+(?:البطريرك|بطريرك)(?:\s|$)/)[0];
  return text.replace(/\s+/g, " ").trim() || short.trim();
}
