"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import LogoWordmark from "./LogoWordmark";

export default function Navbar() {
  const pathname = usePathname();
  const hasSidebarOffset = pathname === "/" || pathname === "/chat";

  function openMobileSidebar() {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent("chat:openSidebar"));
  }

  return (
    <header className="site-header">
      <nav className={`navbar ${hasSidebarOffset ? "navbar-sidebar-offset" : ""}`}>
        {hasSidebarOffset ? (
          <button
            type="button"
            className="mobile-sidebar-toggle navbar-sidebar-toggle"
            onClick={openMobileSidebar}
            aria-label="Open chats panel"
          >
            <span />
            <span />
            <span />
          </button>
        ) : null}

        <Link href="/" className="nav-brand">
          <LogoWordmark variant="nav" />
        </Link>

        <div className="nav-links">
          <Link href="/" className="nav-link">
            Home
          </Link>
          <Link href="/sources" className="nav-link">
            Credits
          </Link>
        </div>
      </nav>
    </header>
  );
}
