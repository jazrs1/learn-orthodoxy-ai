import type { Metadata } from "next";
import { WithItalic } from "./font-italic";
import { pageMetadata } from "../lib/site";
import HomePage from "./home-page";

export const metadata: Metadata = pageMetadata({ path: "/" });

export default function Page() {
  return (
    <WithItalic>
      <HomePage />
    </WithItalic>
  );
}
