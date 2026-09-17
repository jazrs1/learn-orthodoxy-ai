// Brand proposal generator (design-traditional, Step 1).
// Builds the wordmark, lettermark and icon as outlined SVGs (no font needed to display them),
// rasterises them to PNG and lays out comparison sheets.
//
//   FONT_DIR=/path/with/EBGaramond-VF.ttf CHROME_BIN=/path/to/chrome node brand.mjs ../ui-audit/brand
//
// Needs fontkit, sharp and playwright next to this script (see README.md).
import * as fontkit from "fontkit";
import sharp from "sharp";
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve(process.argv[2] ?? "../ui-audit/brand");
const FONT_DIR = process.env.FONT_DIR ?? "fonts";
const REPO = process.env.REPO_ROOT ?? path.resolve(OUT, "../..");

export const C = {
  paper: "#F8F3EA",
  umber: "#4B3A22",
  gold: "#E4AE48", // large use only (1.8:1 on paper)
  antique: "#866426", // small text and hairlines on paper (4.9:1)
  red: "#8E2A1E", // rubrics (7.6:1)
  night: "#2A2117", // dark background
  ivory: "#F4ECDC",
  ivoryMuted: "#D8CAB0",
  candle: "#F1E7D8",
};

const vf = fontkit.openSync(path.join(FONT_DIR, "EBGaramond-VF.ttf"));
const instances = {};
const font = (w) => (instances[w] ??= vf.getVariation({ wght: w }));

const r2 = (s) => s.replace(/-?\d*\.\d+/g, (n) => String(Math.round(+n * 100) / 100));
const f2 = (n) => String(Math.round(n * 100) / 100);

// Set one line as outlines. y is the baseline (y grows downward).
function setText(text, { size, weight = 400, x = 0, y = 0, tracking = 0, features = [] }) {
  const f = font(weight);
  const s = size / f.unitsPerEm;
  const run = f.layout(text, features);
  let pen = x;
  const parts = [];
  const bb = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  run.glyphs.forEach((g, i) => {
    const p = run.positions[i];
    const tp = g.path.scale(s, -s).translate(pen + p.xOffset * s, y - p.yOffset * s);
    if (tp.commands.length) {
      parts.push(tp.toSVG());
      const b = tp.bbox;
      bb.minX = Math.min(bb.minX, b.minX);
      bb.maxX = Math.max(bb.maxX, b.maxX);
      bb.minY = Math.min(bb.minY, b.minY);
      bb.maxY = Math.max(bb.maxY, b.maxY);
    }
    pen += p.xAdvance * s + (i < run.glyphs.length - 1 ? tracking : 0);
  });
  return { d: r2(parts.join("")), bbox: bb, width: bb.maxX - bb.minX, count: run.glyphs.length };
}

function svgDoc(vb, body, title) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.map(f2).join(" ")}" role="img" aria-label="${title}">\n<title>${title}</title>\n${body}\n</svg>\n`;
}

/* ---------------------------------------------------------------- candlestick */
// Drawn in a 60 x 226 box: flame top at y=0, foot at y=226.
function candlestick(dark) {
  const holder = dark ? C.ivoryMuted : C.umber;
  const wax = dark ? C.ivory : C.candle;
  const waxLine = dark ? "none" : C.umber;
  return `<path fill="${C.gold}" d="M30 0C38 12 44 24 43 32C42 40 36 45 30 45C24 45 18 40 17 32C16 24 22 12 30 0Z"/>
<path fill="#F7E6BD" d="M30 13C34 21 35.5 28 35 33C34.5 37.5 32.5 40 30 40C27.5 40 25.5 37.5 25 33C24.5 28 26 21 30 13Z"/>
<rect x="19.5" y="47" width="21" height="76" fill="${wax}" stroke="${waxLine}" stroke-width="1.4"/>
<rect x="29" y="37" width="2" height="11" rx="1" fill="${holder}"/>
<g fill="${holder}">
<path d="M1 123H59C59 128 53 134 43 136H17C7 134 1 128 1 123Z"/>
<rect x="26.5" y="135" width="7" height="8"/>
<ellipse cx="30" cy="145" rx="9" ry="3"/>
<path d="M26 147C24 158 21.5 168 22.5 177C23.5 185 27 189 27 192H33C33 189 36.5 185 37.5 177C38.5 168 36 158 34 147Z"/>
<ellipse cx="30" cy="195" rx="9" ry="3"/>
<path d="M23 197H37C43 203 51 207 55 211H5C9 207 17 203 23 197Z"/>
<rect x="2" y="211" width="56" height="7" rx="2"/>
<rect x="0" y="219" width="60" height="7" rx="3.5"/>
</g>`;
}

