"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import {
  directionForLanguage,
  LANGUAGE_COOKIE,
  LANGUAGE_STORAGE_KEY,
  Language,
  normalizeLanguage,
  TranslationKey,
  translations,
} from "../lib/i18n";

type LanguageContextValue = {
  language: Language;
  dir: "ltr" | "rtl";
  setLanguage: (language: Language) => void;
  t: (key: TranslationKey) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function hasLanguageCookie() {
  return document.cookie.split(";").some((part) => part.trim().startsWith(`${LANGUAGE_COOKIE}=`));
}

function persistLanguage(language: Language) {
  // The cookie lets the server render the right language on the next request (UI-008).
  document.cookie = `${LANGUAGE_COOKIE}=${language}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Storage can be unavailable (private mode); the cookie is enough.
  }
}

export function LanguageProvider({
  children,
  initialLanguage = "en",
}: {
  children: ReactNode;
  initialLanguage?: Language;
}) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);

  // One-time migration: visitors who chose a language before the cookie existed only have it
  // in localStorage. Adopt it once and write the cookie so later visits render correctly.
  useEffect(() => {
    if (hasLanguageCookie()) return;
    let stored: Language | null = null;
    try {
      const raw = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
      stored = raw ? normalizeLanguage(raw) : null;
    } catch {
      stored = null;
    }
    const next = stored ?? initialLanguage;
    persistLanguage(next);
    if (next === initialLanguage) return;
    // Deferred so the state change happens outside the effect body (react-hooks rule).
    const timer = window.setTimeout(() => setLanguageState(next), 0);
    return () => window.clearTimeout(timer);
  }, [initialLanguage]);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = directionForLanguage(language);
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => {
    return {
      language,
      dir: directionForLanguage(language),
      setLanguage(nextLanguage) {
        const normalized = normalizeLanguage(nextLanguage);
        setLanguageState(normalized);
        persistLanguage(normalized);
      },
      t(key) {
        return translations[language][key] || translations.en[key];
      },
    };
  }, [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) {
    throw new Error("useLanguage must be used inside LanguageProvider");
  }
  return value;
}
