// Records a scripted walkthrough of the live Quiet Hours dashboard with Playwright.
// Writes out/raw.webm and out/markers.json (scene name -> seconds from video start).
import { chromium } from "playwright";
import fs from "node:fs";

const URL = process.env.QH_DASHBOARD_URL || "https://quiet-hours-five.vercel.app";
const OUT = "out";
const markers = [];
let t0;
const mark = (name) => { const t = (Date.now() - t0) / 1000; markers.push({ name, t }); console.log(`[${t.toFixed(1)}s] ${name}`); };
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, recordVideo: { dir: OUT, size: { width: 1440, height: 900 } } });
const page = await context.newPage();
t0 = Date.now();
await page.goto(URL, { waitUntil: "networkidle" });
await pause(1500);

async function clickTop(name) {
  const b = page.getByRole("button", { name, exact: true });
  await b.hover(); await pause(400); await b.click();
}
async function waitIdle() {
  await page.waitForSelector('button:has-text("Run sweep now"):not([disabled])', { timeout: 180000 });
  await page.waitForSelector('button:has-text("Next day"):not([disabled])', { timeout: 180000 });
  await pause(1200);
}
async function decide(cardText, buttonName) {
  const card = page.locator(".card", { hasText: cardText }).first();
  try { await card.waitFor({ state: "visible", timeout: 6000 }); } catch { console.log(`(no card for ${cardText}, skipping)`); markers.push({ name: `skipped-${cardText}`, t: (Date.now() - t0) / 1000 }); return; }
  await card.scrollIntoViewIfNeeded();
  await card.hover(); await pause(900);
  const btn = card.getByRole("button", { name: buttonName, exact: true });
  await btn.hover(); await pause(500); await btn.click();
  await card.waitFor({ state: "detached", timeout: 120000 });
  await pause(1200);
}

mark("open-day0");
await clickTop("Start over"); await waitIdle(); await page.reload({ waitUntil: "networkidle" }); await pause(1500);
mark("day0-clean");

// Day 1
await clickTop("Next day"); await waitIdle(); mark("day1-arrived");
await pause(2500);
await clickTop("Run sweep now"); mark("day1-sweep-start"); await waitIdle(); mark("day1-sweep-done");
await pause(3000);
await page.locator(".timeline").first().hover(); await pause(2500); mark("day1-timeline");
await decide("Austin Energy", "Approve and trust from now on"); mark("day1-trust-energy");
await decide("Lonestar", "Decline"); mark("day1-deny-insurance");
await decide("permission", "Approve"); mark("day1-approve-form");
await page.locator(".bottom").scrollIntoViewIfNeeded(); await pause(2500); mark("day1-permissions");
await page.mouse.wheel(0, -2000); await pause(1000);

// Day 2
await clickTop("Next day"); await waitIdle(); mark("day2-arrived");
await clickTop("Run sweep now"); mark("day2-sweep-start"); await waitIdle(); mark("day2-sweep-done");
await pause(2500);
await decide("Keys & Chords", "Approve and trust from now on"); mark("day2-trust-piano");
await decide("Netflix", "Decline"); mark("day2-deny-netflix");

// Day 3
await clickTop("Next day"); await waitIdle(); mark("day3-arrived");
await clickTop("Run sweep now"); mark("day3-sweep-start"); await waitIdle(); mark("day3-sweep-done");
await pause(2500);
await page.locator(".timeline").first().hover(); await pause(2000); mark("day3-timeline");
await page.locator(".bottom").scrollIntoViewIfNeeded(); await pause(3000); mark("day3-trend");

// Ask
const input = page.getByLabel("Ask Quiet Hours a question");
await input.click(); await pause(400);
await input.pressSequentially("Why did you pay the piano invoice without asking me?", { delay: 45 });
await pause(600); mark("ask-typed");
await page.getByRole("button", { name: "Ask", exact: true }).click();
await page.locator(".answer").waitFor({ timeout: 120000 }); await pause(6000); mark("ask-answered");

const video = page.video();
await context.close();
const path = await video.path();
fs.renameSync(path, `${OUT}/raw.webm`);
fs.writeFileSync(`${OUT}/markers.json`, JSON.stringify(markers, null, 2));
await browser.close();
console.log("done", markers.length, "markers");
