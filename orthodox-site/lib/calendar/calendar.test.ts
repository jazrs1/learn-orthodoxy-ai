/**
 * Calendar data tests (CAL-002). Run with `npm test`.
 * The SUS table is the reference for every feast and fast date in 2026 and 2027.
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { describe, test } from "node:test";
import calendarJson from "./data/calendar-2026-2027.json" with { type: "json" };
import sus from "./fixtures/sus-2026-2027.json" with { type: "json" };
import { COPTIC_MONTHS } from "./coptic-months.ts";
import { addDays, weekday } from "./dates.ts";
import type { ObservanceId } from "./observances.ts";
import { buildDay, buildRange, fromCoptic, paschaOf, toCoptic } from "./rules.ts";
import type { CalendarData, CalendarDay } from "./types.ts";

const data = calendarJson as CalendarData;
const byDate = new Map(data.days.map((day) => [day.date, day]));
/** Days inside the generated range come from the file; the few after it (Jan 2028) from the rules. */
const dayAt = (iso: string): CalendarDay => byDate.get(iso) ?? buildDay(iso);

function* each(start: string, end: string) {
  for (let iso = start; iso <= end; iso = addDays(iso, 1)) yield iso;
}

describe("the generated file", () => {
  test("covers Jan 2026 – Dec 2027, one entry per day", () => {
    assert.equal(data.days[0].date, "2026-01-01");
    assert.equal(data.days.at(-1)!.date, "2027-12-31");
    assert.equal(data.days.length, 730);
  });

  test("is up to date with the rules (run `npm run calendar:generate` if this fails)", () => {
    assert.deepEqual(data.days, buildRange("2026-01-01", "2027-12-31"));
  });
});

describe("every feast and fast matches the SUS table", () => {
  for (const row of sus.rows) {
    const id = row.id as ObservanceId;
    const end = row.end ?? row.start;
    test(`${row.start.slice(0, 4)} ${row.sus}: ${row.start}${row.end ? ` – ${row.end}` : ""}`, () => {
      for (const iso of each(row.start, end)) {
        const day = dayAt(iso);
        if (row.type === "fast") assert.equal(day.fast, id, `${iso} should be in ${id}`);
        else if (row.type === "feast") assert.ok(day.observances.includes(id), `${iso} should keep ${id}`);
        else {
          assert.ok(!day.observances.includes(id), `${iso} should not celebrate ${id}`);
          assert.ok(day.suppressed.includes(id), `${iso} should say ${id} is not celebrated`);
        }
      }
      if (row.type === "fast") {
        assert.notEqual(dayAt(addDays(row.start, -1)).fast, id, `${id} starts on ${row.start}`);
        assert.notEqual(dayAt(addDays(end, 1)).fast, id, `${id} ends on ${end}`);
      }
    });
  }
});

describe("the four rules from CAL-001", () => {
  for (const year of [2026, 2027]) {
    const pascha = paschaOf(year);

    test(`${year} rule 1: Great Lent ends the Friday before Lazarus Saturday`, () => {
      const lastDay = addDays(pascha, -9);
      assert.equal(weekday(lastDay), 5);
      assert.equal(dayAt(lastDay).fast, "great-lent");
      assert.equal(dayAt(addDays(lastDay, 1)).fast, "holy-week-fast");
      assert.ok(dayAt(addDays(lastDay, 1)).observances.includes("lazarus-saturday"));
    });

    test(`${year} rule 2: Lazarus Saturday and the Holy Pascha days are listed`, () => {
      const expected: Array<[number, ObservanceId]> = [
        [-8, "lazarus-saturday"],
        [-7, "palm-sunday"],
        [-6, "holy-monday"],
        [-5, "holy-tuesday"],
        [-4, "holy-wednesday"],
        [-3, "covenant-thursday"],
        [-2, "good-friday"],
        [-1, "joyous-saturday"],
      ];
      for (const [offset, id] of expected) assert.ok(dayAt(addDays(pascha, offset)).observances.includes(id), id);
    });
  }

  test("rule 3: the Annunciation is not celebrated in Holy Week (2026) and is in Lent (2027)", () => {
    assert.deepEqual(dayAt("2026-04-07").suppressed, ["annunciation"]);
    assert.ok(!dayAt("2026-04-07").observances.includes("annunciation"));
    assert.ok(dayAt("2027-04-07").observances.includes("annunciation"));
    assert.deepEqual(dayAt("2027-04-07").suppressed, []);
    // No other day in the range suppresses anything.
    assert.deepEqual(
      data.days.filter((day) => day.suppressed.length).map((day) => day.date),
      ["2026-04-07"]
    );
  });

  test("rule 4: the Nativity stays on January 7 after a Coptic leap year", () => {
    // Coptic 1743 is a leap year, so in 1744 Kiahk 29 falls on 8 January 2028.
    assert.deepEqual(toCoptic("2028-01-08"), { year: 1744, month: 4, day: 29 });
    assert.ok(buildDay("2028-01-07").observances.includes("nativity"));
    assert.ok(buildDay("2028-01-08").observances.includes("nativity"));
    assert.equal(buildDay("2028-01-06").fast, "nativity-fast");
    assert.equal(buildDay("2028-01-07").fast, null);
    // In an ordinary year only 7 January is the Nativity.
    assert.ok(dayAt("2027-01-07").observances.includes("nativity"));
    assert.ok(!dayAt("2027-01-08").observances.includes("nativity"));
    assert.ok(!dayAt("2026-01-08").observances.includes("nativity"));
  });
});

