import Image from "next/image";
import { BRAND } from "../lib/brand";

// Section divider: two thin gold rules around the brand cross (UI-014). Decorative only, and
// used sparingly: between the major sections of a page, never inside running text.
export default function Ornament({ className = "" }: { className?: string }) {
  return (
    <div className={`ornament ${className}`} aria-hidden="true">
      <span className="ornament-rule" />
      <Image src={BRAND.cross} alt="" width={22} height={22} className="ornament-cross" />
      <span className="ornament-rule" />
    </div>
  );
}
