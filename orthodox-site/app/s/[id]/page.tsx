import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";
import SharedAnswer from "../../../components/SharedAnswer";
import { query } from "../../../lib/db";
import { sharedAnswerMetadata } from "../../../lib/share-page";
import { getSnapshot } from "../../../lib/share-store";

type Props = { params: Promise<{ id: string }> };

// One database read for both the metadata and the page.
const loadSnapshot = cache((id: string) => getSnapshot({ query }, id));

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const snapshot = await loadSnapshot((await params).id);
  if (!snapshot) return { title: "Shared answer not found", robots: { index: false, follow: false } };
  return sharedAnswerMetadata(snapshot);
}

export default async function SharedAnswerPage({ params }: Props) {
  const snapshot = await loadSnapshot((await params).id);
  if (!snapshot) notFound();

  return (
    <main className="page-shell shared-page">
      <SharedAnswer snapshot={snapshot} />
    </main>
  );
}
