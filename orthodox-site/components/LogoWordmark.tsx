type LogoWordmarkProps = {
  variant?: "nav" | "hero";
};

export default function LogoWordmark({ variant = "nav" }: LogoWordmarkProps) {
  return (
    <span className={`logo-wordmark logo-wordmark-${variant}`} aria-label="Learn Orthodoxy">
      <span className="logo-learn">Learn</span>
      <span className="logo-orthodoxy">
        <span className="logo-cross-o" aria-hidden="true">
          <svg className="logo-coptic-cross" viewBox="0 0 100 100" focusable="false">
            <path d="M50 6 61.5 23.5C64.2 27.7 67.6 29.6 72.5 29.6H90.5C94.5 29.6 96.2 34.6 93 37L78.5 47.8C75.8 49.8 75.8 50.2 78.5 52.2L93 63C96.2 65.4 94.5 70.4 90.5 70.4H72.5C67.6 70.4 64.2 72.3 61.5 76.5L50 94 38.5 76.5C35.8 72.3 32.4 70.4 27.5 70.4H9.5C5.5 70.4 3.8 65.4 7 63L21.5 52.2C24.2 50.2 24.2 49.8 21.5 47.8L7 37C3.8 34.6 5.5 29.6 9.5 29.6H27.5C32.4 29.6 35.8 27.7 38.5 23.5L50 6Z" />
          </svg>
        </span>
        <span>rthodoxy</span>
      </span>
    </span>
  );
}
