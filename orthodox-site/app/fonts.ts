import { Inter, Noto_Naskh_Arabic, Source_Serif_4 } from "next/font/google";

// Self-hosted at build time by next/font (UI-007). The CSS variables are consumed by the
// --font-reading / --font-ui tokens in globals.css.

export const serif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

export const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// Arabic glyphs only; English pages never request it, so it is not preloaded.
export const naskh = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  variable: "--font-naskh",
  display: "swap",
  preload: false,
});

export const fontVariables = `${serif.variable} ${sans.variable} ${naskh.variable}`;
