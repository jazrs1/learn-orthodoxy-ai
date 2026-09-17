import type { MetadataRoute } from "next";
import { BRAND } from "../lib/brand";
import { SITE_DESCRIPTION, SITE_NAME } from "../lib/site";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: SITE_NAME,
    description: SITE_DESCRIPTION,
    start_url: "/",
    display: "browser",
    background_color: "#f8f3ea",
    theme_color: "#f8f3ea",
    icons: [
      { src: BRAND.appIcon192, sizes: "192x192", type: "image/png" },
      { src: BRAND.appIcon512, sizes: "512x512", type: "image/png" },
    ],
  };
}
