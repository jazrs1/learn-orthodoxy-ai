"use client";

import { Language } from "../lib/i18n";
import { useLanguage } from "./LanguageProvider";

export default function LanguageToggle() {
  const { language, setLanguage, t } = useLanguage();

  return (
    <div className="floating-language-toggle">
      <label className="floating-language-label">
        <span className="floating-language-caption">{t("language")}</span>
        <select
          className="floating-language-select"
          value={language}
          onChange={(event) => setLanguage(event.target.value as Language)}
          aria-label={t("language")}
        >
          <option value="en">{t("english")}</option>
          <option value="ar">{t("arabic")}</option>
        </select>
      </label>
    </div>
  );
}
