import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // /about was an unstyled, unlinked draft; /sources was the old name of the credits page (UI-010).
      { source: "/about", destination: "/credits", permanent: true },
      { source: "/sources", destination: "/credits", permanent: true },
    ];
  },
};

export default nextConfig;
