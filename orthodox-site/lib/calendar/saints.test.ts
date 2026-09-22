/**
 * Saint data tests (CAL-003): the 15 sample days from CAL-001, the Pashons 24 check, and the
 * integrity of the source record and index links. Run with `npm test`.
 */

import assert from "node:assert/strict";
import { describe, test } from "node:test";
import saintsJson from "./data/saints.katameros.json" with { type: "json" };
import snapshotJson from "../../scripts/calendar/saints-index.snapshot.json" with { type: "json" };
import { commemorationsFor } from "./calendar.ts";
import { dayView } from "./view.ts";
import type { SaintsData } from "./types.ts";

const saints = saintsJson as SaintsData;
const snapshot = snapshotJson as { en: Array<{ name: string }>; ar: string[] };
const titles = (key: string) => (saints.days[key] ?? []).map((entry) => entry.en);

/** CAL-001's sample days: the saints the .ics lists (and Katameros confirmed), by English title. */
const SAMPLE_DAYS: Record<string, RegExp[]> = {
  "1-1": [/Bartholomew/, /Righteous Job/, /Milius/, /Mark\) the Fifth/],
  "1-26": [/Zacharias the Priest with the Birth of John the Baptist/],
  "2-12": [/Demetrius I/, /Archangel Michael/, /Matthew the Evangelist/],
  "3-12": [/Archangel Michael/, /John \(Youhanna\), the Syrian/],
  "3-27": [/James the Persian/, /Victor Ebn-Romanus/],
  "4-29": [/Martyrs of Akhmeem/],
  "5-11": [/Youannes \(John\) VI/, /Benjamin II/],
  "6-8": [/Simeon the Elder/],
  "7-29": [/Resurrection of the Lord Christ/],
  "8-23": [/George Prince of the Martyrs/],
  "9-24": [/Entrance of the Lord Christ into Egypt/, /Habakkuk/, /Bashnouna/],
  "10-12": [/Kyrillos II/, /Justus, 6th Patriarch/, /Archangel Michael/, /Euphemia/],
  "11-5": [/Peter and Paul/, /Marcus, governor of el-Borolus/],
  "12-16": [/Assumption/, /Matthew IV/],
  "13-3": [/Archangel Raphael/, /Andrianus/, /Yoannis XIV/],
};

describe("the 15 sample days from CAL-001", () => {
  for (const [key, expected] of Object.entries(SAMPLE_DAYS)) {
    test(`Coptic ${key}`, () => {
      for (const pattern of expected) {
        assert.ok(titles(key).some((title) => pattern.test(title)), `${key} should list ${pattern}`);
      }
    });
  }
});

describe("Pashons 24 (1 June)", () => {
  test("shows the Entry of the Lord into Egypt, not Simon the Stylite", () => {
    assert.ok(titles("9-24").some((title) => /Entrance of the Lord Christ into Egypt/.test(title)));
    assert.ok(!titles("9-24").some((title) => /Stylite/.test(title)));
    // Simon the Stylite is commemorated on Pashons 29.
    assert.ok(titles("9-29").some((title) => /Simon the Stylite/.test(title)));
  });

  test("the calendar page gets the feast from the rules and the saints without repeating it", () => {
    for (const iso of ["2026-06-01", "2027-06-01"]) {
      const view = dayView(iso)!;
      assert.ok(view.observances.some((o) => o.id === "entry-into-egypt"));
      assert.ok(!view.commemorations.some((c) => /into Egypt/.test(c.name.en)));
      assert.ok(view.commemorations.some((c) => /Habakkuk/.test(c.name.en)));
    }
  });
});

describe("the saints file", () => {
  test("records its source and the commit it was taken from", () => {
    assert.equal(saints.source.name, "Katameros");
    assert.match(saints.source.commit, /^[0-9a-f]{40}$/);
    assert.equal(saints.source.repository, "https://github.com/pierresaid/katameros-api");
  });

  test("covers all 366 Coptic days", () => {
    assert.equal(Object.keys(saints.days).length, 366);
  });

  test("has English and Arabic for every entry but one (Habib Girgis has no Arabic title)", () => {
    const missing = Object.values(saints.days).flat().filter((entry) => !entry.ar);
    assert.equal(missing.length, 1);
    assert.match(missing[0].en, /Habib Girgis/);
  });

  test("keeps titles only", () => {
    for (const entry of Object.values(saints.days).flat()) {
      assert.ok(entry.en.length < 260, `${entry.id} looks like a story, not a title`);
      assert.deepEqual(Object.keys(entry).sort(), Object.keys(entry).filter((k) => ["id", "kind", "en", "ar", "index"].includes(k)).sort());
    }
  });

  test("links only to names that exist in the saints index snapshot", () => {
    const english = new Set(snapshot.en.map((record) => record.name));
    const arabic = new Set(snapshot.ar);
    for (const entry of Object.values(saints.days).flat()) {
      if (entry.index?.en) assert.ok(english.has(entry.index.en), entry.index.en);
      if (entry.index?.ar) assert.ok(arabic.has(entry.index.ar), entry.index.ar);
      if (entry.index) assert.equal(entry.kind, "saint", `${entry.id} links but is not a saint`);
    }
  });

  test("links the well-known saints checked by hand", () => {
    const find = (key: string, pattern: RegExp) => saints.days[key].find((entry) => pattern.test(entry.en))!;
    assert.deepEqual(find("8-23", /George/).index, { en: "St. George, the Capaducian", ar: "القديس جرجس" });
    assert.deepEqual(find("5-21", /Virgin St. Mary/).index, { en: "St. Mary", ar: "السيدة العذراء مريم" });
    assert.equal(find("10-12", /Kyrillos II/).index?.ar, "كيرلس الثاني البابا السابع والستين");
    assert.equal(find("10-12", /Euphemia/).index, undefined, "two Euphemias: no automatic link");
  });

  test("puts the day's saints before monthly commemorations and events", () => {
    const order = commemorationsFor({ year: 1743, month: 2, day: 12 }).map((entry) => entry.kind);
    assert.deepEqual(order, ["saint", "saint", "monthly"]);
  });
});
