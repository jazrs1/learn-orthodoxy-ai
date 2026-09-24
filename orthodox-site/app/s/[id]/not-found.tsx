import type { Metadata } from "next";
import Link from "next/link";
import { IconArrowForward } from "../../../components/Icons";
import Ornament from "../../../components/Ornament";
import { translations } from "../../../lib/i18n";
import { getRequestLanguage } from "../../../lib/request-language";

// A shared link that leads nowhere (mistyped, or never made): say so kindly and offer to ask (UI-030).
export const metadata: Metadata = {
  title: "Shared answer not found",
};

export default async function SharedAnswerNotFound() {
  const t = translations[await getRequestLanguage()];

  return (
    <main className="page-shell not-found-page">
      <h1 className="page-title not-found-title">{t.sharedNotFoundTitle}</h1>
      <Ornament className="not-found-ornament" />
      <p className="page-subtitle">{t.sharedNotFoundText}</p>
      <div className="not-found-actions">
        <Link href="/" className="button button-primary">
          <span>{t.askYourOwn}</span>
          <IconArrowForward size={16} />
        </Link>
      </div>
    </main>
  );
}
