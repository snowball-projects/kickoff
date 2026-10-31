import { readFileSync } from "node:fs";
import type { Page, Route } from "@playwright/test";
import { expect, test } from "./test";
import { agendaToggle, event, setup } from "./fixtures";
const boards = JSON.parse(readFileSync(new URL("../fixtures/golf-leaderboard.json", import.meta.url), "utf8")).payloads;
const now = "2026-10-30T17:00:00Z";
const endpoint = /^https:\/\/site\.web\.api\.espn\.com\/apis\/site\/v2\/sports\/golf\/leaderboard\?/;
const golf = (id = "401850978", title = "Tournament", start = "2026-10-29", end = "2026-11-01") => event(`espn-pga_tour-${id}`, start,
  { title, source: "espn", sport: "golf", league: "PGA_TOUR", competition_phase: "championship", event_type: "tournament",
    country: null, venue: null, city: null, end_calendar_date: end, source_url: `https://www.espn.com/golf/leaderboard?tournamentId=${id}` });
const answer = (route: Route, payload: unknown) => route.fulfill({ json: payload, headers: { "access-control-allow-origin": "*" } });
async function mock(page: Page, payload = boards.live) {
  const calls: string[] = [];
  await page.route(endpoint, async (route) => {
    expect(route.request().method()).toBe("GET");
    expect(route.request().headers()["content-type"]).toBeUndefined();
    expect(route.request().headers().authorization).toBeUndefined();
    calls.push(route.request().url()); await answer(route, payload);
  });
  return calls;
}
async function enter(page: Page, events = [golf()], time = now, paused = false) {
  await setup(page, events, { now: time });
  if (paused) await pause(page);
  await agendaToggle(page).click();
}
async function pause(page: Page) {
  await page.clock.install({ time: new Date(now) });
  await page.clock.pauseAt(new Date(now));
}
async function observed(page: Page, visible: boolean) {
  await page.evaluate((visible) => new Promise<void>((resolve) => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting === visible) { observer.disconnect(); resolve(); }
    });
    observer.observe(document.querySelector(".golf-board")!);
  }), visible);
}
for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`inline golf ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("centered tournament and round/status, inline sorted top five, whole table opens popup", async ({ page }) => {
      const calls = await mock(page);
      await enter(page);
      const row = page.locator(".agenda-row");
      await expect(row.locator(".agenda-title")).toHaveText("Tournament");
      await expect(row.locator(".agenda-round")).toHaveText("Round 2 · In progress");
      await expect(row.locator("tbody tr")).toHaveCount(5);
      await expect(row.locator("tbody tr").first().locator("td")).toHaveText(["T1", "Mackenzie Hughes", "-6", "-2", "12"]);
      expect(calls).toHaveLength(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/agenda-golf-${width}-${colorScheme}.png` });
      // The row button's transparent hit area includes the passive table.
      await row.click();
      await expect(page.getByRole("dialog").getByRole("table")).toBeVisible();
      await expect.poll(() => calls.length).toBe(2);
      await page.keyboard.press("Escape");
      await expect(row.getByRole("button")).toBeFocused();
    });
  });
}

test("inline and popup never run competing timers; modal and Upcoming pause inline work", async ({ page }) => {
  const calls = await mock(page);
  await enter(page, [golf()], now, true);
  await expect(page.locator(".agenda-row table")).toBeVisible();
  await page.clock.runFor(60_000); await expect.poll(() => calls.length).toBe(2);
  await page.locator(".agenda-row").click();
  await expect(page.getByRole("dialog").getByRole("table")).toBeVisible();
  await expect.poll(() => calls.length).toBe(3);
  await page.clock.runFor(60_000); await expect.poll(() => calls.length).toBe(4);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.clock.runFor(200);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => calls.length).toBe(5);
  await page.clock.runFor(60_000); await expect.poll(() => calls.length).toBe(6);
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  await expect(page.getByRole("dialog")).toContainText("agenda golf sections and event popups contact ESPN");
  await page.clock.runFor(120_000); expect(calls).toHaveLength(6);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.clock.runFor(200);
  await expect.poll(() => calls.length).toBe(7);
  await page.getByRole("button", { name: "Upcoming", exact: true }).click();
  await expect(page.locator(".agenda-row table")).toHaveCount(0);
  await expect(page.locator(".agenda-title").first()).toHaveText("Tournament");
  await page.clock.runFor(120_000); expect(calls).toHaveLength(7);
});

