"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "./LanguageProvider";

export default function Navbar() {
  const pathname = usePathname();
  const { t } = useLanguage();
  const hasSidebarOffset = pathname === "/" || pathname === "/chat";
  const showsMobileSidebarToggle = hasSidebarOffset || pathname === "/sources" || pathname === "/contact";

  function openMobileSidebar() {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent("chat:openSidebar"));
  }

  return (
    <header className="site-header">
      <nav className={`navbar ${hasSidebarOffset ? "navbar-sidebar-offset" : ""}`}>
        {showsMobileSidebarToggle ? (
          <button
            type="button"
            className="mobile-sidebar-toggle navbar-sidebar-toggle"
            onClick={openMobileSidebar}
            aria-label={t("openChatsPanel")}
          >
            <span />
            <span />
            <span />
          </button>
        ) : null}

        <Link href="/" className="nav-brand">
          <Image
            src="/cross.png"
            alt="Coptic cross"
            width={34}
            height={34}
            className="nav-cross"
            priority
          />
          <span className="nav-title">{t("appName")}</span>
        </Link>

        <div className="nav-links">
          <Link href="/" className="nav-link">
            {t("home")}
          </Link>
          <Link href="/sources" className="nav-link">
            {t("credits")}
          </Link>
          <Link href="/contact" className="nav-link">
            {t("contact")}
          </Link>
        </div>
      </nav>
    </header>
  );
}
