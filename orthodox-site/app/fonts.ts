import { Amiri, EB_Garamond, Noto_Naskh_Arabic, Source_Serif_4 } from "next/font/google";

// Self-hosted at build time by next/font (UI-007, UI-013). The CSS variables are consumed by the
// --font-display / --font-reading / --font-ui tokens in globals.css.

// Headings, labels, navigation and buttons (variable weight, Latin only).
export const garamond = EB_Garamond({
  subsets: ["latin"],
  variable: "--font-garamond",
  display: "swap",
});

// Italic is a separate file used for questions; it is not preloaded so pages that never show it
// don't pay for it.
export const garamondItalic = EB_Garamond({
  subsets: ["latin"],
  style: "italic",
  variable: "--font-garamond-italic",
  display: "swap",
  preload: false,
});

// Long answer text: sturdier than Garamond at 16–18px, especially on 1x screens (UI-013).
export const serif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

// Arabic glyphs only; English pages never request these, so they are not preloaded.
export const naskh = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  variable: "--font-naskh",
  display: "swap",
  preload: false,
});

// Arabic headings.
export const amiri = Amiri({
  weight: "400",
  subsets: ["arabic"],
  variable: "--font-amiri",
  display: "swap",
  preload: false,
});

export const fontVariables = [garamond, garamondItalic, serif, naskh, amiri].map((font) => font.variable).join(" ");
