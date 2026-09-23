/** The Today line's short saint names (UI-018). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { briefName } from "./brief.ts";
import { dayView } from "./view.ts";

describe("brief commemoration names", () => {
  test("13 Thout 1743 (23 September 2026): Pope Mettaos II", () => {
    const day = dayView("2026-09-23")!;
    assert.equal(day.coptic.label.en, "13 Thout 1743");
    assert.equal(briefName(day.commemorations[0].short.en, "en"), "Pope Mettaos II");
    assert.equal(briefName(day.commemorations[0].short.ar!, "ar"), "البابا متاؤس الثانى");
  });

  test("keeps a name that has no comma or parentheses", () => {
    assert.equal(briefName("St. George Prince of the Martyrs", "en"), "St. George Prince of the Martyrs");
    assert.equal(briefName("القديس مرقس الرسول", "ar"), "القديس مرقس الرسول");
  });

  test("cuts at the Arabic comma and drops parentheses", () => {
    assert.equal(briefName("القديس يوحنا (يوأنس)، أسقف أورشليم", "ar"), "القديس يوحنا");
    assert.equal(briefName("St. Anthony (Antonius), the Father of the Monks", "en"), "St. Anthony");
  });

  test("never returns an empty name", () => {
    assert.equal(briefName("(Unknown)", "en"), "(Unknown)");
  });
});
