import type { Metadata } from "next";
import { WithItalic } from "../font-italic";
import { pageMetadata } from "../../lib/site";
import ChatPage from "./chat-page";

export const metadata: Metadata = pageMetadata({
  title: "Ask a question",
  description:
    "Ask about Coptic Orthodox teaching, browse catechism topics, or look up a saint. Every answer cites the book and page it comes from.",
  path: "/chat",
});

export default function Page() {
  return (
    <WithItalic>
      <ChatPage />
    </WithItalic>
  );
}