/* ---------------------------------------------------------------- wordmark */
const TAGLINE = "A Coptic Orthodox Study Guide";
const TAGLINE_ALT = "A Coptic Orthodox Catechism Resource";

function wordmark({ tagline, dark }) {
  const col = dark
    ? { learn: C.ivory, orth: C.gold, tag: C.ivoryMuted }
    : { learn: C.umber, orth: C.gold, tag: C.umber };
  const O_SIZE = 128;
  const capO = O_SIZE * 0.65;
  const X = 0; // text left edge; the candle sits to the left of it
  const yO = 0;
  const orth = setText("ORTHODOXY", { size: O_SIZE, weight: 600, x: X, y: yO, tracking: O_SIZE * 0.02 });
  const yL = yO - capO - O_SIZE * 0.14;
  const learn = setText("Learn", { size: 106, weight: 600, x: X, y: yL });

  // Tagline: all small caps, tracked out to the width of ORTHODOXY (within limits), centred under it.
  const T_SIZE = 40;
  const feats = ["c2sc", "smcp"];
  const nat = setText(tagline, { size: T_SIZE, features: feats });
  const track = Math.min(T_SIZE * 0.2, Math.max(T_SIZE * 0.08, (orth.width - nat.width) / (nat.count - 1)));
  const probe = setText(tagline, { size: T_SIZE, features: feats, tracking: track });
  const yT = yO + O_SIZE * 0.38;
  const tx = orth.bbox.minX + (orth.width - probe.width) / 2 - probe.bbox.minX;
  const tag = setText(tagline, { size: T_SIZE, weight: 500, features: feats, tracking: track, x: tx, y: yT });

  // Candle: flame a little above "Learn", foot on the ORTHODOXY baseline, clear of every letter.
  const top = learn.bbox.minY - 18;
  const k = (yO + 1 - top) / 226;
  const gap = O_SIZE * 0.16;
  const kx = k * 1.25; // the candle reads better a little wider than drawn
  const cx = Math.min(orth.bbox.minX, learn.bbox.minX) - gap - 60 * kx;

  const pad = 6;
  const minX = cx - pad;
  const maxX = Math.max(orth.bbox.maxX, tag.bbox.maxX, learn.bbox.maxX) + pad;
  const minY = top - pad;
  const maxY = tag.bbox.maxY + pad;
  const body = `<g transform="translate(${f2(cx)} ${f2(top)}) scale(${kx.toFixed(4)} ${k.toFixed(4)})">
${candlestick(dark)}
</g>
<path fill="${col.learn}" d="${learn.d}"/>
<path fill="${col.orth}" d="${orth.d}"/>
<path fill="${col.tag}" d="${tag.d}"/>`;
  return svgDoc([minX, minY, maxX - minX, maxY - minY], body, `Learn Orthodoxy — ${tagline}`);
}

/* ---------------------------------------------------------------- crosses */
// All crosses are centred on (0,0) and about 104 units tall.
const P = (x, y) => `${f2(x)} ${f2(y)}`;