test("scrolling offscreen and hiding the document stop refreshes; returning resumes one timer", async ({ page }) => {
  const calls = await mock(page);
  await enter(page, [golf(), ...Array.from({ length: 25 }, (_, i) => event(`NFL ${i}`, "2026-10-30", { league: "NFL", sport: "football" }))], now, true);
  await expect(page.locator(".agenda-row table")).toBeVisible();
  const hidden = observed(page, false);
  await page.locator(".agenda-scroll").evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await hidden;
  await page.clock.runFor(120_000); expect(calls).toHaveLength(1);
  const visible = observed(page, true);
  await page.locator(".agenda-scroll").evaluate((el) => { el.scrollTop = 0; });
  await visible; await expect.poll(() => calls.length).toBe(2);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { get: () => "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.clock.runFor(120_000); expect(calls).toHaveLength(2);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { get: () => "visible", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => calls.length).toBe(3);
  await page.clock.runFor(60_000); await expect.poll(() => calls.length).toBe(4);
});

test("Yesterday uses final tournament standings once, with the actual final round label", async ({ page }) => {
  const calls = await mock(page, boards.final);
  await enter(page, [golf("401835149", "Completed tournament", "2026-10-30", "2026-11-01")], "2026-11-02T17:00:00Z");
  expect(calls).toHaveLength(0);
  await page.getByRole("button", { name: "Yesterday", exact: true }).click();
  const row = page.locator(".agenda-row");
  await expect(row.locator(".agenda-round")).toHaveText("Round 3 · Final tournament");
  await expect(row.getByRole("table").locator("thead")).toContainText("Round 4");
  await expect(row.getByRole("table").locator("tbody tr")).toHaveCount(5);
  await page.clock.install({ time: new Date("2026-11-02T17:00:00Z") }); await page.clock.fastForward(180_000); expect(calls).toHaveLength(1);
});

test("an ongoing Yesterday has no invented historical standings or refresh; failures stay silent", async ({ page }) => {
  const calls = await mock(page);
  await enter(page);
  await expect.poll(() => calls.length).toBe(1);
  await page.getByRole("button", { name: "Yesterday", exact: true }).click();
  await expect.poll(() => calls.length).toBe(2);
  await expect(page.locator(".agenda-row table")).toHaveCount(0);
  await expect(page.locator(".agenda-row .agenda-round")).toHaveText("Round 1");
  await page.clock.install({ time: new Date(now) }); await page.clock.fastForward(180_000); expect(calls).toHaveLength(2);
  await page.route(endpoint, (route) => route.fulfill({ status: 503, body: "unavailable" }));
  await page.getByRole("group", { name: "Agenda days", exact: true }).getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.locator(".agenda-row table")).toHaveCount(0);
  await expect(page.locator(".agenda-row")).not.toContainText(/unavailable|failed|No leaderboard/);
});


test("a delayed inline response after switching to Upcoming cannot write or schedule a timer", async ({ page }) => {
  let release!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  let started = false;
  await page.route(endpoint, async (route) => { started = true; await hold; await answer(route, boards.live).catch(() => {}); });
  await enter(page);
  await expect.poll(() => started).toBe(true);
  await page.getByRole("button", { name: "Upcoming", exact: true }).click();
  release();
  await expect(page.locator(".agenda-row table")).toHaveCount(0);
  await expect(page.locator(".agenda-stage")).not.toContainText("Mackenzie Hughes");
  await page.clock.install({ time: new Date(now) }); await page.clock.fastForward(120_000);
  await expect(page.locator(".agenda-row table")).toHaveCount(0);
});
