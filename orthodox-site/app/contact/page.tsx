import type { Metadata } from "next";
import { pageMetadata } from "../../lib/site";
import ContactPage from "./contact-page";

export const metadata: Metadata = pageMetadata({
  title: "Contact",
  description: "Send feedback or questions about Learn Orthodoxy to the team.",
  path: "/contact",
});

export default function Page() {
  return <ContactPage />;
}
