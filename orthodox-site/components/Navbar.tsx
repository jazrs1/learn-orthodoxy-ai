"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();
  const hasSidebarOffset = pathname === "/" || pathname === "/chat";

  return (
    <header className="site-header">
      <nav className={`navbar ${hasSidebarOffset ? "navbar-sidebar-offset" : ""}`}>
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
