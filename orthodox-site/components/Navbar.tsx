import Image from "next/image";
import Link from "next/link";

export default function Navbar() {
  return (
    <header className="site-header">
      <nav className="navbar">
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
            Sources
          </Link>
        </div>
      </nav>
    </header>
  );
}
