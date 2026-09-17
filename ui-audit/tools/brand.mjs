// Brand proposal generator (design-traditional, UI-012).
// Builds the wordmark, lettermark and icons as outlined SVGs (no font needed to display them),
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
const FONT_DIR = path.resolve(process.env.FONT_DIR ?? "fonts");
const REPO = process.env.REPO_ROOT ?? path.resolve(OUT, "../..");

// The cross is pending the priest's choice (UI-012); both are built, Coptic is shown first.
const CROSSES = ["coptic", "latin"];
const CROSS_NAME = { coptic: "Coptic cross", latin: "Latin budded cross" };

export const C = {
  paper: "#F8F3EA",
  umber: "#4B3A22",
  gold: "#E4AE48", // large use only (1.8:1 on paper)
  antique: "#866426", // small text and hairlines on paper (4.9:1)
  brass: "#B08A3E", // candlestick on dark (4.9:1 on night)
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
const P = (x, y) => `${f2(x)} ${f2(y)}`;

function bboxOf(points) {
  const b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  for (const [x, y] of points) {
    b.minX = Math.min(b.minX, x);
    b.maxX = Math.max(b.maxX, x);
    b.minY = Math.min(b.minY, y);
    b.maxY = Math.max(b.maxY, y);
  }
  return b;
}

// Set one line as outlines. y is the baseline (y grows downward).
function setText(text, { size, weight = 400, x = 0, y = 0, tracking = 0, features = [] }) {
  const f = font(weight);
  const s = size / f.unitsPerEm;
  const run = f.layout(text, features);
  let pen = x;
  const parts = [];
  const contours = [];
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
      for (const c of tp.commands) {
        if (c.command === "moveTo") contours.push([]);
        for (let j = 0; j < c.args.length; j += 2) contours.at(-1).push([c.args[j], c.args[j + 1]]);
      }
    }
    pen += p.xAdvance * s + (i < run.glyphs.length - 1 ? tracking : 0);
  });
  return { d: r2(parts.join("")), bbox: bb, width: bb.maxX - bb.minX, count: run.glyphs.length, contours };
}

function svgDoc(vb, body, title) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.map(f2).join(" ")}" role="img" aria-label="${title}">\n<title>${title}</title>\n${body}\n</svg>\n`;
}

// Closed ellipse; clockwise on screen when cw, else counter-clockwise (for holes under nonzero fill).
const ellipse = (cx, cy, rx, ry, cw = true) => {
  const s = cw ? 1 : 0;
  return `M${P(cx - rx, cy)}A${P(rx, ry)} 0 1 ${s} ${P(cx + rx, cy)}A${P(rx, ry)} 0 1 ${s} ${P(cx - rx, cy)}Z`;
};

