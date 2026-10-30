import { readFileSync } from "node:fs";
import type { Page, Route } from "@playwright/test";
import { expect, test } from "./test";
import { event, month, setup } from "./fixtures";

const fixture = JSON.parse(readFileSync(new URL("../fixtures/golf-leaderboard.json", import.meta.url), "utf8")).payloads;
const endpoint = /^https:\/\/site\.web\.api\.espn\.com\/apis\/site\/v2\/sports\/golf\/leaderboard\?/;
const now = "2026-10-30T17:00:00Z";
const golf = (id = "401850978", league = "PGA_TOUR", title = "VidantaWorld Mexico Open", date = "2026-10-29", end = "2026-11-01") =>
  event(`espn-${league.toLowerCase()}-${id}`, date, { source: "espn", sport: "golf", league, title,
    event_type: "tournament", country: null, venue: null, city: null, end_calendar_date: end,
    source_url: `https://www.espn.com/golf/leaderboard?tournamentId=${id}` });
const fulfill = (route: Route, json: unknown) => route.fulfill({ json, headers: { "access-control-allow-origin": "*" } });
async function mock(page: Page, answer = (_call: number) => fixture.live) {
  const calls: string[] = [];
  await page.route(endpoint, async (route) => {
    const request = route.request();
    calls.push(request.method());
    expect(request.method()).toBe("GET");
    expect(request.postData()).toBeNull();
    expect(request.headers()["content-type"]).toBeUndefined();
    expect(request.headers().authorization).toBeUndefined();
    expect(Object.keys(request.headers()).some((key) => key.startsWith("x-"))).toBe(false);
    await fulfill(route, answer(calls.length));
  });
  return calls;
}
async function paused(page: Page) {
  await page.clock.install({ time: new Date(now) });
  await page.clock.pauseAt(new Date(now));
}
async function open(page: Page, date = "2026-10-30", name = "VidantaWorld Mexico Open") {
  await page.locator(`#day-${date} .event-pill`).filter({ hasText: name }).click();
}

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`golf rounds and top five ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("daily all-day pills, sorted ties, round scores, local tee time and single-date popup", async ({ page }) => {
      const calls = await mock(page);
      await setup(page, [golf(), golf("401811953", "PGA_TOUR", "Other tournament")], { now });
      const cell = page.locator("#day-2026-10-30");
      await expect(cell.locator(".event-pill")).toHaveCount(2);
      await expect(cell.locator(".pill-text")).toHaveText(["Other tournament, Round 2", "VidantaWorld Mexico Open, Round 2"]);
      await open(page);
      const sheet = page.getByRole("dialog");
      await expect(sheet.locator("h3")).toHaveText("VidantaWorld Mexico Open, Round 2");
      await expect(sheet).toContainText("Friday, October 30, 2026");
      await expect(sheet).not.toContainText("Time TBD");
      await expect(sheet).not.toContainText("through");
      const table = sheet.getByRole("table");
      await expect(table.locator("tbody tr")).toHaveCount(5);
      await expect(table.locator("tbody tr td:nth-child(2)")).toHaveText(["Mackenzie Hughes", "Jackson Suber", "Matthieu Pavon", "Adrien Dumont de Chassart", "Kensei Hirata"]);
      await expect(table.locator("tbody tr").first().locator("td")).toHaveText(["T1", "Mackenzie Hughes", "-6", "-2", "12"]);
      await expect(table.locator("tbody tr").last().locator("td").nth(3)).toHaveText("2:13 PM");
      expect(calls).toEqual(["GET"]);
      expect(await sheet.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/golf-top-five-${width}-${colorScheme}.png` });
    });
  });
}

