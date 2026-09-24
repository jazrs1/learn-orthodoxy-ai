import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { OG_IMAGE } from "./site.ts";
import { shareDate, shareExcerpt, shareTitle, sharedAnswerMetadata } from "./share-page.ts";
import type { Snapshot } from "./share-store.ts";

const snapshot: Snapshot = {
  id: "Ab3dEfGh1jKlMn0p",
  question: "What is prayer?",
  answer:
    "**Prayer** is speaking with God [1]. It is the breath of the soul, and the Church teaches us to pray without ceasing, in the morning, at noon and at night [2].\n\n| Hour | Psalm |\n|---|---|\n| Prime | 1 |",
  sources: [],
  language: "en",
  corpusVersion: "v2",
  promptVersion: "p7",
  model: "gpt-test",
  answeredAt: "2026-09-23T18:04:00.000Z",
  createdAt: "2026-09-23T19:00:00.000Z",
};

describe("shared page text and link-preview tags (UI-030)", () => {
  it("uses the question as the title and a short plain excerpt as the description", () => {
    const metadata = sharedAnswerMetadata(snapshot);
    assert.deepEqual(metadata.title, { absolute: "What is prayer?" });
    assert.equal(
      metadata.description,
      "Prayer is speaking with God. It is the breath of the soul, and the Church teaches us to pray without ceasing, in the morning, at noon and at night."
    );
    const long = shareExcerpt(`${"Prayer is the breath of the soul [1]. ".repeat(10)}`);
    assert.ok(long.length <= 161, long);
    assert.ok(long.endsWith("…"), long);
    assert.doesNotMatch(long, /\[1\]/);
  });

  it("gives Open Graph and Twitter tags with the site's card image", () => {
    const metadata = sharedAnswerMetadata(snapshot);
    const og = metadata.openGraph as Record<string, unknown>;
    assert.equal(og.type, "article");
    assert.equal(og.title, "What is prayer?");
    assert.equal(og.url, "/s/Ab3dEfGh1jKlMn0p");
    assert.equal(og.locale, "en_US");
    assert.deepEqual(og.images, [OG_IMAGE]);
    assert.equal(OG_IMAGE.url, "/og-image.png");
    const twitter = metadata.twitter as Record<string, unknown>;
    assert.equal(twitter.card, "summary_large_image");
    assert.deepEqual(twitter.images, ["/og-image.png"]);
    assert.equal(sharedAnswerMetadata({ ...snapshot, language: "ar" }).openGraph?.locale, "ar_EG");
  });

  it("keeps shared pages out of search results", () => {
    assert.deepEqual(sharedAnswerMetadata(snapshot).robots, { index: false, follow: false });
    assert.deepEqual(sharedAnswerMetadata(snapshot).alternates, { canonical: "/s/Ab3dEfGh1jKlMn0p" });
  });

  it("shortens very long questions and leaves short answers whole", () => {
    const long = "Why ".repeat(40).trim() + "?";
    assert.ok(shareTitle(long).length <= 90);
    assert.ok(shareTitle(long).endsWith("…"));
    assert.equal(shareExcerpt("Short answer [1]."), "Short answer.");
  });

  it("leaves tables out of the excerpt unless the answer is only a table", () => {
    const table = "| Fast | Length |\n| --- | --- |\n| Great Lent | 55 days [1] |";
    assert.equal(shareExcerpt(`The main fasts [1]:\n\n${table}\n\nFasting goes with prayer [2].`), "The main fasts: Fasting goes with prayer.");
    assert.equal(shareExcerpt(table), "Fast Length Great Lent 55 days");
  });

  it("dates the answer in the snapshot's language", () => {
    assert.deepEqual(shareDate(snapshot), { iso: snapshot.answeredAt, text: "September 23, 2026" });
    assert.match(shareDate({ ...snapshot, language: "ar" }).text, /سبتمبر/);
    assert.equal(shareDate({ ...snapshot, answeredAt: null }).iso, snapshot.createdAt);
  });
});
