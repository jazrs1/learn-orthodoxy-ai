/** What of a half-written answer is shown (UI-026): tables only once complete. Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { plainAnswerText, streamView } from "./stream-markdown.ts";

const TABLE = [
  "Here are the fasts [1]:",
  "",
  "| Fast | Length |",
  "| --- | --- |",
  "| Great Lent | 55 days |",
  "| Apostles' Fast | varies |",
].join("\n");

describe("stream view: tables", () => {
  test("a table is held back at every point while it is written, and shown once text follows it", () => {
    for (let end = TABLE.indexOf("|") + 1; end <= TABLE.length; end += 1) {
      const view = streamView(TABLE.slice(0, end));
      assert.equal(view.tableHeld, true, `at ${end}`);
      assert.equal(view.text, "Here are the fasts [1]:", `at ${end}`);
      assert.ok(!view.text.includes("|"));
    }
    // A row just finished ("…|\n"): the next row may still come.
    assert.equal(streamView(`${TABLE}\n`).tableHeld, true);
    // A blank line or text after the table ends it.
    for (const after of ["\n\n", "\n\nThe longest", "\nThe longest"]) {
      const view = streamView(TABLE + after);
      assert.equal(view.tableHeld, false, JSON.stringify(after));
      assert.ok(view.text.includes("| Apostles' Fast | varies |"));
    }
  });

  test("the end of the stream shows the table", () => {
    assert.deepEqual(streamView(TABLE, true), { text: TABLE, tableHeld: false });
  });

  test("text before an earlier, finished table keeps showing while a second table is written", () => {
    const text = `${TABLE}\n\nAnd the feasts:\n\n| Feast | Date |\n| --- |`;
    const view = streamView(text);
    assert.equal(view.tableHeld, true);
    assert.ok(view.text.endsWith("And the feasts:"));
    assert.ok(view.text.includes("| Great Lent | 55 days |"));
  });

  test("a table at the very start is held without leaving anything behind", () => {
    assert.deepEqual(streamView("| Fast | Length |\n| --- |"), { text: "", tableHeld: true });
  });
});

describe("stream view: citations and bold", () => {
  test("a citation marker still being written is hidden; a finished one stays", () => {
    assert.equal(streamView("Prayer is talking with God [").text, "Prayer is talking with God");
    assert.equal(streamView("Prayer is talking with God [1").text, "Prayer is talking with God");
    assert.equal(streamView("Prayer is talking with God [1, 3").text, "Prayer is talking with God");
    assert.equal(streamView("الصلاة [1،").text, "الصلاة");
    assert.equal(streamView("Prayer is talking with God [1].").text, "Prayer is talking with God [1].");
  });

  test("a list item or heading whose text hasn't arrived isn't shown as an empty marker", () => {
    assert.equal(streamView("Kinds of prayer:\n\n1. Praise [1].\n2.").text, "Kinds of prayer:\n\n1. Praise [1].");
    assert.equal(streamView("Kinds of prayer:\n\n- ").text, "Kinds of prayer:");
    assert.equal(streamView("Intro.\n\n##").text, "Intro.");
    assert.equal(streamView("Kinds of prayer:\n\n2. Thanks").text, "Kinds of prayer:\n\n2. Thanks");
    // A number ending a sentence is not a list marker.
    assert.equal(streamView("Great Lent lasts 55").text, "Great Lent lasts 55");
  });

  test("open bold is closed so it doesn't flash as asterisks", () => {
    assert.equal(streamView("**St. Anth").text, "**St. Anth**");
    assert.equal(streamView("**St. Anthony**").text, "**St. Anthony**");
    assert.equal(streamView("Of **St. Anthony** and **").text, "Of **St. Anthony** and");
  });
});

describe("plain answer text for the screen-reader announcement", () => {
  test("drops citations, Markdown marks and table rules", () => {
    assert.equal(
      plainAnswerText("## Prayer\n\n**Prayer** is talking with God [1][2, 3].\n\n- Pray daily [4].\n\n| Fast | Days |\n| --- | --- |\n| Lent | 55 |"),
      "Prayer Prayer is talking with God. Pray daily. Fast Days Lent 55"
    );
    assert.equal(plainAnswerText("الصلاة هي حديث مع الله [1، 2]."), "الصلاة هي حديث مع الله.");
  });
});