function budEnd(ex, ey, dx, dy, w) {
  // Flared arm end with a pointed central bud and two round side buds.
  const px = -dy, py = dx;
  const a = (t, n) => [ex + dx * t + px * n, ey + dy * t + py * n];
  const [b1, b2, b3, b4] = [a(-9, w / 2), a(-1, 6.2), a(-1, -6.2), a(-9, -w / 2)];
  const flare = `<path d="M${P(...b1)}L${P(...b2)}L${P(...b3)}L${P(...b4)}Z"/>`;
  const [l1, tip, l2] = [a(-1, 5.2), a(11, 0), a(-1, -5.2)];
  const c1 = a(4, 6.5), c2 = a(4, -6.5);
  const lens = `<path d="M${P(...l1)}Q${P(...c1)} ${P(...tip)}Q${P(...c2)} ${P(...l2)}Z"/>`;
  const s1 = a(-1, 6.6), s2 = a(-1, -6.6);
  return `${flare}${lens}<circle cx="${f2(s1[0])}" cy="${f2(s1[1])}" r="3.7"/><circle cx="${f2(s2[0])}" cy="${f2(s2[1])}" r="3.7"/>`;
}

function latinBudded() {
  const w = 9, bar = -15;
  return `<rect x="${-w / 2}" y="-42" width="${w}" height="84"/>
<rect x="-30" y="${bar - w / 2}" width="60" height="${w}"/>
${budEnd(0, -41, 0, -1, w)}${budEnd(0, 41, 0, 1, w)}${budEnd(-29, bar, -1, 0, w)}${budEnd(29, bar, 1, 0, w)}`;
}

function copticEnd(dx, dy) {
  // Equal arm flaring from the centre into three round points (one tip, two corners).
  const px = -dy, py = dx;
  const a = (t, n) => [dx * t + px * n, dy * t + py * n];
  const pts = [a(0, 5), a(35, 10.5), a(38, 0), a(35, -10.5), a(0, -5)];
  const arm = `<path d="M${pts.map((p) => P(...p)).join("L")}Z"/>`;
  const tip = a(40.5, 0), s1 = a(35, 11), s2 = a(35, -11);
  return `${arm}<circle cx="${f2(tip[0])}" cy="${f2(tip[1])}" r="6"/><circle cx="${f2(s1[0])}" cy="${f2(s1[1])}" r="5"/><circle cx="${f2(s2[0])}" cy="${f2(s2[1])}" r="5"/>`;
}

function copticCross() {
  // Scaled so its visual weight matches the Latin cross.
  return `<g transform="scale(1.02)">${copticEnd(0, -1)}${copticEnd(0, 1)}${copticEnd(-1, 0)}${copticEnd(1, 0)}<rect x="-6" y="-6" width="12" height="12" transform="rotate(45)"/></g>`;
}

/* ---------------------------------------------------------------- O bubble */
// The EB Garamond O plus a speech-bubble tail at the lower left.
function bubbleO({ size, weight = 800, x = 0, y = 0 }) {
  const o = setText("O", { size, weight, x, y });
  const b = o.bbox;
  const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2;
  const rx = (b.maxX - b.minX) / 2, ry = (b.maxY - b.minY) / 2;
  const on = (deg, f) => [cx + rx * f * Math.cos((deg * Math.PI) / 180), cy + ry * f * Math.sin((deg * Math.PI) / 180)];
  const A = on(165, 0.95), B = on(118, 0.95);
  const T = [cx - rx * 1.02, cy + ry * 1.0];
  const q1 = [cx - rx * 0.9, cy + ry * 0.72];
  const q2 = [cx - rx * 0.6, cy + ry * 0.9];
  const tail = `M${P(...A)}Q${P(...q1)} ${P(...T)}Q${P(...q2)} ${P(...B)}A${f2(rx * 0.95)} ${f2(ry * 0.95)} 0 0 1 ${P(...A)}Z`;
  return { o, tail, cx, cy, rx, ry, bbox: { ...b, minX: T[0], maxY: Math.max(b.maxY, T[1]) } };
}

