// Side-by-side before/after images for the design-traditional review (UI-015).
//   node compare.mjs ../ui-audit/before-traditional ../ui-audit/after-traditional
// Writes <after>/compare/<screen>.png: the deployed design on the left, the new one on the right.
import sharp from "sharp";
import fs from "node:fs";
import path from "node:path";

const [BEFORE, AFTER] = process.argv.slice(2).map((p) => path.resolve(p));
const OUT = path.join(AFTER, "compare");
fs.mkdirSync(OUT, { recursive: true });

// Home, chat with a table and citations (top and the Sources list at the bottom), saints, 404.
const SCREENS = [
  "01-home",
  "08-chat-table-top",
  "09-chat-table-bottom",
  "08-chat-long-top",
  "13-saints-list",
  "16-saint-detail",
  "19-404",
];

const GAP = 24;
const LABEL = 44;
const label = (text, width) =>
  Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${LABEL}"><rect width="100%" height="100%" fill="#ffffff"/><text x="8" y="30" font-family="Segoe UI, Arial" font-size="22" fill="#333">${text}</text></svg>`
  );

let count = 0;
for (const lang of ["en", "ar"]) {
  for (const vp of ["desktop", "mobile"]) {
    for (const screen of SCREENS) {
      const name = `${lang}-${vp}-${screen}.png`;
      const a = path.join(BEFORE, name);
      const b = path.join(AFTER, name);
      if (!fs.existsSync(a) || !fs.existsSync(b)) continue;
      const [ma, mb] = await Promise.all([sharp(a).metadata(), sharp(b).metadata()]);
      const width = ma.width + GAP + mb.width;
      const height = LABEL + Math.max(ma.height, mb.height);
      await sharp({ create: { width, height, channels: 3, background: "#ffffff" } })
        .composite([
          { input: label(`Before (deployed) — ${name}`, ma.width), left: 0, top: 0 },
          { input: label("After (design-traditional)", mb.width), left: ma.width + GAP, top: 0 },
          { input: a, left: 0, top: LABEL },
          { input: b, left: ma.width + GAP, top: LABEL },
        ])
        .png()
        .toFile(path.join(OUT, name));
      count++;
    }
  }
}
console.log(`${count} comparisons -> ${OUT}`);
