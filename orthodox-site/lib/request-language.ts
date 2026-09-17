import "server-only";

import { cookies } from "next/headers";
import { LANGUAGE_COOKIE, normalizeLanguage, type Language } from "./i18n";

/** The language the visitor chose last time (cookie set by LanguageProvider); English otherwise. */
export async function getRequestLanguage(): Promise<Language> {
  const store = await cookies();
  return normalizeLanguage(store.get(LANGUAGE_COOKIE)?.value);
}