// Favicon sizes drawn on the pixel grid (viewBox = pixel size): whole-pixel strokes, plain cross,
// heavier O, bigger tail. g = 1 for 16 px, 2 for 32 px.
function pixelIcon({ px, cross, dark }) {
  const g = px / 16;
  const ink = dark ? C.ivory : C.umber;
  const counter = dark ? C.night : C.paper;
  const cx = 8.5 * g, cy = 7.5 * g;
  const [rx, ry, irx, iry] = [6.5 * g, 7 * g, 3.5 * g, 5 * g];
  const ring = `M${cx - rx} ${cy}a${rx} ${ry} 0 1 0 ${2 * rx} 0a${rx} ${ry} 0 1 0 ${-2 * rx} 0Z` +
    `M${cx - irx} ${cy}a${irx} ${iry} 0 1 1 ${2 * irx} 0a${irx} ${iry} 0 1 1 ${-2 * irx} 0Z`;
  const tail = g === 1 ? "M3.2 10.3Q3.6 13.6 0.4 15.6Q4.6 15.7 7.2 14.1Z" : "M6.3 20.6Q7.1 27.2 0.8 31.2Q9.2 31.4 14.4 28.2Z";
  const R = (x, y, w, h) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`;
  let c;
  if (g === 1) {
    c = cross === "coptic" ? R(8, 5, 1, 5) + R(6, 7, 5, 1) : R(8, 3, 1, 9) + R(6, 5, 5, 1);
  } else if (cross === "coptic") {
    // Equal arms with a small flare at each end.
    c = R(16, 9, 2, 12) + R(11, 14, 12, 2) + R(15, 9, 4, 1) + R(15, 20, 4, 1) + R(11, 13, 1, 4) + R(22, 13, 1, 4);
  } else {
    c = R(16, 6, 2, 18) + R(12, 10, 10, 2);
  }
  const body = `<ellipse cx="${cx}" cy="${cy}" rx="${irx + 0.5}" ry="${iry + 0.5}" fill="${counter}"/>
<path fill="${C.gold}" fill-rule="evenodd" d="${ring}"/>
<path fill="${C.gold}" d="${tail}"/>
<g fill="${ink}">${c}</g>`;
  const name = cross === "coptic" ? "Coptic cross" : "Latin cross";
  return svgDoc([0, 0, px, px], body, `Learn Orthodoxy icon, ${name}`);
}

/* ---------------------------------------------------------------- lettermark + icons */
function lettermark({ cross, dark }) {
  const SIZE = 400;
  const ink = dark ? C.ivory : C.umber;
  const L = setText("L", { size: SIZE, weight: 800 });
  const probe = bubbleO({ size: SIZE });
  const gap = SIZE * 0.06;
  const shift = L.bbox.maxX + gap - probe.bbox.minX;
  const O = bubbleO({ size: SIZE, x: shift });
  const crossScale = (O.ry * 2 * 0.5) / 104;
  const body = `<path fill="${ink}" d="${L.d}"/>
<path fill="${C.gold}" fill-rule="nonzero" d="${O.o.d}"/>
<path fill="${C.gold}" d="${r2(O.tail)}"/>
<g fill="${ink}" transform="translate(${f2(O.cx)} ${f2(O.cy)}) scale(${crossScale.toFixed(4)})">${cross === "coptic" ? copticCross() : latinBudded()}</g>`;
  const pad = 8;
  const minX = L.bbox.minX - pad, maxX = O.bbox.maxX + pad;
  const minY = Math.min(L.bbox.minY, O.bbox.minY) - pad, maxY = Math.max(L.bbox.maxY, O.bbox.maxY) + pad;
  const name = cross === "coptic" ? "Coptic cross" : "Latin cross";
  return svgDoc([minX, minY, maxX - minX, maxY - minY], body, `LO lettermark, ${name}`);
}

// Icon: the O bubble alone, counter filled with paper so the cross reads on any tab colour.
function icon({ cross, dark, square }) {
  const ink = dark ? C.ivory : C.umber;
  const fillCounter = dark ? C.night : C.paper;
  let body, box;
  {
    const O = bubbleO({ size: 400 });
    const crossScale = (O.ry * 2 * 0.5) / 104;
    body = `<ellipse cx="${f2(O.cx)}" cy="${f2(O.cy)}" rx="${f2(O.rx * 0.8)}" ry="${f2(O.ry * 0.85)}" fill="${fillCounter}"/>
<path fill="${C.gold}" d="${O.o.d}"/>
<path fill="${C.gold}" d="${r2(O.tail)}"/>
<g fill="${ink}" transform="translate(${f2(O.cx)} ${f2(O.cy)}) scale(${crossScale.toFixed(4)})">${cross === "coptic" ? copticCross() : latinBudded()}</g>`;
    box = O.bbox;
  }
  // Square viewBox centred on the artwork.
  const w = box.maxX - box.minX, h = box.maxY - box.minY;
  let side = Math.max(w, h) * (square ? 1.4 : 1.04);
  const mx = (box.minX + box.maxX) / 2, my = (box.minY + box.maxY) / 2;
  const vb = [mx - side / 2, my - side / 2, side, side];
  const bg = square ? `<rect x="${f2(vb[0])}" y="${f2(vb[1])}" width="${f2(side)}" height="${f2(side)}" fill="${dark ? C.night : C.paper}"/>\n` : "";
  const name = cross === "coptic" ? "Coptic cross" : "Latin cross";
  return svgDoc(vb, bg + body, `Learn Orthodoxy icon, ${name}`);
}

/* ---------------------------------------------------------------- build */
const files = {
  "wordmark.svg": wordmark({ tagline: TAGLINE, dark: false }),
  "wordmark-dark.svg": wordmark({ tagline: TAGLINE, dark: true }),
  "wordmark-alt.svg": wordmark({ tagline: TAGLINE_ALT, dark: false }),
  "wordmark-alt-dark.svg": wordmark({ tagline: TAGLINE_ALT, dark: true }),
};
for (const cross of ["latin", "coptic"]) {
  files[`lettermark-${cross}.svg`] = lettermark({ cross, dark: false });
  files[`lettermark-${cross}-dark.svg`] = lettermark({ cross, dark: true });
  files[`icon-${cross}.svg`] = icon({ cross, dark: false });
  files[`icon-${cross}-dark.svg`] = icon({ cross, dark: true });
  for (const px of [16, 32]) {
    files[`icon-${px}-${cross}.svg`] = pixelIcon({ px, cross, dark: false });
    files[`icon-${px}-${cross}-dark.svg`] = pixelIcon({ px, cross, dark: true });
  }
  files[`app-icon-${cross}.svg`] = icon({ cross, dark: false, square: true });
  files[`app-icon-${cross}-dark.svg`] = icon({ cross, dark: true, square: true });
}

fs.mkdirSync(path.join(OUT, "svg"), { recursive: true });
fs.mkdirSync(path.join(OUT, "png"), { recursive: true });
for (const [name, svg] of Object.entries(files)) fs.writeFileSync(path.join(OUT, "svg", name), svg);

// PNG renders: rasterise large, then downsample (what favicon tools do).
async function png(name, width, outName) {
  const buf = Buffer.from(files[name]);
  const vbWidth = +files[name].match(/viewBox="[^ ]+ [^ ]+ ([^ ]+)/)[1];
  await sharp(buf, { density: Math.min(2400, 72 * Math.max(1, (width * 4) / vbWidth)) })
    .resize({ width, kernel: "lanczos3" })
    .png()
    .toFile(path.join(OUT, "png", outName));
}
const renders = [];
for (const name of Object.keys(files)) {
  const base = name.replace(/\.svg$/, "");
  const sizes = name.startsWith("wordmark") ? [1200, 480, 240] : name.startsWith("lettermark") ? [600, 128, 48] : name.startsWith("icon-16") ? [16] : name.startsWith("icon-32") ? [32] : [512, 180, 32, 16];
  for (const w of sizes) {
    const out = /^icon-(16|32)-/.test(name) ? `${base}.png` : `${base}-${w}.png`;
    await png(name, w, out);
    renders.push(out);
  }
}

/* ---------------------------------------------------------------- sheets */
const orig = (f) => `file:///${path.join(REPO, "orthodox-site/public/brand", f).replace(/\\/g, "/")}`;
const img = (f, w, extra = "") => `<img src="png/${f}" width="${w}" ${extra}>`;
const zoom = (f, n) => `<img src="png/${f}" width="${n * 8}" style="image-rendering:pixelated">`;
const cell = (label, inner, dark) => `<figure class="${dark ? "dark" : ""}">${inner}<figcaption>${label}</figcaption></figure>`;

const css = `body{margin:0;padding:32px;background:#fff;font:14px/1.4 Georgia,serif;color:#333;width:1600px}
h1{font-size:24px;margin:0 0 20px}h2{font-size:17px;margin:28px 0 10px;border-bottom:1px solid #ccc}
.row{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap}
figure{margin:0;padding:16px;background:${C.paper};border:1px solid #ddd;display:flex;flex-direction:column;gap:8px;align-items:flex-start}
figure.dark{background:${C.night}}figure.dark figcaption{color:#ccc}
figcaption{font:12px/1.3 system-ui,sans-serif;color:#555}
.sw{width:210px}.sw div{align-self:stretch;height:64px;border:1px solid #ccc}
.tab{display:flex;align-items:center;gap:8px;background:#dee1e6;padding:8px 14px;border-radius:8px 8px 0 0;font:13px system-ui}
.tab.darktab{background:#35363a;color:#e8eaed}`;

const sheets = {
  "sheet-1-wordmark": `<h1>Wordmark — original vs. proposal</h1>
<div class="row">${cell("Original (PNG, 2560×1440 with padding)", `<img src="${orig("LearnOrthodoxyLogo-Wordmark2.png")}" width="760">`)}
${cell("Proposal: EB Garamond throughout, candle clear of the O, trimmed, new tagline", img("wordmark-1200.png", 760))}</div>
<div class="row">${cell("Alternate tagline (original wording)", img("wordmark-alt-1200.png", 760))}
${cell("Light on dark", img("wordmark-dark-1200.png", 760), true)}</div>
<div class="row">${cell("Alternate, light on dark", img("wordmark-alt-dark-1200.png", 760), true)}</div>
<h2>Small sizes</h2>
<div class="row">${cell("480 px", img("wordmark-480.png", 480))}${cell("240 px", img("wordmark-240.png", 240))}
${cell("240 px, alternate", img("wordmark-alt-240.png", 240))}${cell("240 px, dark", img("wordmark-dark-240.png", 240), true)}</div>`,

  "sheet-2-lettermark": `<h1>Lettermark — original vs. proposal</h1>
<div class="row">${cell("Original", `<img src="${orig("LearnOrthodoxyLogo-Lettermark2.png")}" width="360">`)}
${cell("Latin budded cross (as original)", img("lettermark-latin-600.png", 360))}
${cell("Equal-armed Coptic cross", img("lettermark-coptic-600.png", 360))}</div>
<div class="row">${cell("Latin, dark", img("lettermark-latin-dark-600.png", 360), true)}
${cell("Coptic, dark", img("lettermark-coptic-dark-600.png", 360), true)}</div>
<h2>Header sizes (128 and 48 px wide)</h2>
<div class="row">${["latin", "coptic"].map((c) => cell(c, img(`lettermark-${c}-128.png`, 128) + img(`lettermark-${c}-48.png`, 48))).join("")}
${["latin", "coptic"].map((c) => cell(c + ", dark", img(`lettermark-${c}-dark-128.png`, 128) + img(`lettermark-${c}-dark-48.png`, 48), true)).join("")}</div>`,

  "sheet-3-icons": `<h1>Icon (O bubble with cross) — favicon and app icon</h1>
<p>"Detailed" is the lettermark O (for 180 px and up). "Pixel" versions are drawn on the 16 and 32 px grid: whole-pixel strokes, heavier O, plain cross. The counter is filled so the cross reads on light and dark tabs.</p>
${["latin", "coptic"]
  .map(
    (c) => `<h2>${c === "latin" ? "Latin budded cross" : "Coptic cross"}</h2>
<div class="row">${cell("Detailed 180", img(`icon-${c}-180.png`, 180))}${cell("Detailed 180, dark", img(`icon-${c}-dark-180.png`, 180), true)}
${cell("App icon 180 (square)", img(`app-icon-${c}-180.png`, 180))}${cell("App icon, dark", img(`app-icon-${c}-dark-180.png`, 180), true)}
${cell("Detailed at 32 / 16", img(`icon-${c}-32.png`, 32) + img(`icon-${c}-16.png`, 16))}
${cell("Pixel at 32 / 16", img(`icon-32-${c}.png`, 32) + img(`icon-16-${c}.png`, 16))}
${cell("Pixel at 32 / 16, dark", img(`icon-32-${c}-dark.png`, 32) + img(`icon-16-${c}-dark.png`, 16), true)}</div>
<div class="row">${cell("Detailed 32, zoomed 8×", zoom(`icon-${c}-32.png`, 32))}${cell("Pixel 32, zoomed 8×", zoom(`icon-32-${c}.png`, 32))}
${cell("Detailed 16, zoomed 8×", zoom(`icon-${c}-16.png`, 16))}${cell("Pixel 16, zoomed 8×", zoom(`icon-16-${c}.png`, 16))}
${cell("Browser tabs (16 px)", `<div class="tab">${img(`icon-16-${c}.png`, 16)} Learn Orthodoxy</div><div class="tab darktab">${img(`icon-16-${c}.png`, 16)} Learn Orthodoxy</div>`)}</div>`,
  )
  .join("")}`,

  "sheet-4-palette": `<h1>Palette</h1>
<div class="row">${[
    ["Paper (background)", C.paper, "—"],
    ["Umber (text, L, candle holder)", C.umber, "9.9 : 1 on paper"],
    ["Gold (large use: ORTHODOXY, O)", C.gold, "1.8 : 1 on paper — logo / large ornament only"],
    ["Antique gold (small use: hairlines, labels)", C.antique, "4.9 : 1 on paper, AA for text"],
    ["Rubric red (initials, marks, citation numbers)", C.red, "7.6 : 1 on paper"],
    ["Night (dark background)", C.night, "ivory 13.5 : 1, gold 7.9 : 1"],
    ["Ivory (text on dark)", C.ivory, ""],
  ]
    .map(([n, h, note]) => `<figure class="sw"><div style="background:${h}"></div><figcaption><b>${n}</b><br>${h}<br>${note}</figcaption></figure>`)
    .join("")}</div>`,
};

const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const [name, html] of Object.entries(sheets)) {
  const file = path.join(OUT, `${name}.html`);
  fs.writeFileSync(file, `<!doctype html><meta charset="utf-8"><style>${css}</style><body>${html}</body>`);
  await page.goto("file:///" + file.replace(/\\/g, "/"));
  await page.waitForLoadState("load");
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}
await browser.close();
console.log(`${Object.keys(files).length} SVGs, ${renders.length} PNGs, ${Object.keys(sheets).length} sheets -> ${OUT}`);
