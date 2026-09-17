import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { IconArrowForward } from "../components/Icons";
import { translations } from "../lib/i18n";
import { getRequestLanguage } from "../lib/request-language";

// Next.js already marks not-found responses noindex.
export const metadata: Metadata = {
  title: "Page not found",
};

export default async function NotFound() {
  const t = translations[await getRequestLanguage()];

  return (
    <main className="page-shell not-found-page">
      <Image src="/cross-mark.png" alt="" width={72} height={72} className="not-found-cross" />
      <p className="not-found-code" aria-hidden="true">
        404
      </p>
      <h1 className="page-title not-found-title">{t.notFoundTitle}</h1>
      <p className="page-subtitle">{t.notFoundText}</p>
      <div className="not-found-actions">
        <Link href="/" className="button button-primary">
          {t.backHome}
        </Link>
        <Link href="/chat" className="button button-secondary">
          <span>{t.startChat}</span>
          <IconArrowForward size={16} />
        </Link>
      </div>
    </main>
  );
}
