/** Namesake menus in the frontend (RET-010): a saint choice keeps its entry ID from the backend's
 * reply, through the saved conversation, to the request the chip sends. Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  backendSaintSelection,
  decodeStoredOptions,
  encodeStoredOptions,
  namesakesFromBackend,
  namesakesRequest,
  optionsFromBackend,
  saintSelectionRequest,
  visibleMessageOptions,
} from "./message-options.ts";

const ENGLISH_MENU = {
  answer: "I found multiple saints matching 'St. Athanasius'. Choose one option below.",
  options: [
    "St. Athanasius the Apostolic, the 20th Pope of Alexandria",
    "St. Athanasius (The martyr, vol. 1, p. 269)",
    "St. Athanasius, the Saint (vol. 1, p. 269)",
  ],
  option_ids: ["athanasius-the-apostolic-the-20th-pope-of-alexandria", "athanasius", "athanasius-the-saint"],
};

const ARABIC_MENU = {
  answer: "وجدت أكثر من قديس يطابق 'القديس أغاثون'. اختر واحدًا من الخيارات أدناه.",
  options: ["أغاثون الشهيد", "أغاثون القديس", "أغاثون البابا التاسع والثلاثون", "أغاثون العمودي القديس"],
  option_ids: ["ar-e1622", "agathon-2", "agathon-the-39th-pope", "agathon-the-stylite"],
};

const noLookup = () => false;

/** Reply -> saved message -> reloaded message -> chips, as the route, the database and the page do. */
function chipsAfterReload(reply: { options: string[]; option_ids: string[] }) {
  const { options, optionIds } = optionsFromBackend(reply);
  const stored = JSON.parse(JSON.stringify(encodeStoredOptions(options, optionIds)));
  const reloaded = decodeStoredOptions(stored);
  return visibleMessageOptions(reloaded.options, reloaded.optionIds, noLookup);
}

describe("namesake menus", () => {
  test("an English menu choice sends the entry's ID, and the full name with its comma stays whole", () => {
    const chips = chipsAfterReload(ENGLISH_MENU);
    assert.deepEqual(
      chips.map((chip) => chip.saintId),
      ["athanasius-the-apostolic-the-20th-pope-of-alexandria", "athanasius", "athanasius-the-saint"]
    );
    const request = saintSelectionRequest(chips[0], "en");
    assert.equal(request.question, "search saint: St. Athanasius the Apostolic, the 20th Pope of Alexandria");
    assert.equal(request.mode, "saints");
    assert.deepEqual(backendSaintSelection(request), { saint_id: "athanasius-the-apostolic-the-20th-pope-of-alexandria" });
  });

  test("an Arabic menu choice sends the entry's ID", () => {
    const chips = chipsAfterReload(ARABIC_MENU);
    assert.equal(chips.length, 4);
    const stylite = chips.find((chip) => chip.label === "أغاثون العمودي القديس");
    assert.ok(stylite);
    const request = saintSelectionRequest(stylite, "ar");
    assert.equal(request.question, "من هو أغاثون العمودي القديس؟");
    assert.deepEqual(backendSaintSelection(request), { saint_id: "agathon-the-stylite" });
  });

  test("two namesakes with the same label stay two choices with their own IDs", () => {
    const chips = chipsAfterReload({ options: ["St. Agathon", "St. Agathon"], option_ids: ["agathon", "agathon-2"] });
    assert.deepEqual(chips.map((chip) => chip.saintId), ["agathon", "agathon-2"]);
  });

  test("a menu saved before IDs existed selects by exact name, never by the matcher", () => {
    const reloaded = decodeStoredOptions(["St. Gregory of Nyssa", "St. Gregory, the Monk"]);
    const chips = visibleMessageOptions(reloaded.options, reloaded.optionIds, () => true);
    assert.deepEqual(chips, [{ label: "St. Gregory of Nyssa" }, { label: "St. Gregory, the Monk" }]);
    assert.deepEqual(backendSaintSelection(saintSelectionRequest(chips[1], "en")), { saint_name: "St. Gregory, the Monk" });
  });

  test("follow-up questions stay questions and carry no ID", () => {
    const reloaded = decodeStoredOptions(encodeStoredOptions(["What is fasting?", "How do I pray?"], []));
    const chips = visibleMessageOptions(reloaded.options, reloaded.optionIds, noLookup);
    assert.deepEqual(chips, [{ label: "What is fasting?" }, { label: "How do I pray?" }]);
  });

  test("a reply without option_ids keeps its options and no IDs", () => {
    assert.deepEqual(optionsFromBackend({ options: ["A?", 7, "B?"] }), { options: ["A?", "B?"], optionIds: ["", ""] });
    assert.deepEqual(backendSaintSelection({}), {});
  });

  test("the namesakes link survives the saved conversation and asks for the other saints (RET-011)", () => {
    const reply = {
      answer: "St. Mary, the Theotokos … [1]",
      options: [],
      namesakes: { label: "Looking for a different St. Mary?", name: "St. Mary" },
    };
    const link = namesakesFromBackend(reply);
    assert.deepEqual(link, { label: "Looking for a different St. Mary?", name: "St. Mary" });
    const stored = JSON.parse(JSON.stringify(encodeStoredOptions([], [], link)));
    const reloaded = decodeStoredOptions(stored);
    assert.deepEqual(reloaded, { options: [], optionIds: [], namesakes: link });
    // The link is not a chip.
    assert.deepEqual(visibleMessageOptions(reloaded.options, reloaded.optionIds, () => true), []);
    const request = namesakesRequest(reloaded.namesakes!);
    assert.equal(request.question, "Looking for a different St. Mary?");
    assert.deepEqual(backendSaintSelection(request), { namesakes_of: "St. Mary" });
  });

  test("an Arabic namesakes link, and replies without one", () => {
    const link = namesakesFromBackend({ namesakes: { label: "هل تبحث عن قديس آخر باسم مرقس؟", name: "مرقس" } });
    assert.deepEqual(backendSaintSelection(namesakesRequest(link!)), { namesakes_of: "مرقس" });
    assert.equal(namesakesFromBackend({}), undefined);
    assert.equal(namesakesFromBackend({ namesakes: null }), undefined);
    assert.equal(namesakesFromBackend({ namesakes: { label: "", name: "x" } }), undefined);
    // A menu choice's ID wins over everything else.
    assert.deepEqual(backendSaintSelection({ saintId: "marcus-the-apostle", namesakesOf: "مرقس" }), { saint_id: "marcus-the-apostle" });
  });
});
