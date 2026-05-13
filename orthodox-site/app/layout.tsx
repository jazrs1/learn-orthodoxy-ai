import type { Metadata } from "next";
import "./globals.css";
import Navbar from "../components/Navbar";

const siteUrl = "https://learnorthodoxy.net";
const siteDescription =
  "Ask questions about Orthodox saints, Coptic Orthodox catechism, Church teaching, and Orthodox Christian tradition.";
const ogImage = "/og-image.png";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Learn Orthodoxy",
  description: siteDescription,
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        {children}
      </body>
    </html>
  );
}
