/**
 * Extracts the English and Arabic synaxarium titles from a local clone of the Katameros API
 * repository into lib/calendar/data/saints.katameros.json (CAL-003). Titles only; the stories
 * are never read. Also links titles to our saints index where the match is unambiguous.
 *
 *   git clone https://github.com/pierresaid/katameros-api
 *   npm run calendar:saints -- <path-to-katameros-api>
 *
 * The site never talks to Katameros; it reads the JSON written here.
 */

import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import type { Commemoration, CommemorationKind, SaintsData } from "../../lib/calendar/types.ts";

const repo = process.argv[2];
if (!repo) {
  console.error("Usage: npm run calendar:saints -- <path-to-katameros-api clone>");
  process.exit(1);
}

const here = fileURLToPath(new URL(".", import.meta.url));
const root = fileURLToPath(new URL("../../", import.meta.url));
const DB_PATH = "Core/KatamerosDatabase.db";
const ENGLISH = 2;
const ARABIC = 3;

const commit = execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
const db = new DatabaseSync(join(repo, DB_PATH), { readOnly: true });
const rows = db
  .prepare(
    `SELECT Month AS month, Day AS day, "Order" AS position, Title AS title, LanguageId AS language, StoryId AS story
     FROM Synaxarium WHERE LanguageId IN (${ENGLISH}, ${ARABIC}) ORDER BY Month, Day, "Order"`
  )
  .all() as Array<{ month: number; day: number; position: number; title: string; language: number; story: number }>;

// ---------- Kind: saint, monthly commemoration, event, or a feast we already compute ----------

/** Synaxarium entries that are the feasts lib/calendar/rules.ts already marks, by Coptic day. */
const FEAST_TITLES: Record<string, RegExp> = {
  "1-1": /Nayrouz/i,
  "1-17": /Honorable Cross/i,
  "1-18": /Feast of the Cross/i,
  "1-19": /Feast of the Cross/i,
  "4-29": /Birth of Our Lord/i,
  "5-6": /Feast of Circumcision/i,
  "5-11": /Theophany Feast/i,
  "5-13": /Wedding at Cana/i,
  "6-8": /Presenting the Lord/i,
  "7-10": /Appearance of the Honorable Cross/i,
  "7-29": /Glorious Annunciation/i,
  "9-24": /Entrance of the Lord Christ into Egypt/i,
  "12-13": /Transfiguration/i,
  "12-16": /Assumption/i,
};

/** Monthly commemorations: Michael on the 12th, the Virgin on the 21st, the three feasts on the 29th. */
function isMonthly(month: number, day: number, title: string): boolean {
  if (day === 12 && /Archangel Michael|Michael, the Archangel/i.test(title)) return month !== 3 && month !== 10;
  if (day === 21 && /^The Commemoration of (the )?(Holy and )?(Pure |Lady, the )?(Virgin|Theotokos)/i.test(title)) return true;
  if (day === 29 && /Three Major Feasts/i.test(title)) return true;
  return false;
}

const EVENT =
  /^(the |a )?(consecration|relocation|translocation|assembly|appearance|return|apparition|arrival|discovery|raid|paramoun|paramouni|grand opening|adoration|second day|third day|beginning|inauguration|first pontifical|receiving|visit|council|thanksgiving|coming|revealing of the virginity)\b|^(the )?commemoration of (the )?(assembly|miracle|celebration|consecration|relocation|appearance|crucifixion|resurrection|raising|ascension|feast|second universal|opening|first church|sign|great sign|reign)\b/i;

function kindOf(month: number, day: number, title: string): CommemorationKind {
  if (FEAST_TITLES[`${month}-${day}`]?.test(title)) return "feast";
  if (isMonthly(month, day, title)) return "monthly";
  if (EVENT.test(title.trim())) return "event";
  return "saint";
}

// ---------- Links to our saints index ----------

type IndexSnapshot = { taken: string; en: Array<{ name: string; aliases: string[] }>; ar: string[]; ar_aliases?: Record<string, string[]> };
const snapshot = JSON.parse(readFileSync(join(here, "saints-index.snapshot.json"), "utf8")) as IndexSnapshot;
const overrides = JSON.parse(readFileSync(join(here, "saint-link-overrides.json"), "utf8")) as {
  links: Record<string, { en?: string | null; ar?: string | null; why: string }>;
};

