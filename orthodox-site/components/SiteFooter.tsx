"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "./LanguageProvider";

/**
 * The page footer on the home, calendar, credits and contact pages (UI-019): Credits and Contact
 * moved here from the header. The chat page has no footer; its sidebar lists both.
 */
export default function SiteFooter() {
  const { t } = useLanguage();
  const pathname = usePathname();
  const links = [
    { href: "/credits", label: t("credits") },
    { href: "/contact", label: t("contact") },
  ];

  return (
    <footer className="site-footer">
      <nav className="site-footer-nav" aria-label={t("footerNavigation")}>
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="site-footer-link"
            aria-current={pathname === link.href ? "page" : undefined}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </footer>
  );
}
