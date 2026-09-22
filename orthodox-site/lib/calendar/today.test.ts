/** The visitor's "today" (CAL-004). Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { localCalendarDate, localCalendarDateScript, possibleTodays } from "./today.ts";

describe("today", () => {
  test("midnight: the civil date on the visitor's clock", () => {
    assert.equal(localCalendarDate(new Date(2026, 8, 22, 23, 59), "midnight"), "2026-09-22");
    assert.equal(localCalendarDate(new Date(2026, 8, 23, 0, 0), "midnight"), "2026-09-23");
  });

  test("sunset: the next day from the approximate sunset hour", () => {
    assert.equal(localCalendarDate(new Date(2026, 8, 22, 17, 59), "sunset"), "2026-09-22");
    assert.equal(localCalendarDate(new Date(2026, 8, 22, 18, 0), "sunset"), "2026-09-23");
    assert.equal(localCalendarDate(new Date(2026, 11, 31, 20, 0), "sunset"), "2027-01-01");
  });

  test("the server's candidates always include the visitor's date, from UTC−12 to UTC+14", () => {
    for (const instant of ["2026-09-22T00:30:00Z", "2026-09-22T11:59:00Z", "2026-09-22T23:30:00Z"]) {
      const now = new Date(instant);
      for (let offsetHours = -12; offsetHours <= 14; offsetHours++) {
        const local = new Date(now.getTime() + offsetHours * 3_600_000).toISOString().slice(0, 10);
        assert.ok(possibleTodays(now, "midnight").includes(local), `${instant} at UTC${offsetHours}`);
      }
    }
  });

  test("the inline script computes the same date as the component", () => {
    const pick = new Function(`return (${localCalendarDateScript("midnight")})()`) as () => string;
    assert.equal(pick(), localCalendarDate(new Date(), "midnight"));
  });
});
