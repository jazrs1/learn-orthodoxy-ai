import type { NextConfig } from "next";
import { BRAND } from "./lib/brand";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // /about was an unstyled, unlinked draft; /sources was the old name of the credits page (UI-010).
      { source: "/about", destination: "/credits", permanent: true },
      { source: "/sources", destination: "/credits", permanent: true },
    ];
  },
  async rewrites() {
    // Browsers and crawlers that ask for /favicon.ico directly get the current brand favicon (UI-014).
    return [{ source: "/favicon.ico", destination: BRAND.favicon }];
  },
};

export default nextConfig;
