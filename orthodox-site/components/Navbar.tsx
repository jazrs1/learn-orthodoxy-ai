"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { MouseEvent } from "react";
import { useLanguage } from "./LanguageProvider";

export default function Navbar() {
  const pathname = usePathname();
  const { language, setLanguage, t } = useLanguage();
  const [hash, setHash] = useState("");

  const hasSidebarOffset = pathname === "/" || pathname === "/chat";
  const showsMobileSidebarToggle = hasSidebarOffset || pathname === "/credits" || pathname === "/contact";
  const chatModeHash = hash || "#chat";

  useEffect(() => {
    function syncHash() {
      setHash(window.location.hash || "");
    }

    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => {
      window.removeEventListener("hashchange", syncHash);
    };
  }, [pathname]);

  function openMobileSidebar() {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent("chat:openSidebar"));
  }

  function navLinkClass(isActive: boolean) {
    return `nav-link ${isActive ? "nav-link-active" : ""}`;
  }

  function selectChatMode(mode: "chat" | "catechism" | "saints", event: MouseEvent<HTMLAnchorElement>) {
    if (pathname !== "/chat" || typeof window === "undefined") return;

    event.preventDefault();
    const nextHash = `#${mode}`;
    window.history.replaceState(null, "", `/chat${nextHash}`);
    setHash(nextHash);
    window.dispatchEvent(new CustomEvent("chat:setMode", { detail: { mode } }));
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

        <div className="language-toggle" aria-label={t("language")}>
          <button
            type="button"
            className={`language-toggle-btn ${language === "en" ? "language-toggle-btn-active" : ""}`}
            onClick={() => setLanguage("en")}
          >
            English
          </button>
          <button
            type="button"
            className={`language-toggle-btn ${language === "ar" ? "language-toggle-btn-active" : ""}`}
            onClick={() => setLanguage("ar")}
          >
            العربية
          </button>
        </div>

        <div className="nav-links">
          <Link
            href="/chat#chat"
            className={navLinkClass(pathname === "/chat" && chatModeHash === "#chat")}
            onClick={(event) => selectChatMode("chat", event)}
          >
            {t("chat")}
          </Link>
          <Link
            href="/chat#catechism"
            className={navLinkClass(pathname === "/chat" && chatModeHash === "#catechism")}
            onClick={(event) => selectChatMode("catechism", event)}
          >
            {t("catechism")}
          </Link>
          <Link
            href="/chat#saints"
            className={navLinkClass(pathname === "/chat" && chatModeHash === "#saints")}
            onClick={(event) => selectChatMode("saints", event)}
          >
            {t("saintsSearch")}
          </Link>
          <Link href="/credits" className={navLinkClass(pathname === "/credits")}>
            {t("credits")}
          </Link>
          <Link href="/contact" className={navLinkClass(pathname === "/contact")}>
            {t("contact")}
          </Link>
        </div>
      </nav>
    </header>
  );
}
