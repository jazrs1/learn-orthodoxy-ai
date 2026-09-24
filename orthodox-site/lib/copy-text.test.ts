import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { answerCopyText, markdownToPlainText } from "./copy-text.ts";

describe("copied answer as plain text (UI-031)", () => {
  it("drops Markdown marks but keeps lists, paragraphs and [n] citations", () => {
    const text = markdownToPlainText(
      "## Prayer\n\n**Prayer** is *the life* of the soul [1].\n\n* praise [2]\n* thanks [1, 3]\n\n1. first\n2. `second`"
    );
    assert.equal(text, "Prayer\n\nPrayer is the life of the soul [1].\n\n- praise [2]\n- thanks [1, 3]\n\n1. first\n2. second");
  });

  it("turns a table into rows of cells without its rule", () => {
    const text = markdownToPlainText("| Fast | Length |\n|---|:---:|\n| Great Lent | 55 days [1] |");
    assert.equal(text, "Fast | Length\nGreat Lent | 55 days [1]");
  });

  it("keeps a link's address", () => {
    assert.equal(markdownToPlainText("See [the Synaxarium](https://example.org/s) [2]."), "See the Synaxarium (https://example.org/s) [2].");
  });

  it("puts the question first and the numbered sources last", () => {
    const text = answerCopyText({
      question: " What is prayer? ",
      answer: "**Prayer** is speaking with God [1].",
      sources: [
        { n: 1, pdf: "catechism1.pdf", page: 31, pages: "31", title: "What is prayer?" },
        { n: 2, source_type: "website", url: "https://www.copticchurch.net/x", title: "Coptic Church" },
      ],
      language: "en",
      sourcesLabel: "Sources",
    });
    assert.equal(
      text,
      "What is prayer?\n\nPrayer is speaking with God [1].\n\nSources:\n" +
        "1. What is prayer?, Catechism of the Coptic Orthodox Church, Vol. 1 · p. 31\n" +
        "2. Coptic Church, copticchurch.net"
    );
  });

  it("leaves out the sources heading when there are none", () => {
    assert.equal(
      answerCopyText({ question: "", answer: "No passage covers this.", language: "en", sourcesLabel: "Sources" }),
      "No passage covers this."
    );
  });
});
