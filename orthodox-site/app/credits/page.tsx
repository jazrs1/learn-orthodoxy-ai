import type { Metadata } from "next";
import { WithItalic } from "../font-italic";
import { pageMetadata } from "../../lib/site";
import CreditsPage from "./credits-page";

export const metadata: Metadata = pageMetadata({
  title: "Sources and credits",
  description:
    "The books behind Learn Orthodoxy: the Catechism of the Coptic Orthodox Church and the Encyclopedia of the Saints and Fathers of the Church, with thanks to Fr. Tadros Yacoub Malaty.",
  path: "/credits",
});

export default function Page() {
  return (
    <WithItalic>
      <CreditsPage />
    </WithItalic>
  );
}
