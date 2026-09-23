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
  const otherLanguage = language === "ar" ? "en" : "ar";
  const [hash, setHash] = useState("");

  const showsMobileSidebarToggle =
    pathname === "/" ||
    pathname === "/chat" ||
    pathname === "/calendar" ||
    pathname === "/credits" ||
    pathname === "/contact";
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
    { id: "saints", label: t("saints") },
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
            href="/calendar"
            className={`nav-link ${pathname === "/calendar" ? "nav-link-active" : ""}`}
            aria-current={pathname === "/calendar" ? "page" : undefined}
          >
            {t("calendar")}
          </Link>
          {/* Credits and Contact are in the page footer and the sidebar (UI-019). */}
        </div>

        {/* One toggle, named in the other language: "العربية" on English pages, "English" on Arabic. */}
        <button
          type="button"
          lang={otherLanguage}
          className="language-toggle-btn"
          onClick={() => setLanguage(otherLanguage)}
        >
          {otherLanguage === "ar" ? "العربية" : "English"}
        </button>
      </nav>
    </header>
  );
}
