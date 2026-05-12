import Image from "next/image";

type LogoWordmarkProps = {
  variant?: "nav" | "hero";
};

export default function LogoWordmark({ variant = "nav" }: LogoWordmarkProps) {
  return (
    <span className={`logo-wordmark logo-wordmark-${variant}`} aria-label="Learn Orthodoxy">
      <span className="logo-learn">Learn</span>
      <span className="logo-orthodoxy">
        <span className="logo-cross-o" aria-hidden="true">
          <span className="logo-o-letter">O</span>
          <Image src="/cross.png" alt="" width={96} height={96} priority={variant === "hero"} />
        </span>
        <span>rthodoxy</span>
      </span>
    </span>
  );
}
