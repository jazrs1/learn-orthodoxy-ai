"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import {
  directionForLanguage,
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

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedLanguage = normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY));
    if (storedLanguage === language) return;

    const timer = window.setTimeout(() => {
      setLanguageState(storedLanguage);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [language]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const dir = directionForLanguage(language);
    document.documentElement.lang = language;
    document.documentElement.dir = dir;
    document.body.dataset.language = language;
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => {
    const dir = directionForLanguage(language);

    return {
      language,
      dir,
      setLanguage(nextLanguage) {
        const normalized = normalizeLanguage(nextLanguage);
        setLanguageState(normalized);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(LANGUAGE_STORAGE_KEY, normalized);
        }
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
