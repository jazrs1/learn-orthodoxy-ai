import Image from "next/image";

type LogoWordmarkProps = {
  variant?: "nav" | "hero";
};

export default function LogoWordmark({ variant = "nav" }: LogoWordmarkProps) {
  return (
    <span className={`logo-wordmark logo-wordmark-${variant}`} aria-label="Learn Orthodoxy">
      <span>Learn </span>
      <span className="logo-orthodoxy">
        <span className="logo-cross-o" aria-hidden="true">
          <Image src="/cross.png" alt="" width={96} height={96} priority={variant === "hero"} />
        </span>
        <span>rthodoxy</span>
      </span>
    </span>
  );
}