const EN_STOP = new Set(["st", "sts", "saint", "saints", "the", "of", "a", "an", "and", "in", "at", "to", "pope", "abba", "anba", "apa", "holy"]);
/** Words that describe a person rather than name them; a link needs at least one real name word. */
const EN_DESCRIPTORS = new Set(
  "apostle martyr prophet bishop monk hermit priest deacon archdeacon confessor ascetic anchorite virgin soldier prince great elder patriarch metropolitan hegomen father mother one twelve seventy disciple evangelist righteous just upright blessed ethiopian syrian persian roman egyptian first second third alexandria rome antioch jerusalem constantinople".split(" ")
);

function enTokens(value: string): string[] {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/\(.*?\)/g, " ")
    .replace(/\bkyrillos\b/g, "cyril")
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .map((token) => (token.length > 4 && token.endsWith("s") ? token.slice(0, -1) : token))
    .filter((token) => token && !EN_STOP.has(token));
}

const EN_EVENT_PREFIX = /^(the )?(martyrdom|departure|repose|commemoration|martyrdom)( of)?( the)?\s+/i;

const AR_STOP = new Set(["القديس", "القديسه", "القديسين", "القديسان", "البابا", "الانبا", "انبا", "ابا", "من", "في", "و", "مار", "الشهيد", "الشهيده", "الشهداء"]);
const AR_DESCRIPTORS = new Set(
  "الرسول الرسل النبي الاسقف الراهب الناسك السائح المعترف العظيم البطريرك الكبير الصديق البار المتوحد القس الشماس رئيس الملاك البتول العذراء الجليل بطاركه الكرازه المرقسيه الاول الثاني الثالث".split(" ")
);

