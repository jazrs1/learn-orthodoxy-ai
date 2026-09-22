/**
 * Writes lib/calendar/data/calendar-2026-2027.json from the rules in lib/calendar/rules.ts (CAL-002).
 * Run with `npm run calendar:generate`; commit the result. The site reads the JSON only.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { buildRange, RULES } from "../../lib/calendar/rules.ts";
import type { CalendarData } from "../../lib/calendar/types.ts";

const START = "2026-01-01";
const END = "2027-12-31";

const root = fileURLToPath(new URL("../../", import.meta.url));
const pkg = JSON.parse(readFileSync(`${root}node_modules/coptic-calendar/package.json`, "utf8")) as { version: string };

const data: CalendarData = {
  meta: {
    generatedBy: "scripts/calendar/generate-calendar.ts",
    library: `coptic-calendar@${pkg.version} (conversion and computus only)`,
    start: START,
    end: END,
    rules: RULES,
  },
  days: buildRange(START, END),
};

// One day per line keeps diffs readable when a rule changes.
const lines = data.days.map((day) => `    ${JSON.stringify(day)}`).join(",\n");
const json = `{\n  "meta": ${JSON.stringify(data.meta, null, 2).replace(/\n/g, "\n  ")},\n  "days": [\n${lines}\n  ]\n}\n`;
const out = `${root}lib/calendar/data/calendar-2026-2027.json`;
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, json);
console.log(`Wrote ${data.days.length} days to ${out}`);
