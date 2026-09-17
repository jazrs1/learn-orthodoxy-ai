import { chromium } from "playwright";
const OUT = "C:/Users/johnb/Projects/learn-orthodoxy-ai/ui-audit/before/";
const b = await chromium.launch({ executablePath: process.env.CHROME_BIN });
let ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
let p = await ctx.newPage();
await p.route("**/api/**", (r) => r.fulfill({ contentType: "application/json", body: '{"conversations":[]}' }));
await p.goto("http://localhost:3217/about", { waitUntil: "networkidle" });
await p.screenshot({ path: OUT + "en-desktop-22-about-orphan.png" });
await ctx.close();
// Server-rendered HTML with JS off: what an Arabic visitor sees before hydration.
ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, javaScriptEnabled: false });
await ctx.addCookies([{ name: "lo_lang", value: "ar", url: "http://localhost:3217" }]);
p = await ctx.newPage();
await p.goto("http://localhost:3217/", { waitUntil: "load" });
await p.screenshot({ path: OUT + "ar-mobile-23-first-paint-before-hydration.png" });
await ctx.close();
// Multi-line question: the composer does not grow.
ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
p = await ctx.newPage();
await p.route("**/api/**", (r) => r.fulfill({ contentType: "application/json", body: '{"conversations":[]}' }));
await p.goto("http://localhost:3217/chat", { waitUntil: "networkidle" });
await p.fill(".chat-input", "I have a long question about fasting.\nFirst, why do we fast on Wednesdays and Fridays?\nSecond, how should a beginner start?\nThird, what if I am sick?");
await p.waitForTimeout(300);
await p.screenshot({ path: OUT + "en-mobile-24-multiline-composer.png" });
await b.close();
