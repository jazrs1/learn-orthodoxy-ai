// Renders og-image.html to orthodox-site/public/og-image.png (1200x630).
// Run from a directory where `playwright` is installed: node og-image.mjs
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = process.env.REPO_ROOT || path.resolve(here, "../..");
const site = path.join(repo, "orthodox-site");
const cross = fs.readFileSync(path.join(site, "public/cross-mark.png")).toString("base64");
const html = fs
  .readFileSync(process.env.OG_HTML || path.join(here, "og-image.html"), "utf-8")
  .replace("CROSS_SRC", `data:image/png;base64,${cross}`);

const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await page.setContent(html, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
const out = path.join(site, "public/og-image.png");
await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 1200, height: 630 } });
await browser.close();
console.log("wrote", out);