test.describe("leaderboard lifecycle", () => {
  test.use({ reducedMotion: "reduce" });
  test("refreshes at 60 seconds only until the round completes, including LPGA's overnight shape", async ({ page }) => {
    await paused(page);
    const finishedRound = structuredClone(fixture.live);
    finishedRound.events[0].competitions[0].status.type = { name: "STATUS_PLAY_COMPLETE", state: "post" };
    const calls = await mock(page, (call) => call === 1 ? fixture.live : finishedRound);
    await setup(page, [golf()], { now });
    await open(page);
    await expect(page.getByRole("table")).toBeVisible();
    await page.clock.runFor(59_999);
    expect(calls).toHaveLength(1);
    await page.clock.runFor(1);
    await expect.poll(() => calls.length).toBe(2);
    await page.clock.runFor(180_000);
    expect(calls).toHaveLength(2);
  });

  test("a failed refresh hides the table, retains the source and retries an active round", async ({ page }) => {
    await paused(page);
    let calls = 0;
    const finishedRound = structuredClone(fixture.live);
    finishedRound.events[0].competitions[0].status.type = { name: "STATUS_PLAY_COMPLETE", state: "post" };
    await page.route(endpoint, async (route) => {
      calls++;
      if (calls === 2) await route.fulfill({ status: 503, body: "unavailable", headers: { "access-control-allow-origin": "*" } });
      else await fulfill(route, calls > 2 ? finishedRound : fixture.live);
    });
    await setup(page, [golf()], { now });
    await open(page);
    await expect(page.getByRole("table")).toBeVisible();
    await page.clock.runFor(60_000);
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Schedule source/ })).toBeVisible();
    await page.clock.runFor(60_000);
    await expect(page.getByRole("table")).toBeVisible();
    expect(calls).toBe(3);
    await page.clock.runFor(180_000);
    expect(calls).toBe(3);
  });

  test("closing just before a refresh cancels the timer immediately", async ({ page }) => {
    await paused(page);
    const calls = await mock(page);
    await setup(page, [golf()], { now });
    await open(page);
    await expect(page.getByRole("table")).toBeVisible();
    await page.clock.runFor(59_999);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.clock.runFor(180_001);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(calls).toHaveLength(1);
  });

  test("a delayed response after closing cannot write into another tournament", async ({ page }) => {
    let release!: () => void;
    const hold = new Promise<void>((resolve) => { release = resolve; });
    let oldStarted = false;
    let oldFinished!: () => void;
    const done = new Promise<void>((resolve) => { oldFinished = resolve; });
    await page.route(endpoint, async (route) => {
      if (new URL(route.request().url()).searchParams.get("event") === "401850978") {
        oldStarted = true;
        await hold;
        await fulfill(route, fixture.live).catch(() => {});
        oldFinished();
      } else await fulfill(route, fixture.between_rounds);
    });
    await setup(page, [golf(), golf("401835174", "LPGA_TOUR", "Maybank Championship")], { now });
    await open(page);
    await expect.poll(() => oldStarted).toBe(true);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await open(page, "2026-10-30", "Maybank Championship");
    await expect(page.getByRole("table")).toContainText("Miyu Yamashita");
    release();
    await done;
    await expect(page.getByRole("table")).toContainText("Miyu Yamashita");
    await expect(page.getByRole("table")).not.toContainText("Mackenzie Hughes");
  });

  test("a future round makes no request and an ongoing past round has no historical snapshot", async ({ page }) => {
    await paused(page);
    const calls = await mock(page);
    await setup(page, [golf()], { now });
    await open(page, "2026-10-31");
    await expect(page.getByRole("dialog").locator("h3")).toHaveText("VidantaWorld Mexico Open, Round 3");
    await page.clock.runFor(120_000);
    expect(calls).toHaveLength(0);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.clock.runFor(1);
    await open(page, "2026-10-29");
    await expect.poll(() => calls.length).toBe(1);
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Schedule source/ })).toBeVisible();
    await page.clock.runFor(180_000);
    expect(calls).toHaveLength(1);
  });

  test("a past day shows final tournament standings once and labels the actual final round", async ({ page }) => {
    await paused(page);
    const calls = await mock(page, () => fixture.final);
    await setup(page, [golf("401835149", "LPGA_TOUR", "The Chevron Championship", "2026-04-23", "2026-04-26")], { now });
    await month(page, "April 2026");
    await open(page, "2026-04-23", "The Chevron Championship");
    const sheet = page.getByRole("dialog");
    await expect(sheet.locator("h3")).toHaveText("The Chevron Championship, Round 1");
    await expect(sheet.getByRole("table")).toHaveAccessibleName("Final tournament top 5 · ESPN");
    await expect(sheet.getByRole("columnheader", { name: "Round 4", exact: true })).toBeVisible();
    await expect(sheet.getByRole("table")).toContainText("Nelly Korda");
    await page.clock.runFor(180_000);
    expect(calls).toHaveLength(1);
  });

  test("an LPGA round completed overnight shows local upcoming tee times without polling", async ({ page }) => {
    await paused(page);
    const calls = await mock(page, () => fixture.between_rounds);
    await setup(page, [golf("401835174", "LPGA_TOUR", "Maybank Championship")], { now });
    await open(page, "2026-10-30", "Maybank Championship");
    await expect(page.getByRole("table").locator("tbody tr").first().locator("td").nth(3)).toHaveText("8:27 PM");
    await page.clock.runFor(180_000);
    expect(calls).toHaveLength(1);
  });

  for (const failure of ["http", "json", "wrong-event"]) {
    test(`${failure} failure silently leaves the source link`, async ({ page }) => {
      let calls = 0;
      await page.route(endpoint, async (route) => {
        calls++;
        if (failure === "http") await route.fulfill({ status: 503, body: "unavailable", headers: { "access-control-allow-origin": "*" } });
        else if (failure === "json") await route.fulfill({ contentType: "application/json", body: "{", headers: { "access-control-allow-origin": "*" } });
        else await fulfill(route, fixture.final);
      });
      await setup(page, [golf()], { now });
      await open(page);
      await expect.poll(() => calls).toBe(1);
      await expect(page.getByRole("table")).toHaveCount(0);
      await expect(page.getByRole("link", { name: /Schedule source/ })).toBeVisible();
      await expect(page.getByRole("dialog")).not.toContainText("unavailable");
    });
  }
});
