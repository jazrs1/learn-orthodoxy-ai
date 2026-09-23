/** The calendar page's month and URL handling (CAL-006). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { monthOptions, monthView, resolveSelection } from "./month.ts";
import { dayView } from "./view.ts";

describe("calendar page data", () => {
  test("offers the 24 months from January 2026 to December 2027", () => {
    const options = monthOptions();
    assert.equal(options.length, 24);
    assert.equal(options[0].value, "2026-01");
    assert.equal(options[23].value, "2027-12");
    assert.equal(options[8].label.en, "September 2026");
  });

  test("builds a month with its blanks, Coptic span and neighbours", () => {
    const september = monthView("2026-09");
    assert.equal(september.days.length, 30);
    assert.equal(september.leadingBlanks, 2); // 1 September 2026 is a Tuesday
    assert.equal(september.coptic.en, "Mesori 1742 – Thout 1743");
    assert.equal(september.previous, "2026-08");
    assert.equal(monthView("2026-01").previous, null);
    assert.equal(monthView("2027-12").next, null);
  });

  test("reads ?d= and ?m=, keeps dates inside the calendar, and ignores nonsense", () => {
    assert.deepEqual(resolveSelection({ d: "2027-05-01" }, "2026-09-22"), { date: "2027-05-01", requested: true, clamped: false });
    assert.deepEqual(resolveSelection({ m: "2026-12" }, "2026-09-22"), { date: "2026-12-01", requested: true, clamped: false });
    assert.deepEqual(resolveSelection({ d: "2030-01-01" }, "2026-09-22"), { date: "2027-12-31", requested: true, clamped: true });
    assert.deepEqual(resolveSelection({ d: "2026-02-30" }, "2026-09-22"), { date: "2026-09-22", requested: false, clamped: false });
    assert.deepEqual(resolveSelection({}, "2031-01-01"), { date: "2027-12-31", requested: false, clamped: false });
  });

  test("day cells get short titles without 'The Departure of' / 'نياحة'", () => {
    const view = dayView("2027-05-01")!;
    const george = view.commemorations.find((entry) => /George/.test(entry.name.en))!;
    assert.equal(george.short.en, "St. George Prince of the Martyrs");
    assert.ok(!george.short.ar!.startsWith("شهادة"));
  });

  test("names the weekly fast after the day", () => {
    assert.equal(dayView("2026-09-23")!.fast!.name.en, "Wednesday fast");
    assert.equal(dayView("2026-09-25")!.fast!.name.ar, "صوم الجمعة");
  });
});