/* ---------------------------------------------------------------- candlestick */
// Drawn in a 60 x 226 box: flame top at y=0, foot at y=226.
function candlestick(dark) {
  const holder = dark ? C.brass : C.umber;
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
const O_SIZE = 128;
const T_SIZE = 40;
const T_FEATURES = ["c2sc", "smcp"];

// One fixed tracking for every tagline: the spacing that fits the longer, original tagline to the
// width of a SemiBold ORTHODOXY. Shorter taglines keep it and are centred rather than stretched.
const TAG_TRACKING = (() => {
  const orth = setText("ORTHODOXY", { size: O_SIZE, weight: 600, tracking: O_SIZE * 0.02 });
  const nat = setText(TAGLINE_ALT, { size: T_SIZE, features: T_FEATURES });
  return (orth.width - nat.width) / (nat.count - 1);
})();

function wordmark({ tagline, dark, weight = 600 }) {
  const col = dark
    ? { learn: C.ivory, orth: C.gold, tag: C.ivoryMuted }
    : { learn: C.umber, orth: C.gold, tag: C.umber };
  const capO = O_SIZE * 0.65;
  const yO = 0;
  const orth = setText("ORTHODOXY", { size: O_SIZE, weight, y: yO, tracking: O_SIZE * 0.02 });
  const yL = yO - capO - O_SIZE * 0.14;
  const learn = setText("Learn", { size: 106, weight: 600, y: yL });

  let tag = null;
  if (tagline) {
    const probe = setText(tagline, { size: T_SIZE, weight: 500, features: T_FEATURES, tracking: TAG_TRACKING });
    const tx = orth.bbox.minX + (orth.width - probe.width) / 2 - probe.bbox.minX;
    tag = setText(tagline, { size: T_SIZE, weight: 500, features: T_FEATURES, tracking: TAG_TRACKING, x: tx, y: yO + O_SIZE * 0.38 });
  }

  // Candle: flame a little above "Learn", foot on the ORTHODOXY baseline, clear of every letter.
  const top = learn.bbox.minY - 18;
  const k = (yO + 1 - top) / 226;
  const kx = k * 1.25; // the candle reads better a little wider than drawn
  const cx = Math.min(orth.bbox.minX, learn.bbox.minX) - O_SIZE * 0.16 - 60 * kx;

  const pad = 6;
  const minX = Math.min(cx, tag?.bbox.minX ?? Infinity) - pad;
  const maxX = Math.max(orth.bbox.maxX, learn.bbox.maxX, tag?.bbox.maxX ?? -Infinity) + pad;
  const minY = top - pad;
  const maxY = (tag ? tag.bbox.maxY : orth.bbox.maxY) + pad;
  const body = `<g transform="translate(${f2(cx)} ${f2(top)}) scale(${kx.toFixed(4)} ${k.toFixed(4)})">
${candlestick(dark)}
</g>
<path fill="${col.learn}" d="${learn.d}"/>
<path fill="${col.orth}" d="${orth.d}"/>${tag ? `\n<path fill="${col.tag}" d="${tag.d}"/>` : ""}`;
  const label = tagline ? `Learn Orthodoxy — ${tagline}` : "Learn Orthodoxy";
  return svgDoc([minX, minY, maxX - minX, maxY - minY], body, label);
}

/* ---------------------------------------------------------------- crosses */
// Each cross is centred on (0,0). An arm end is drawn once and rotated into place, so opposite
// and adjacent arms are identical by construction. Returns { svg, w, h } (overall extents).

// Budded end pointing up, with its base at the origin: a short flare, a pointed central bud and
// two round side buds. k scales it with the arm width.
function budEnd(w) {
  const k = w / 9;
  return `<path d="M${P(w / 2, 9 * k)}L${P(6.2 * k, k)}L${P(-6.2 * k, k)}L${P(-w / 2, 9 * k)}Z"/>` +
    `<path d="M${P(5.2 * k, k)}Q${P(6.5 * k, -4 * k)} ${P(0, -11 * k)}Q${P(-6.5 * k, -4 * k)} ${P(-5.2 * k, k)}Z"/>` +
    `<circle cx="${f2(6.6 * k)}" cy="${f2(k)}" r="${f2(3.7 * k)}"/><circle cx="${f2(-6.6 * k)}" cy="${f2(k)}" r="${f2(3.7 * k)}"/>`;
}

function latinCross() {
  // Top and side arms are equal (a); the foot (b) is longer. The whole cross is vertically centred.
  const w = 11, a = 24, b = 50;
  const tip = 11 * (w / 9);
  const c = (a - b) / 2; // crossing point, chosen so top tip and foot tip are equidistant from 0
  const end = budEnd(w);
  const svg = `<rect x="${f2(-w / 2)}" y="${f2(c - a)}" width="${w}" height="${a + b}"/>
<rect x="${-a}" y="${f2(c - w / 2)}" width="${2 * a}" height="${w}"/>
<g transform="translate(0 ${f2(c - a)})">${end}</g><g transform="translate(0 ${f2(c + b)}) rotate(180)">${end}</g>
<g transform="translate(${-a} ${f2(c)}) rotate(-90)">${end}</g><g transform="translate(${a} ${f2(c)}) rotate(90)">${end}</g>`;
  return { svg, w: 2 * (a + tip), h: a + b + 2 * tip };
}

function copticCross() {
  // Four equal straight arms with small three-point (trefoil) ends; the centre is left plain.
  const w = 12, L = 40;
  const side = w / 2 + 1.6;
  const end = `<path d="M${P(w / 2, 7)}L${P(side, 1.5)}L${P(-side, 1.5)}L${P(-w / 2, 7)}Z"/>` +
    `<circle cx="0" cy="-3" r="4.8"/><circle cx="${f2(side)}" cy="1.5" r="4"/><circle cx="${f2(-side)}" cy="1.5" r="4"/>`;
  const arms = [0, 90, 180, 270].map((r) => `<g transform="rotate(${r}) translate(0 ${-L})">${end}</g>`).join("");
  const svg = `<rect x="${-w / 2}" y="${-L}" width="${w}" height="${2 * L}"/><rect x="${-L}" y="${-w / 2}" width="${2 * L}" height="${w}"/>${arms}`;
  const ext = L + 7.8;
  return { svg, w: 2 * ext, h: 2 * ext };
}

const crossArt = (name) => (name === "coptic" ? copticCross() : latinCross());

// Scale a cross to fit a counter: height fraction fh, never wider than fraction fw of the width.
function placeCross(name, { cx, cy, cw, ch, fh, fw, ink }) {
  const art = crossArt(name);
  const s = Math.min((ch * fh) / art.h, (cw * fw) / art.w);
  return `<g fill="${ink}" transform="translate(${f2(cx)} ${f2(cy)}) scale(${s.toFixed(4)})">${art.svg}</g>`;
}

/* ---------------------------------------------------------------- O shapes */
// Speech-bubble tail at the lower left of an ellipse (centre cx,cy; radii rx,ry). Runs clockwise so
// it merges with a clockwise outer contour under the nonzero rule. Its inner edge is an arc at 96%
// of the outer radius, which stays inside the stroke.
function tailPath(cx, cy, rx, ry, drop = 1.0) {
  const on = (deg) => [cx + rx * 0.96 * Math.cos((deg * Math.PI) / 180), cy + ry * 0.96 * Math.sin((deg * Math.PI) / 180)];
  const A = on(162), B = on(116);
  const T = [cx - rx * 1.04, cy + ry * drop];
  const q1 = [cx - rx * 0.92, cy + ry * 0.74];
  const q2 = [cx - rx * 0.6, cy + ry * 0.92];
  return `M${P(...A)}A${P(rx * 0.96, ry * 0.96)} 0 0 0 ${P(...B)}Q${P(...q2)} ${P(...T)}Q${P(...q1)} ${P(...A)}Z`;
}

// Lettermark O: the EB Garamond ExtraBold glyph (calligraphic stress) with a tail.
function garamondO({ size, x = 0 }) {
  const o = setText("O", { size, weight: 800, x });
  const b = o.bbox;
  const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2;
  const rx = (b.maxX - b.minX) / 2, ry = (b.maxY - b.minY) / 2;
  // The counter is the contour with the smaller bounding box.
  const boxes = o.contours.map(bboxOf).sort((p, q) => (p.maxX - p.minX) - (q.maxX - q.minX));
  const inner = boxes[0];
  return {
    d: o.d,
    tail: tailPath(cx, cy, rx, ry),
    counter: { cx: (inner.minX + inner.maxX) / 2, cy: (inner.minY + inner.maxY) / 2, w: inner.maxX - inner.minX, h: inner.maxY - inner.minY },
    bbox: { minX: cx - rx * 1.04, maxX: b.maxX, minY: b.minY, maxY: Math.max(b.maxY, cy + ry) },
  };
}

// Icon O: upright, near-even stroke (sides slightly heavier than top and bottom), drawn with the
// tail and the counter hole as one compound path, so there is no seam between the pieces.
const ICON_O = { rx: 100, ry: 108, side: 30, cap: 24 };
function iconO() {
  const { rx, ry, side, cap } = ICON_O;
  const irx = rx - side, iry = ry - cap;
  return {
    d: ellipse(0, 0, rx, ry, true) + tailPath(0, 0, rx, ry) + ellipse(0, 0, irx, iry, false),
    // The counter fill runs half-way under the stroke.
    fill: { rx: irx + side / 2, ry: iry + cap / 2 },
    counter: { w: 2 * irx, h: 2 * iry },
    bbox: { minX: -rx * 1.04, maxX: rx, minY: -ry, maxY: ry },
  };
}

/* ---------------------------------------------------------------- lettermark */
function lettermark({ cross, dark }) {
  const SIZE = 400;
  const ink = dark ? C.ivory : C.umber;
  const L = setText("L", { size: SIZE, weight: 800 });
  const probe = garamondO({ size: SIZE });
  const O = garamondO({ size: SIZE, x: L.bbox.maxX + SIZE * 0.06 - probe.bbox.minX });
  const Oh = O.bbox.maxY - O.bbox.minY;
  // About 12% larger than the first proposal (Latin 0.50 -> 0.56 of the O's height).
  const fh = (cross === "coptic" ? 0.51 : 0.56) * (Oh / O.counter.h);
  const body = `<path fill="${ink}" d="${L.d}"/>
<path fill="${C.gold}" d="${O.d}"/>
<path fill="${C.gold}" d="${O.tail}"/>
${placeCross(cross, { cx: O.counter.cx, cy: O.counter.cy, cw: O.counter.w, ch: O.counter.h, fh, fw: 0.86, ink })}`;
  const pad = 8;
  const minX = L.bbox.minX - pad, maxX = O.bbox.maxX + pad;
  const minY = Math.min(L.bbox.minY, O.bbox.minY) - pad, maxY = Math.max(L.bbox.maxY, O.bbox.maxY) + pad;
  return svgDoc([minX, minY, maxX - minX, maxY - minY], body, `LO lettermark, ${CROSS_NAME[cross]}`);
}

/* ---------------------------------------------------------------- icons */
// Detailed icon (48 px and up) and the square app icon.
function icon({ cross, dark, square }) {
  const ink = dark ? C.ivory : C.umber;
  const O = iconO();
  const body = `<ellipse cx="0" cy="0" rx="${O.fill.rx}" ry="${O.fill.ry}" fill="${dark ? C.night : C.paper}"/>
<path fill="${C.gold}" d="${r2(O.d)}"/>
${placeCross(cross, { cx: 0, cy: 0, cw: O.counter.w, ch: O.counter.h, fh: 0.62, fw: 0.7, ink })}`;
  const box = O.bbox;
  const side = Math.max(box.maxX - box.minX, box.maxY - box.minY) * (square ? 1.4 : 1.04);
  const mx = (box.minX + box.maxX) / 2, my = (box.minY + box.maxY) / 2;
  const vb = [mx - side / 2, my - side / 2, side, side];
  const bg = square ? `<rect x="${f2(vb[0])}" y="${f2(vb[1])}" width="${f2(side)}" height="${f2(side)}" fill="${dark ? C.night : C.paper}"/>\n` : "";
  return svgDoc(vb, bg + body, `Learn Orthodoxy icon, ${CROSS_NAME[cross]}`);
}

// Favicons drawn on the pixel grid (viewBox = pixel size). Every cross stroke and every counter
// edge at its widest point lands on whole pixels. Rects are [x, y, w, h].
const PIXEL = {
  "16": {
    cx: 9, cy: 8, rx: 6, ry: 7, irx: 4, iry: 5,
    tail: "M3.2 9.5L8.6 14.4Q7 15.9 0.3 16Q3 13.6 3.2 9.5Z",
    latin: [[8, 4, 2, 8], [6, 6, 6, 2]],
    coptic: [[8, 5, 2, 6], [6, 7, 6, 2]],
  },
  "16-notail": {
    cx: 8, cy: 8, rx: 7, ry: 7.5, irx: 5, iry: 5.5,
    latin: [[7, 4, 2, 8], [5, 6, 6, 2]],
    coptic: [[7, 5, 2, 6], [5, 7, 6, 2]],
  },
  "16-square": {
    corner: 3, cx: 8, cy: 8, rx: 6, ry: 6.5, irx: 4, iry: 4.5,
    latin: [[7, 4, 2, 8], [5, 6, 6, 2]],
    coptic: [[7, 5, 2, 6], [5, 7, 6, 2]],
  },
  "32": {
    cx: 17, cy: 15, rx: 13, ry: 14, irx: 7, iry: 10,
    tail: "M6.3 20.6L14.4 28.2Q9.2 31.4 0.8 31.2Q7.1 27.2 6.3 20.6Z",
    latin: [[16, 6, 2, 18], [12, 10, 10, 2]],
    coptic: [[16, 9, 2, 12], [11, 14, 12, 2], [15, 9, 4, 1], [15, 20, 4, 1], [11, 13, 1, 4], [22, 13, 1, 4]],
  },
  "32-notail": {
    cx: 16, cy: 16, rx: 14, ry: 15, irx: 8, iry: 11,
    latin: [[15, 7, 2, 18], [11, 11, 10, 2]],
    coptic: [[15, 9, 2, 14], [9, 15, 14, 2], [14, 9, 4, 1], [14, 22, 4, 1], [9, 14, 1, 4], [22, 14, 1, 4]],
  },
  "32-square": {
    corner: 6, cx: 17, cy: 15, rx: 11, ry: 12, irx: 7, iry: 8,
    tail: "M7.5 20L15 26.6Q10 29.8 3.5 29.5Q8 26 7.5 20Z",
    latin: [[16, 8, 2, 14], [12, 11, 10, 2]],
    coptic: [[16, 9, 2, 12], [11, 14, 12, 2], [15, 9, 4, 1], [15, 20, 4, 1], [11, 13, 1, 4], [22, 13, 1, 4]],
  },
};

function pixelIcon({ variant, cross, dark }) {
  const v = PIXEL[variant];
  const px = +variant.slice(0, 2);
  const onDark = dark || v.corner;
  const ink = onDark ? C.ivory : C.umber;
  const counter = onDark ? C.night : C.paper;
  const ring = ellipse(v.cx, v.cy, v.rx, v.ry, true) + (v.tail ?? "") + ellipse(v.cx, v.cy, v.irx, v.iry, false);
  const under = { rx: (v.rx + v.irx) / 2, ry: (v.ry + v.iry) / 2 };
  const bg = v.corner ? `<rect width="${px}" height="${px}" rx="${v.corner}" fill="${C.night}"/>\n` : "";
  const body = `${bg}<ellipse cx="${v.cx}" cy="${v.cy}" rx="${under.rx}" ry="${under.ry}" fill="${counter}"/>
<path fill="${C.gold}" d="${ring}"/>
<g fill="${ink}">${v[cross].map(([x, y, w, h]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`).join("")}</g>`;
  return svgDoc([0, 0, px, px], body, `Learn Orthodoxy icon, ${CROSS_NAME[cross]}`);
}

/* ---------------------------------------------------------------- build */
const files = {};
const WEIGHTS = [500, 600, 700, 800];
for (const dark of [false, true]) {
  const d = dark ? "-dark" : "";
  files[`wordmark${d}.svg`] = wordmark({ tagline: TAGLINE, dark });
  files[`wordmark-alt${d}.svg`] = wordmark({ tagline: TAGLINE_ALT, dark });
  files[`wordmark-short${d}.svg`] = wordmark({ tagline: null, dark });
}
for (const w of WEIGHTS) {
  files[`wordmark-w${w}.svg`] = wordmark({ tagline: TAGLINE, dark: false, weight: w });
  files[`wordmark-short-w${w}.svg`] = wordmark({ tagline: null, dark: false, weight: w });
}
for (const cross of CROSSES) {
  for (const dark of [false, true]) {
    const d = dark ? "-dark" : "";
    files[`lettermark-${cross}${d}.svg`] = lettermark({ cross, dark });
    files[`icon-${cross}${d}.svg`] = icon({ cross, dark });
    files[`app-icon-${cross}${d}.svg`] = icon({ cross, dark, square: true });
    for (const variant of ["16", "16-notail", "32", "32-notail"]) {
      files[`icon-${variant}-${cross}${d}.svg`] = pixelIcon({ variant, cross, dark });
    }
  }
  files[`icon-16-square-${cross}.svg`] = pixelIcon({ variant: "16-square", cross });
  files[`icon-32-square-${cross}.svg`] = pixelIcon({ variant: "32-square", cross });
}

fs.rmSync(path.join(OUT, "svg"), { recursive: true, force: true });
fs.rmSync(path.join(OUT, "png"), { recursive: true, force: true });
fs.mkdirSync(path.join(OUT, "svg"), { recursive: true });
fs.mkdirSync(path.join(OUT, "png"), { recursive: true });
for (const [name, svg] of Object.entries(files)) fs.writeFileSync(path.join(OUT, "svg", name), svg);

// PNG renders: rasterise at 4x or more, then downsample (what favicon tools do).
async function png(name, width, outName) {
  const buf = Buffer.from(files[name]);
  const vbWidth = +files[name].match(/viewBox="[^ ]+ [^ ]+ ([^ ]+)/)[1];
  await sharp(buf, { density: Math.min(2400, 72 * Math.max(1, (width * 4) / vbWidth)) })
    .resize({ width, kernel: "lanczos3" })
    .png()
    .toFile(path.join(OUT, "png", outName));
}
function sizesFor(name) {
  if (/^icon-(16|32)-/.test(name)) return [+name.slice(5, 7)];
  if (name.startsWith("wordmark-short")) return [480, 320, 240];
  if (name.startsWith("wordmark")) return [1200, 480]; // taglines are not used below ~400 px
  if (name.startsWith("lettermark")) return [600, 128, 48];
  return [512, 180, 64, 48];
}
const renders = [];
for (const name of Object.keys(files)) {
  const base = name.replace(/\.svg$/, "");
  for (const w of sizesFor(name)) {
    const out = /^icon-(16|32)-/.test(name) ? `${base}.png` : `${base}-${w}.png`;
    await png(name, w, out);
    renders.push(out);
  }
}

/* ---------------------------------------------------------------- sheets */
const fileUrl = (p) => "file:///" + p.replace(/\\/g, "/");
const orig = (f) => fileUrl(path.join(REPO, "orthodox-site/public/brand", f));
const img = (f, w) => `<img src="png/${f}" width="${w}">`;
const zoom = (f, n, k = 8) => `<img src="png/${f}" width="${n * k}" style="image-rendering:pixelated">`;
const cell = (label, inner, dark) => `<figure class="${dark ? "dark" : ""}">${inner}<figcaption>${label}</figcaption></figure>`;
const row = (...cells) => `<div class="row">${cells.join("")}</div>`;

const css = `@font-face{font-family:"EB Garamond";src:url("${fileUrl(path.join(FONT_DIR, "EBGaramond-VF.ttf"))}");font-weight:400 800}
body{margin:0;padding:32px;background:#fff;font:14px/1.4 Georgia,serif;color:#333;width:1600px}
h1{font-size:24px;margin:0 0 12px}h2{font-size:17px;margin:28px 0 10px;border-bottom:1px solid #ccc}
p{margin:0 0 12px;max-width:1100px}
.row{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap;margin-bottom:18px}
figure{margin:0;padding:16px;background:${C.paper};border:1px solid #ddd;display:flex;flex-direction:column;gap:8px;align-items:flex-start}
figure.dark{background:${C.night}}figure.dark figcaption{color:#ccc}
figcaption{font:12px/1.3 system-ui,sans-serif;color:#555;max-width:760px}
.pair{display:flex;gap:12px;align-items:flex-end}
.sw{width:210px}.sw div{align-self:stretch;height:64px;border:1px solid #ccc}
.tabs{display:flex;flex-direction:column;gap:0;width:560px}
.strip{display:flex;gap:2px;padding:8px 8px 0;background:#dee1e6}
.strip.darkstrip{background:#202124}
.tab{display:flex;align-items:center;gap:8px;padding:8px 14px;border-radius:8px 8px 0 0;font:13px system-ui;color:#1f1f1f;width:150px}
.strip .tab{background:#f1f3f4}.strip .tab.active{background:#fff}
.darkstrip .tab{background:#292a2d;color:#e8eaed}.darkstrip .tab.active{background:#35363a}
.hdr{display:flex;align-items:center;gap:12px;width:720px;height:64px;padding:0 20px;box-sizing:border-box;background:${C.paper};border-bottom:1px solid ${C.antique}55}
.hdr b{font:600 24px/1 "EB Garamond",serif;color:${C.umber};letter-spacing:.005em}
.hdr nav{margin-inline-start:auto;display:flex;gap:22px;font:500 17px/1 "EB Garamond",serif;font-variant-caps:all-small-caps;letter-spacing:.06em;color:${C.umber}}
.hdr.dk{background:${C.night};border-color:${C.brass}66}.hdr.dk b,.hdr.dk nav{color:${C.ivory}}`;

const tabStrip = (dark, icons) =>
  `<div class="strip ${dark ? "darkstrip" : ""}">${icons
    .map(([f, label], i) => `<div class="tab ${i === 0 ? "active" : ""}">${img(f, 16)}${label}</div>`)
    .join("")}</div>`;

const header = (cross, dark) =>
  `<div class="hdr ${dark ? "dk" : ""}">${img(`lettermark-${cross}${dark ? "-dark" : ""}-48.png`, 48)}<b>Learn Orthodoxy</b><nav><span>Ask</span><span>Catechism</span><span>Saints</span></nav></div>`;

const sheets = {
  "sheet-1-wordmark": `<h1>Wordmark</h1>
<p>Tagline tracking is now fixed (${(TAG_TRACKING / T_SIZE).toFixed(2)} em, the spacing of the original tagline) and centred under ORTHODOXY. Tagline versions are rendered at 480 px and up only; below that, use the short version. The candlestick on dark is brass (${C.brass}).</p>
${row(
  cell("Original (PNG)", `<img src="${orig("LearnOrthodoxyLogo-Wordmark2.png")}" width="560">`),
  cell("Main: “A Coptic Orthodox Study Guide”", img("wordmark-1200.png", 700)),
)}
${row(
  cell("Alternate (original wording)", img("wordmark-alt-1200.png", 700)),
  cell("Main, light on dark (new tagline, brass candlestick)", img("wordmark-dark-1200.png", 700), true),
)}
${row(cell("Alternate, light on dark", img("wordmark-alt-dark-1200.png", 700), true))}
<h2>ORTHODOXY weight (the current version is already SemiBold 600, so Bold and ExtraBold are included as the heavier options)</h2>
${row(...WEIGHTS.map((w) => cell(`${w} — ${{ 500: "Medium", 600: "SemiBold (current)", 700: "Bold", 800: "ExtraBold" }[w]}`, img(`wordmark-w${w}-1200.png`, 700))))}
<h2>Weight at header sizes (short version, 320 and 240 px wide)</h2>
${row(...WEIGHTS.map((w) => cell(`${w}`, `<div class="pair">${img(`wordmark-short-w${w}-320.png`, 320)}${img(`wordmark-short-w${w}-240.png`, 240)}</div>`)))}
<h2>Smaller sizes</h2>
${row(
  cell("480 px with tagline (smallest tagline size)", img("wordmark-480.png", 480)),
  cell("480 px, dark", img("wordmark-dark-480.png", 480), true),
)}
${row(
  cell("Short, 320 px", img("wordmark-short-320.png", 320)),
  cell("Short, 240 px", img("wordmark-short-240.png", 240)),
  cell("Short, 320 px, dark", img("wordmark-short-dark-320.png", 320), true),
  cell("Short, 240 px, dark", img("wordmark-short-dark-240.png", 240), true),
)}`,

  "sheet-2-lettermark": `<h1>Lettermark</h1>
<p>The cross is about 12% larger and centred on the O's counter (measured from the glyph outline). The Coptic cross has four identical straight arms, smaller trefoil ends and a plain centre. The Latin cross has a heavier stroke, and its top and side arms are equal.</p>
${row(
  cell("Original", `<img src="${orig("LearnOrthodoxyLogo-Lettermark2.png")}" width="300">`),
  ...CROSSES.map((c) => cell(CROSS_NAME[c], img(`lettermark-${c}-600.png`, 360))),
)}
${row(...CROSSES.map((c) => cell(`${CROSS_NAME[c]}, dark`, img(`lettermark-${c}-dark-600.png`, 360), true)))}
<h2>128 and 48 px wide</h2>
${row(
  ...CROSSES.map((c) => cell(CROSS_NAME[c], `<div class="pair">${img(`lettermark-${c}-128.png`, 128)}${img(`lettermark-${c}-48.png`, 48)}</div>`)),
  ...CROSSES.map((c) => cell(`${CROSS_NAME[c]}, dark`, `<div class="pair">${img(`lettermark-${c}-dark-128.png`, 128)}${img(`lettermark-${c}-dark-48.png`, 48)}</div>`, true)),
)}
${row(...CROSSES.map((c) => cell(`${CROSS_NAME[c]}, 48 px zoomed 4× (nearest neighbour)`, zoom(`lettermark-${c}-48.png`, 48, 4))))}
<h2>Mock site header: 48 px lettermark + “Learn Orthodoxy” in EB Garamond SemiBold, nav in small caps</h2>
${CROSSES.map((c) => row(cell(`${CROSS_NAME[c]}, paper`, header(c, false)), cell(`${CROSS_NAME[c]}, dark`, header(c, true), true))).join("")}`,

  "sheet-3-icons": `<h1>Icons</h1>
<p><b>Detailed icon and app icon (48 px and up):</b> an upright O with a nearly even stroke, drawn together with its tail as one compound path. The counter fill extends halfway under the stroke, so no background shows at the join. The cross is centred on the counter.
<b>Favicons:</b> drawn on the 16 and 32 px pixel grid. At 16 px the stroke is thinner (2 px) and the cross is 2 px wide. “Square” is the dark app-icon design, which stays visible on light tabs.</p>
${CROSSES.map(
  (c) => `<h2>${CROSS_NAME[c]}</h2>
${row(
  cell("Detailed 180", img(`icon-${c}-180.png`, 180)),
  cell("Detailed 180, dark", img(`icon-${c}-dark-180.png`, 180), true),
  cell("App icon 180", img(`app-icon-${c}-180.png`, 180)),
  cell("App icon 180, dark", img(`app-icon-${c}-dark-180.png`, 180), true),
  cell("Seam check: 48 and 64 px, zoomed 4×", `<div class="pair">${zoom(`icon-${c}-48.png`, 48, 4)}${zoom(`icon-${c}-64.png`, 64, 4)}</div>`),
  cell("Seam check, dark", `<div class="pair">${zoom(`icon-${c}-dark-48.png`, 48, 4)}${zoom(`icon-${c}-dark-64.png`, 64, 4)}</div>`, true),
)}
${row(
  ...[
    ["16", "16 px, tail"],
    ["16-notail", "16 px, no tail"],
    ["16-square", "16 px, dark square"],
    ["32", "32 px, tail"],
    ["32-notail", "32 px, no tail"],
    ["32-square", "32 px, dark square (tail)"],
  ].map(([v, label]) => {
    const n = +v.slice(0, 2);
    return cell(`${label} — actual size and 8×`, `<div class="pair">${img(`icon-${v}-${c}.png`, n)}${zoom(`icon-${v}-${c}.png`, n)}</div>`);
  }),
)}
${row(
  ...["16", "16-notail", "32", "32-notail"].map((v) => {
    const n = +v.slice(0, 2);
    return cell(`${v.replace("-notail", " px, no tail").replace(/^(\d+)$/, "$1 px, tail")}, dark-page version — 8×`, `<div class="pair">${img(`icon-${v}-${c}-dark.png`, n)}${zoom(`icon-${v}-${c}-dark.png`, n)}</div>`, true);
  }),
)}
${row(
  cell(
    "Browser tabs at 16 px: light theme (top) and dark theme (bottom). Each tab shows one candidate.",
    `<div class="tabs">${tabStrip(false, [[`icon-16-${c}.png`, "Tail"], [`icon-16-notail-${c}.png`, "No tail"], [`icon-16-square-${c}.png`, "Dark square"]])}
${tabStrip(true, [[`icon-16-${c}.png`, "Tail"], [`icon-16-notail-${c}.png`, "No tail"], [`icon-16-square-${c}.png`, "Dark square"]])}</div>`,
  ),
)}`,
).join("")}`,

  "sheet-4-palette": `<h1>Palette</h1>
${row(
  ...[
    ["Paper (background)", C.paper, "—"],
    ["Umber (text, L, candle holder)", C.umber, "9.9 : 1 on paper"],
    ["Gold (large use: ORTHODOXY, O)", C.gold, "1.8 : 1 on paper — logo / large ornament only"],
    ["Antique gold (small use: hairlines, labels)", C.antique, "4.9 : 1 on paper, AA for text"],
    ["Rubric red (initials, marks, citation numbers)", C.red, "7.6 : 1 on paper"],
    ["Night (dark background)", C.night, "ivory 13.5 : 1, gold 7.9 : 1"],
    ["Ivory (text on dark)", C.ivory, ""],
    ["Brass (candlestick on dark)", C.brass, "4.9 : 1 on night"],
  ].map(([n, h, note]) => `<figure class="sw"><div style="background:${h}"></div><figcaption><b>${n}</b><br>${h}<br>${note}</figcaption></figure>`),
)}`,
};

const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const [name, html] of Object.entries(sheets)) {
  const file = path.join(OUT, `${name}.html`);
  fs.writeFileSync(file, `<!doctype html><meta charset="utf-8"><style>${css}</style><body>${html}</body>`);
  await page.goto(fileUrl(file));
  await page.waitForLoadState("load");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}
await browser.close();
console.log(`tagline tracking ${(TAG_TRACKING / T_SIZE).toFixed(3)} em`);
console.log(`${Object.keys(files).length} SVGs, ${renders.length} PNGs, ${Object.keys(sheets).length} sheets -> ${OUT}`);
