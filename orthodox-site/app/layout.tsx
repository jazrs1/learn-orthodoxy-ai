import type { Metadata } from "next";
import "./globals.css";
import { fontVariables } from "./fonts";
import Navbar from "../components/Navbar";
import { LanguageProvider } from "../components/LanguageProvider";
import { directionForLanguage } from "../lib/i18n";
import { getRequestLanguage } from "../lib/request-language";

const siteUrl = "https://learnorthodoxy.net";
const siteDescription =
  "Ask questions about Orthodox saints, Coptic Orthodox catechism, Church teaching, and Orthodox Christian tradition.";
const ogImage = "/og-image.png";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Learn Orthodoxy",
  description: siteDescription,
  verification: {
    google: "qSkr64BCs0d2ya1fOEyD6AmupuD7UhMKVqu_Vxb_wu0",
  },
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Learn Orthodoxy",
    description: siteDescription,
    url: siteUrl,
    siteName: "Learn Orthodoxy",
    images: [
      {
        url: ogImage,
        width: 1200,
        height: 630,
        alt: "Learn Orthodoxy",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Learn Orthodoxy",
    description: siteDescription,
    images: [ogImage],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
  icons: {
    icon: "/favicon.ico",
  },
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
