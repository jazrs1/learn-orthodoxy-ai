import type { ReactNode } from "react";
import { EB_Garamond } from "next/font/google";

// EB Garamond Italic, for questions and notes (UI-013, UI-015). It is set only on the pages that
// show it above the fold (home, chat, credits), so next/font preloads it on those routes alone.
// Loading it late caused a visible swap and a small layout shift.
const garamondItalic = EB_Garamond({
  subsets: ["latin"],
  style: "italic",
  variable: "--font-garamond-italic",
  display: "swap",
});

export function WithItalic({ children }: { children: ReactNode }) {
  return <div className={`${garamondItalic.variable} font-scope`}>{children}</div>;
}
