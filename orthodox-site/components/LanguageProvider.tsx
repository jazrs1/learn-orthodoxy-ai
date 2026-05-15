"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo } from "react";
import {
  directionForLanguage,
  Language,
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
  const language: Language = "en";

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
      setLanguage() {
        // The full Arabic UI toggle is intentionally disabled for now.
      },
      t(key) {
        return translations.en[key];
      },
    };
  }, []);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) {
    throw new Error("useLanguage must be used inside LanguageProvider");
  }
  return value;
}
