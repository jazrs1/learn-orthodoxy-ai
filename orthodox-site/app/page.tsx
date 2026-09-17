import type { Metadata } from "next";
import { pageMetadata } from "../lib/site";
import HomePage from "./home-page";

export const metadata: Metadata = pageMetadata({ path: "/" });

export default function Page() {
  return <HomePage />;
}
