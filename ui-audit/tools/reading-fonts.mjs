// Reading-font comparison for long answers (design-traditional, UI-013).
// Renders one real eval answer at phone width in EB Garamond and Source Serif 4 at a few sizes,
// measures x-height and characters per line, and writes a side-by-side screenshot.
//
//   FONT_DIR=/path/to/fonts CHROME_BIN=/path/to/chrome node reading-fonts.mjs ../ui-audit/typography
//
// Needs playwright and marked next to this script; FONT_DIR holds EBGaramond-VF.ttf,
// EBGaramond-Italic-VF.ttf and SourceSerif4-VF.ttf (github.com/google/fonts).
import { chromium } from "playwright";
import { marked } from "marked";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve(process.argv[2] ?? "../ui-audit/typography");
const FONT_DIR = path.resolve(process.env.FONT_DIR ?? "fonts");
const FX = JSON.parse(fs.readFileSync(new URL("./fixtures.json", import.meta.url), "utf-8"));
fs.mkdirSync(OUT, { recursive: true });

const url = (f) => "file:///" + path.join(FONT_DIR, f).replace(/\\/g, "/");
const answer = marked.parse(FX["CAT-06"].answer.replace(/\[(\d+(?:,\s*\d+)*)\]/g, '<sup class="cite">$1</sup>'));

const VARIANTS = [
  { id: "ss4-17", label: "Source Serif 4 · 17px / 1.7 (today)", family: "SS4", size: 17, leading: 1.7 },
  { id: "ss4-18", label: "Source Serif 4 · 18px / 1.65", family: "SS4", size: 18, leading: 1.65 },
  { id: "ebg-19", label: "EB Garamond · 19px / 1.6", family: "EBG", size: 19, leading: 1.6 },
  { id: "ebg-20", label: "EB Garamond · 20px / 1.55", family: "EBG", size: 20, leading: 1.55 },
];
const X_HEIGHT = { SS4: 0.475, EBG: 0.4 };

const css = `
@font-face{font-family:EBG;src:url("${url("EBGaramond-VF.ttf")}");font-weight:400 800}
@font-face{font-family:EBG;src:url("${url("EBGaramond-Italic-VF.ttf")}");font-weight:400 800;font-style:italic}
@font-face{font-family:SS4;src:url("${url("SourceSerif4-VF.ttf")}");font-weight:200 900}
body{margin:0;background:#F8F3EA;color:#3B2D1B}
.phone{width:390px;padding:16px;box-sizing:border-box}
.label{font:600 13px system-ui;color:#555;margin:0 0 10px}
h2{font:600 22px/1.2 EBG;color:#4B3A22;margin:0 0 12px}
.q{font:italic 400 20px/1.4 EBG;margin:0 0 16px;padding-inline-start:12px;border-inline-start:2px solid #866426}
.a p{margin:0 0 .8em}.a ul,.a ol{padding-inline-start:1.3em;margin:0 0 .8em}
.a h1,.a h2,.a h3{font-family:EBG;font-weight:600;color:#4B3A22;margin:1.2em 0 .4em;font-size:1.15em}
.a > p:first-child::first-letter{initial-letter:2;color:#8E2A1E;font-family:EBG;font-weight:500;margin-inline-end:.08em}
.cite{font:700 .68em/0 SS4;color:#8E2A1E;margin-inline-start:.1em}
.a strong{font-weight:650}
`;

const html = `<!doctype html><meta charset="utf-8"><style>${css}
${VARIANTS.map((v) => `#${v.id} .a{font-family:${v.family};font-size:${v.size}px;line-height:${v.leading}}`).join("\n")}
.row{display:flex;gap:0;align-items:flex-start}.phone+.phone{border-inline-start:1px solid #d8cab0}
</style><div class="row">${VARIANTS.map(
  (v) => `<div class="phone" id="${v.id}"><p class="label">${v.label}</p>
<p class="q">${FX["CAT-06"].question}</p><div class="a">${answer}</div></div>`,
).join("")}</div>`;

const file = path.join(OUT, "reading-fonts.html");
fs.writeFileSync(file, html);
const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
const results = {};
for (const dpr of [2, 1]) {
  const page = await browser.newPage({ viewport: { width: 390 * VARIANTS.length, height: 900 }, deviceScaleFactor: dpr });
  await page.goto("file:///" + file.replace(/\\/g, "/"));
  await page.evaluate(() => document.fonts.ready);
  if (dpr === 2) {
    // Characters per line across the body paragraphs, measured from rendered line boxes.
    for (const v of VARIANTS) {
      results[v.id] = await page.evaluate((id) => {
        const lines = new Map();
        for (const p of document.querySelectorAll(`#${id} .a p, #${id} .a li`)) {
          const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            for (let i = 0; i < node.length; i++) {
              const r = document.createRange();
              r.setStart(node, i);
              r.setEnd(node, i + 1);
              const rect = r.getBoundingClientRect();
              if (!rect.height) continue;
              const key = `${p.dataset.k ?? (p.dataset.k = Math.random())}:${Math.round(rect.top)}`;
              lines.set(key, (lines.get(key) ?? 0) + 1);
            }
          }
        }
        const counts = [...lines.values()].sort((a, b) => a - b);
        // Ignore the last short line of each block by taking the upper half.
        const full = counts.slice(Math.floor(counts.length / 2));
        const height = document.querySelector(`#${id} .a`).getBoundingClientRect().height;
        return { medianFullLine: full[Math.floor(full.length / 2)], lines: counts.length, heightPx: Math.round(height) };
      }, v.id);
      results[v.id].xHeightPx = Number((X_HEIGHT[v.family] * v.size).toFixed(1));
    }
  }
  await page.screenshot({ path: path.join(OUT, `reading-fonts-${dpr}x.png`), fullPage: true });
  await page.close();
}
await browser.close();
fs.writeFileSync(path.join(OUT, "reading-fonts.json"), JSON.stringify(results, null, 1));
console.log(results);
