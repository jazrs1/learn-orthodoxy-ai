import type { Metadata, Viewport } from "next";
import "./globals.css";
import { fontVariables } from "./fonts";
import Navbar from "../components/Navbar";
import { LanguageProvider } from "../components/LanguageProvider";
import { directionForLanguage } from "../lib/i18n";
import { getRequestLanguage } from "../lib/request-language";
import { pageMetadata, SITE_DESCRIPTION, SITE_NAME, SITE_TAGLINE, SITE_URL } from "../lib/site";

// Defaults for every page; each page sets its own title, canonical URL and social tags
// through pageMetadata() (UI-010).
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: SITE_NAME,
  title: {
    default: `${SITE_NAME} — ${SITE_TAGLINE}`,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  verification: {
    google: "qSkr64BCs0d2ya1fOEyD6AmupuD7UhMKVqu_Vxb_wu0",
  },
  robots: {
    index: true,
    follow: true,
  },
  ...pageMetadata({ path: "/" }),
  alternates: undefined,
};

export const viewport: Viewport = {
  themeColor: "#f8f3ea",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Server-render the visitor's chosen language so Arabic pages never flash English (UI-008).
  const language = await getRequestLanguage();
  return (
    <html lang={language} dir={directionForLanguage(language)} className={fontVariables}>
      <body>
        <LanguageProvider initialLanguage={language}>
          <Navbar />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
