// Lighthouse, mobile and desktop presets, on a production build (UI-003).
//   BASE_URL=http://localhost:3217 CHROME_BIN=/path/to/chrome node lighthouse.mjs <out-dir> [runs]
// Writes one full report per page/preset/run and a summary, _lighthouse.json.
import lighthouse from "lighthouse";
import desktopConfig from "lighthouse/core/config/desktop-config.js";
import * as chromeLauncher from "chrome-launcher";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE_URL || "http://localhost:3217";
const OUT = process.argv[2];
const RUNS = Number(process.argv[3] || 2);
// Lighthouse reports an error instead of scores for a page that answers 404, so the 404 page is
// covered by capture.mjs (axe) only.
const PAGES = [["home", "/"], ["chat", "/chat"], ["credits", "/credits"], ["contact", "/contact"]];
fs.mkdirSync(path.join(OUT, "lighthouse"), { recursive: true });

const chrome = await chromeLauncher.launch({ chromePath: process.env.CHROME_BIN, chromeFlags: ["--headless=new"] });
const summary = {};
try {
  for (const [name, url] of PAGES) {
    for (const preset of ["mobile", "desktop"]) {
      for (let run = 1; run <= RUNS; run++) {
        const result = await lighthouse(
          BASE + url,
          { port: chrome.port, output: "json", logLevel: "error" },
          preset === "desktop" ? desktopConfig : undefined
        );
        const lhr = result.lhr;
        fs.writeFileSync(path.join(OUT, "lighthouse", `${name}-${preset}-${run}.json`), result.report);
        if (lhr.runtimeError) throw new Error(`${name} ${preset}: ${lhr.runtimeError.message}`);
        const fonts = (lhr.audits["network-requests"].details?.items ?? []).filter((r) => r.resourceType === "Font");
        const a = lhr.audits;
        (summary[`${name}-${preset}`] ??= []).push({
          performance: Math.round(lhr.categories.performance.score * 100),
          accessibility: Math.round(lhr.categories.accessibility.score * 100),
          bestPractices: Math.round(lhr.categories["best-practices"].score * 100),
          seo: Math.round(lhr.categories.seo.score * 100),
          fcp: Math.round(a["first-contentful-paint"].numericValue),
          lcp: Math.round(a["largest-contentful-paint"].numericValue),
          cls: Number(a["cumulative-layout-shift"].numericValue.toFixed(3)),
          tbt: Math.round(a["total-blocking-time"].numericValue),
          totalKB: Math.round(a["total-byte-weight"].numericValue / 1024),
          fontFiles: fonts.length,
          fontKB: Math.round(fonts.reduce((sum, r) => sum + (r.transferSize || 0), 0) / 1024),
          lcpElement: a["largest-contentful-paint-element"]?.details?.items?.[0]?.items?.[0]?.node?.snippet?.slice(0, 120) ?? null,
        });
        console.log(name, preset, run, JSON.stringify(summary[`${name}-${preset}`].at(-1)));
      }
    }
  }
} finally {
  fs.writeFileSync(path.join(OUT, "_lighthouse.json"), JSON.stringify(summary, null, 1));
  try {
    await chrome.kill();
  } catch (error) {
    // Windows sometimes keeps the profile folder locked; the results are already written.
    console.warn("chrome cleanup:", error.code ?? error.message);
  }
}
