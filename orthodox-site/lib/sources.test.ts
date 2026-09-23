/** Source display for v1 and v2 answers (ING-005). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { sourceDetails, sourceSummary, toDisplaySources } from "./sources.ts";

describe("answer sources", () => {
  test("a v1 source shows the book, volume and PDF page as before", () => {
    const [source] = toDisplaySources([
      { source_type: "pdf", pdf: "catechism2.pdf", page: 31, n: 1, label: "Catechism of the Coptic Orthodox Church, Volume 2, p. 31" },
    ]);
    assert.equal(source.title, "Catechism of the Coptic Orthodox Church");
    assert.equal(sourceDetails(source, "en"), "Vol. 2 · p. 31");
    assert.equal(source.entry, undefined);
  });

  test("a v2 source shows the question and the printed pages, not the PDF page", () => {
    const [source] = toDisplaySources([
      { source_type: "pdf", pdf: "saints1.pdf", page: 43, pages: "33–35", entry: "St. Abanoub El-Nehissy", n: 2,
        chunk_id: "v2:sts1:saint:abanoub-el-nehissy:c2" },
    ]);
    assert.equal(sourceDetails(source, "en"), "Vol. 1 · pp. 33–35");
    // the range is isolated left-to-right so RTL layout does not show it as "35–33"
    assert.equal(sourceDetails(source, "ar"), `المجلد 1 · ص ${String.fromCharCode(0x2066)}33–35${String.fromCharCode(0x2069)}`);
    assert.equal(sourceSummary(source, "ar").split("، ").length, 3);
    assert.equal(sourceSummary(source, "en"), "St. Abanoub El-Nehissy, Encyclopedia of the Saints and Fathers of the Church, Vol. 1 · pp. 33–35");
  });

  test("two passages from the same page stay two sources", () => {
    const sources = toDisplaySources([
      { source_type: "pdf", pdf: "saints1.pdf", page: 33, pages: "33", entry: "St. Abadion", n: 1, chunk_id: "a" },
      { source_type: "pdf", pdf: "saints1.pdf", page: 33, pages: "33", entry: "St. Abamon", n: 2, chunk_id: "b" },
    ]);
    assert.deepEqual(sources.map((s) => [s.n, s.entry, sourceDetails(s, "en")]), [
      [1, "St. Abadion", "Vol. 1 · p. 33"],
      [2, "St. Abamon", "Vol. 1 · p. 33"],
    ]);
  });

  test("a v2 web source names its section", () => {
    const [source] = toDisplaySources([
      { source_type: "website", url: "https://www.mindofchristlight.com/x", title: "GOD", entry: "4. He Has God's Characteristics", n: 1 },
    ]);
    assert.equal(source.kind, "website");
    assert.equal(source.entry, "4. He Has God's Characteristics");
    assert.equal(sourceDetails(source, "en"), "mindofchristlight.com");
  });
});
