"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();
  const hasSidebarOffset = pathname === "/" || pathname === "/chat";
  const showsMobileSidebarToggle = hasSidebarOffset || pathname === "/sources";

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
            aria-label="Open chats panel"
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
          <span className="nav-title">Learn Orthodoxy</span>
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