function normalizeArabic(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/[ً-ٰٟـ]/g, "")
    .replace(/[أإآ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي");
}

function arTokens(value: string): string[] {
  return normalizeArabic(value)
    .replace(/[^ء-ي0-9 ]+/g, " ")
    .split(/\s+/)
    // "الثامن والتسعين" and "الثامن والتسعون" are the same number in different cases.
    .map((token) => token.replace(/ون$/, "ين"))
    .filter((token) => token && !AR_STOP.has(token));
}

const AR_EVENT_PREFIX = /^(نياحه|استشهاد|شهاده|تذكار)\s+/;

type Candidate = { name: string; tokens: string[] };
const enCandidates: Candidate[] = snapshot.en.flatMap((record) =>
  [record.name, ...record.aliases].map((alias) => ({ name: record.name, tokens: enTokens(alias) }))
);
// A v2 snapshot also carries Arabic aliases (the index's full names, e.g. "مرقس الخامس البابا الثامن
// والتسعون" for the dictionary heading "مرقس الخامس"); a match on an alias links to the heading (ING-008).
const arCandidates: Candidate[] = snapshot.ar.flatMap((name) =>
  [name, ...(snapshot.ar_aliases?.[name] ?? [])].map((alias) => ({ name, tokens: arTokens(alias) }))
);

const EN_NUMERAL = /^(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx|[0-9]+(st|nd|rd|th)?)$/;
const AR_NUMERAL = /^(ال|و)?(اول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر|حادي|عشر|عشرين|ثلاثين|اربعين|خمسين|ستين|سبعين|ثمانين|تسعين|مايه|المايه|[0-9]+)$/;

function firstName(tokens: string[], descriptors: Set<string>): string | undefined {
  return tokens.find((token) => !descriptors.has(token));
}

/** Index entries per first name word; a one-word name is only trusted when it is unique. */
function firstNameCounts(candidates: Candidate[], descriptors: Set<string>) {
  const names = new Map<string, Set<string>>();
  for (const candidate of candidates) {
    const first = firstName(candidate.tokens, descriptors);
    if (first) names.set(first, (names.get(first) ?? new Set()).add(candidate.name));
  }
  return names;
}
const enFirstNames = firstNameCounts(enCandidates, EN_DESCRIPTORS);
const arFirstNames = firstNameCounts(arCandidates, AR_DESCRIPTORS);

/**
 * The index entry for a title, or nothing. Conservative on purpose (CAL-003): a wrong link is
 * worse than none. The entry's words must all appear in the title; both must start with the same
 * name; a pope number in the title must be in the entry too; a two-word entry must cover at least
 * half the title's words, a one-word entry all of them and be the only entry with that name.
 */
function bestMatch(
  titleTokens: string[],
  candidates: Candidate[],
  descriptors: Set<string>,
  numeral: RegExp,
  firstNames: Map<string, Set<string>>,
  titleFirstNames: Map<string, number>
): string | undefined {
  const title = new Set(titleTokens);
  const titleFirst = firstName(titleTokens, descriptors);
  const titleNumerals = titleTokens.filter((token) => numeral.test(token));
  let best: { name: string; score: number } | undefined;
  let tied = false;
  for (const candidate of candidates) {
    const tokens = new Set(candidate.tokens);
    const first = firstName(candidate.tokens, descriptors);
    if (!first || first !== titleFirst) continue;
    if (![...tokens].every((token) => title.has(token))) continue;
    if (!titleNumerals.every((token) => tokens.has(token))) continue;
    const score = tokens.size / new Set([...title, ...tokens]).size;
    // "Timothy, the Bishop" only says which Timothy when it is the index's only Timothy and the
    // synaxarium's only Timothy; otherwise it must match the title word for word.
    const onlyDescribed = [...tokens].every((token) => token === first || descriptors.has(token));
    const uniqueName = (firstNames.get(first)?.size ?? 0) === 1 && (titleFirstNames.get(first) ?? 0) === 1;
    if (score < 0.5) continue;
    if (onlyDescribed && score < 1 && !uniqueName) continue;
    if (tokens.size === 1 && (score < 1 || !uniqueName)) continue;
    if (!best || score > best.score) {
      best = { name: candidate.name, score };
      tied = false;
    } else if (score === best.score && candidate.name !== best.name) {
      tied = true;
    }
  }
  return best && !tied ? best.name : undefined;
}

/** How many synaxarium saints start with each name word; filled once the titles are read. */
const enTitleFirstNames = new Map<string, number>();
const arTitleFirstNames = new Map<string, number>();

function countTitleFirstNames(titles: Array<{ en: string; ar?: string }>) {
  for (const { en, ar } of titles) {
    const enFirst = firstName(enTokens(en.replace(EN_EVENT_PREFIX, "")), EN_DESCRIPTORS);
    if (enFirst) enTitleFirstNames.set(enFirst, (enTitleFirstNames.get(enFirst) ?? 0) + 1);
    const arFirst = ar ? firstName(arTokens(normalizeArabic(ar).replace(AR_EVENT_PREFIX, "")), AR_DESCRIPTORS) : undefined;
    if (arFirst) arTitleFirstNames.set(arFirst, (arTitleFirstNames.get(arFirst) ?? 0) + 1);
  }
}

function autoLink(kind: CommemorationKind, en: string, ar: string | undefined) {
  if (kind !== "saint") return {};
  return {
    en: bestMatch(enTokens(en.replace(EN_EVENT_PREFIX, "")), enCandidates, EN_DESCRIPTORS, EN_NUMERAL, enFirstNames, enTitleFirstNames),
    ar: ar
      ? bestMatch(arTokens(normalizeArabic(ar).replace(AR_EVENT_PREFIX, "")), arCandidates, AR_DESCRIPTORS, AR_NUMERAL, arFirstNames, arTitleFirstNames)
      : undefined,
  };
}

function checkKnown(story: number, language: string, name: string | undefined) {
  const known = language === "en" ? snapshot.en.some((r) => r.name === name) : snapshot.ar.includes(name as string);
  if (name && !known) throw new Error(`Override for story ${story} names "${name}", which is not in the ${language} index`);
}

// ---------- Assemble ----------

const byStory = new Map<number, { month: number; day: number; position: number; en?: string; ar?: string }>();
for (const row of rows) {
  const entry = byStory.get(row.story) ?? { month: row.month, day: row.day, position: row.position };
  const title = row.title.replace(/\s+/g, " ").trim();
  if (row.language === ENGLISH) entry.en = title;
  else entry.ar = title;
  entry.position = Math.min(entry.position, row.position);
  byStory.set(row.story, entry);
}

const ordered = [...byStory].sort(
  (a, b) => a[1].month - b[1].month || a[1].day - b[1].day || a[1].position - b[1].position
);
const kinds = new Map(ordered.map(([story, entry]) => [story, kindOf(entry.month, entry.day, entry.en ?? "")]));
countTitleFirstNames(
  ordered.filter(([story]) => kinds.get(story) === "saint").map(([, entry]) => ({ en: entry.en ?? "", ar: entry.ar }))
);
const auto = new Map(ordered.map(([story, entry]) => [story, autoLink(kinds.get(story)!, entry.en ?? "", entry.ar)]));

// One person has one synaxarium entry: an index name claimed by two different entries is ambiguous.
for (const language of ["en", "ar"] as const) {
  const claims = new Map<string, number[]>();
  for (const [story, link] of auto) if (link[language]) claims.set(link[language]!, [...(claims.get(link[language]!) ?? []), story]);
  for (const stories of claims.values()) if (stories.length > 1) for (const story of stories) auto.get(story)![language] = undefined;
}

const days: SaintsData["days"] = {};
for (const [story, entry] of ordered) {
  if (!entry.en) throw new Error(`Story ${story} has no English title`);
  const override = overrides.links[String(story)];
  const link = {
    en: override && override.en !== undefined ? override.en ?? undefined : auto.get(story)!.en,
    ar: override && override.ar !== undefined ? override.ar ?? undefined : auto.get(story)!.ar,
  };
  checkKnown(story, "en", link.en);
  checkKnown(story, "ar", link.ar);
  const index = link.en || link.ar ? { ...(link.en ? { en: link.en } : {}), ...(link.ar ? { ar: link.ar } : {}) } : undefined;
  const item: Commemoration = {
    id: story,
    kind: kinds.get(story)!,
    en: entry.en,
    ...(entry.ar ? { ar: entry.ar } : {}),
    ...(index ? { index } : {}),
  };
  (days[`${entry.month}-${entry.day}`] ??= []).push(item);
}

const data: SaintsData = {
  source: {
    name: "Katameros",
    url: "https://katameros.app",
    repository: "https://github.com/pierresaid/katameros-api",
    commit,
    file: DB_PATH,
    table: "Synaxarium (LanguageId 2 = English, 3 = Arabic), Title column only",
    extracted: new Date().toISOString().slice(0, 10),
    license: "Repository: MIT, Copyright (c) 2022 katameros. The synaxarium text's own license is not stated (CAL-001).",
    permission: "Titles used on the owner's decision (CAL-003); a courtesy permission request was sent to the maintainer.",
    content: "Titles only, no stories. English and Arabic are paired by StoryId.",
    indexSnapshot: `scripts/calendar/saints-index.snapshot.json, taken ${snapshot.taken}`,
  },
  days,
};

const lines = Object.entries(days)
  .map(([key, items]) => `    ${JSON.stringify(key)}: ${JSON.stringify(items)}`)
  .join(",\n");
const json = `{\n  "source": ${JSON.stringify(data.source, null, 2).replace(/\n/g, "\n  ")},\n  "days": {\n${lines}\n  }\n}\n`;
writeFileSync(join(root, "lib/calendar/data/saints.katameros.json"), json);

const all = Object.values(days).flat();
const count = (predicate: (c: Commemoration) => boolean) => all.filter(predicate).length;
console.log(
  `Katameros ${commit.slice(0, 7)}: ${Object.keys(days).length} days, ${all.length} entries ` +
    `(${count((c) => c.kind === "saint")} saints, ${count((c) => c.kind === "monthly")} monthly, ` +
    `${count((c) => c.kind === "event")} events, ${count((c) => c.kind === "feast")} feasts); ` +
    `linked: ${count((c) => Boolean(c.index?.en))} English, ${count((c) => Boolean(c.index?.ar))} Arabic`
);
