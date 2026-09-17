"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { MouseEvent } from "react";
import { BRAND } from "../lib/brand";
import { IconMenu } from "./Icons";
import { useLanguage } from "./LanguageProvider";

type ChatMode = "chat" | "catechism" | "saints";

export default function Navbar() {
  const pathname = usePathname();
  const { language, setLanguage, t } = useLanguage();
  const [hash, setHash] = useState("");

  const showsMobileSidebarToggle =
    pathname === "/" || pathname === "/chat" || pathname === "/credits" || pathname === "/contact";
  const chatModeHash = hash || "#chat";

  useEffect(() => {
    function syncHash() {
      setHash(window.location.hash || "");
    }

    syncHash();
    window.addEventListener("hashchange", syncHash);
    window.addEventListener("chat:setMode", syncHash);
    return () => {
      window.removeEventListener("hashchange", syncHash);
      window.removeEventListener("chat:setMode", syncHash);
    };
  }, [pathname]);

  function openMobileSidebar() {
    window.dispatchEvent(new CustomEvent("chat:openSidebar"));
  }

  function selectChatMode(mode: ChatMode, event: MouseEvent<HTMLAnchorElement>) {
    if (pathname !== "/chat") return;

    event.preventDefault();
    const nextHash = `#${mode}`;
    window.history.replaceState(null, "", `/chat${nextHash}`);
    setHash(nextHash);
    window.dispatchEvent(new CustomEvent("chat:setMode", { detail: { mode } }));
  }

  const modes: Array<{ id: ChatMode; label: string }> = [
    { id: "chat", label: t("chat") },
    { id: "catechism", label: t("catechism") },
    { id: "saints", label: t("saintsSearch") },
  ];

  return (
    <header className="site-header">
      <nav className="navbar" aria-label={t("mainNavigation")}>
        {showsMobileSidebarToggle ? (
          <button
            type="button"
            className="icon-button mobile-sidebar-toggle navbar-sidebar-toggle"
            onClick={openMobileSidebar}
            aria-label={t("openChatsPanel")}
          >
            <IconMenu size={24} />
          </button>
        ) : null}

        <Link href="/" className="nav-brand">
          <Image
            src={BRAND.lettermark.src}
            alt=""
            width={BRAND.lettermark.width}
            height={BRAND.lettermark.height}
            className="nav-lettermark"
            loading="eager"
          />
          <span className="nav-title">{t("appName")}</span>
        </Link>

        <div className="nav-links">
          <div className="nav-modes">
            {modes.map((mode) => {
              const active = pathname === "/chat" && chatModeHash === `#${mode.id}`;
              return (
                <Link
                  key={mode.id}
                  href={`/chat#${mode.id}`}
                  className={`nav-link nav-mode ${active ? "nav-link-active" : ""}`}
                  aria-current={active ? "page" : undefined}
                  onClick={(event) => selectChatMode(mode.id, event)}
                >
                  {mode.label}
                </Link>
              );
            })}
          </div>
          <Link
            href="/credits"
            className={`nav-link ${pathname === "/credits" ? "nav-link-active" : ""}`}
            aria-current={pathname === "/credits" ? "page" : undefined}
          >
            {t("credits")}
          </Link>
          <Link
            href="/contact"
            className={`nav-link ${pathname === "/contact" ? "nav-link-active" : ""}`}
            aria-current={pathname === "/contact" ? "page" : undefined}
          >
            {t("contact")}
          </Link>
        </div>

        <div className="language-toggle" role="group" aria-label={t("language")}>
          <button
            type="button"
            lang="en"
            className={`language-toggle-btn ${language === "en" ? "language-toggle-btn-active" : ""}`}
            aria-pressed={language === "en"}
            onClick={() => setLanguage("en")}
          >
            English
          </button>
          <button
            type="button"
            lang="ar"
            className={`language-toggle-btn ${language === "ar" ? "language-toggle-btn-active" : ""}`}
            aria-pressed={language === "ar"}
            onClick={() => setLanguage("ar")}
          >
            العربية
          </button>
        </div>
      </nav>
    </header>
  );
}