describe("Wednesday and Friday fasts", () => {
  test("kept on ordinary Wednesdays and Fridays", () => {
    assert.equal(dayAt("2026-09-23").fast, "wednesday-friday");
    assert.equal(dayAt("2026-09-25").fast, "wednesday-friday");
    assert.equal(dayAt("2026-09-24").fast, null);
  });

  test("not kept in the Holy Fifty or from the Nativity to Theophany", () => {
    for (const iso of each("2026-04-12", "2026-05-31")) {
      assert.equal(dayAt(iso).fastFree, "holy-fifty", iso);
      assert.equal(dayAt(iso).fast, null, iso);
    }
    for (const iso of each("2027-01-07", "2027-01-19")) {
      assert.equal(dayAt(iso).fastFree, "nativity-to-theophany", iso);
      assert.equal(dayAt(iso).fast, null, iso);
    }
  });
});

describe("Gregorian ↔ Coptic conversion", () => {
  const cases: Array<[string, number, number, number]> = [
    ["2026-09-11", 1743, 1, 1], // Nayrouz 1743
    ["2027-09-11", 1743, 13, 6], // 1743 is a leap year: Nasie has 6 days
    ["2027-09-12", 1744, 1, 1], // so Thout 1 moves to 12 September
    ["2025-09-11", 1742, 1, 1],
    ["2023-09-12", 1740, 1, 1],
    ["2027-01-07", 1743, 4, 29],
    ["2026-06-01", 1742, 9, 24], // Pashons 24, the Entry into Egypt
  ];
  for (const [iso, year, month, day] of cases) {
    test(`${iso} = ${day}/${month}/${year} and back`, () => {
      assert.deepEqual(toCoptic(iso), { year, month, day });
      assert.equal(fromCoptic(year, month, day), iso);
    });
  }

  test("consecutive days advance the Coptic date by one, with 30-day months and a 5- or 6-day Nasie", () => {
    let previous = data.days[0].coptic;
    for (const day of data.days.slice(1)) {
      const { year, month, day: d } = day.coptic;
      const nasieLength = previous.year % 4 === 3 ? 6 : 5;
      const monthLength = previous.month === 13 ? nasieLength : 30;
      if (previous.day < monthLength) assert.deepEqual(day.coptic, { ...previous, day: previous.day + 1 }, day.date);
      else if (previous.month < 13) assert.deepEqual({ year, month, day: d }, { year: previous.year, month: previous.month + 1, day: 1 }, day.date);
      else assert.deepEqual({ year, month, day: d }, { year: previous.year + 1, month: 1, day: 1 }, day.date);
      previous = day.coptic;
    }
  });

  test("the generated calendar is the same in every time zone", () => {
    const script = `import { buildRange } from "./lib/calendar/rules.ts"; process.stdout.write(JSON.stringify(buildRange("2026-01-01", "2027-12-31")));`;
    const expected = JSON.stringify(buildRange("2026-01-01", "2027-12-31"));
    for (const timeZone of ["Pacific/Auckland", "Africa/Cairo", "America/Los_Angeles", "Pacific/Kiritimati", "Etc/GMT+12"]) {
      const output = execFileSync(
        process.execPath,
        ["--disable-warning=MODULE_TYPELESS_PACKAGE_JSON", "--input-type=module", "-e", script],
        { env: { ...process.env, TZ: timeZone }, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 }
      );
      assert.equal(output, expected, timeZone);
    }
  });

  test("month names follow coptic-calendar (Arabic Nasie spelled نسيء)", () => {
    const root = new URL("../../node_modules/coptic-calendar/dist/core/locales/", import.meta.url);
    const en = JSON.parse(readFileSync(new URL("en.json", root), "utf8")) as Record<string, string>;
    const ar = JSON.parse(readFileSync(new URL("ar.json", root), "utf8")) as Record<string, string>;
    assert.deepEqual(COPTIC_MONTHS.en, Object.values(en));
    assert.deepEqual(COPTIC_MONTHS.ar.slice(0, 12), Object.values(ar).slice(0, 12));
    assert.equal(COPTIC_MONTHS.ar[12], "نسيء");
  });
});
