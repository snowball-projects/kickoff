import { readFileSync } from "node:fs";
import { expect, test } from "./test";
import { agendaToggle, event, month, setup } from "./fixtures";
import type { Page } from "@playwright/test";

const today = "2026-10-28";
const golf = event("espn-pga_tour-401850978", today, { title: "Mexico Open", source: "espn", sport: "golf", league: "PGA_TOUR", event_type: "tournament" });
const fixtures = [event("Match"), golf, event("March", "2027-03-02")];
const live = JSON.parse(readFileSync(new URL("../fixtures/golf-leaderboard.json", import.meta.url), "utf8")).payloads.live;
async function logo(page: Page) {
  const rect = (await page.locator(".brand").boundingBox())!;
  // Real pointer coordinates also exercise the native modal backdrop.
  await page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2);
}
async function home(page: Page) {
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(agendaToggle(page)).toHaveAttribute("aria-checked", "false");
  await expect(page.locator(".month-stage")).toBeVisible();
  await expect(page.locator(".year-grid, .day-timeline-stage")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1, exact: true, name: "October" })).toBeVisible();
  await expect(page.locator(`#day-${today} .day-number`)).toBeInViewport();
  expect(await page.evaluate(() => localStorage.getItem("kickoff.view.v1"))).toBe("calendar");
}
for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`small fixes ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("logo returns every view and sheet to today's month, persists without reload, stops agenda golf", async ({ page }) => {
      let documents = 0, calls = 0;
      page.on("request", (request) => { if (request.resourceType() === "document") documents++; });
      await page.route("https://site.web.api.espn.com/**", (route) => { calls++; return route.fulfill({ json: live }); });
      await setup(page, fixtures);
      expect(await page.locator(".brand").evaluate((a: HTMLAnchorElement) => a.href)).toBe(new URL("./", page.url()).href);
      await month(page, "March 2026"); await logo(page); await home(page);
      await page.getByRole("button", { name: /Show .* year calendar/ }).click(); await logo(page); await home(page);
      await page.locator(`#day-${today} .day-number`).click(); await logo(page); await home(page);
      for (const name of ["About kickoff and schedule coverage", "Interests"]) {
        await page.getByRole("button", { name, exact: true }).click();
        await expect(page.getByRole("dialog")).toBeVisible(); await logo(page); await home(page);
      }
      await page.locator(`#day-${today} .event-pill`).first().click();
      await expect(page.getByRole("dialog")).toBeVisible(); await logo(page); await home(page);
      await page.clock.install({ time: new Date("2026-10-28T17:00Z") });
      await page.clock.pauseAt(new Date("2026-10-28T17:01Z"));
      for (const modal of ["none", "golf", "about"]) {
        await agendaToggle(page).click(); await expect(page.locator(".agenda-row table")).toBeVisible();
        if (modal === "golf") {
          await page.locator(".agenda-row").filter({ has: page.getByRole("table") }).click();
          await expect(page.getByRole("dialog").getByRole("table")).toBeVisible();
        } else if (modal === "about") await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
        await logo(page); await home(page);
        const stopped = calls; await page.clock.runFor(120_000); expect(calls).toBe(stopped);
      }
      await logo(page); await logo(page); await home(page);
      await page.locator(".brand").press("Enter"); await home(page);
      expect(documents).toBe(1);
      await page.reload(); await home(page);
      await page.screenshot({ path: `test-results/home-${width}-${colorScheme}.png` });
    });
  });
}

test("a delayed skipped transition cannot overwrite repeated home navigation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.addInitScript(() => {
    const state = window as unknown as { delayed: (() => void)[] };
    state.delayed = [];
    Object.defineProperty(document, "startViewTransition", { configurable: true, value: (update: () => void) => {
      state.delayed.push(update);
      return { skipTransition() {}, finished: Promise.resolve() };
    } });
  });
  await setup(page, fixtures);
  await page.locator(`#day-${today} .day-number`).click();
  await logo(page); await logo(page);
  await page.evaluate(() => (window as unknown as { delayed: (() => void)[] }).delayed.reverse().forEach((update) => update()));
  await home(page);
  await page.getByRole("button", { name: /Show .* year calendar/ }).click();
  await logo(page);
  await page.evaluate(() => (window as unknown as { delayed: (() => void)[] }).delayed.splice(0).forEach((update) => update()));
  await home(page);
});

for (const colorScheme of ["light", "dark"] as const) test(`pill flags follow names and fade tracks true overflow across resize, ${colorScheme}`, async ({ page }) => {
  await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
  await page.setViewportSize({ width: 320, height: 844 });
  await setup(page, [
    event("Short", today, { league: "F1", sport: "motorsport", event_type: "race", country: "JP" }),
    event("Medium", "2026-10-29", { title: "Mexico", league: "PGA_TOUR", sport: "golf", country: "JP" }),
    event("Long", "2026-10-30", { title: "A very long tournament name that cannot fit in a month cell", league: "PGA_TOUR", sport: "golf", country: "JP" }),
  ]);
  const short = page.locator(`#day-${today} .event-pill`), medium = page.locator("#day-2026-10-29 .pill-text"), long = page.locator("#day-2026-10-30 .pill-text");
  await expect(short.locator(".pill-text")).toHaveCSS("mask-image", "none");
  await expect(medium).toHaveClass(/truncated/); await expect(long).toHaveClass(/truncated/);
  await expect(short.locator(".country-flag")).toBeHidden();
  await page.setViewportSize({ width: 1280, height: 844 });
  await expect(medium).not.toHaveClass(/truncated/); await expect(medium).toHaveCSS("mask-image", "none");
  await expect(long).toHaveClass(/truncated/); await expect(long).not.toHaveCSS("mask-image", "none");
  const children = await short.locator(":scope > *").evaluateAll((els) => els.map((el) => el.classList[0]));
  expect(children).toEqual(["sport-icon", "pill-text", "country-flag"]);
  const gap = await short.evaluate((pill) => {
    const text = pill.querySelector(".pill-text")!.getBoundingClientRect(), flag = pill.querySelector(".country-flag")!.getBoundingClientRect();
    return flag.left - text.right;
  });
  expect(gap).toBeCloseTo(3, 0);
  for (const width of [699, 700, 320, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    if (width < 700) await expect(short.locator(".country-flag")).toBeHidden();
    else await expect(short.locator(".country-flag")).toBeVisible();
    await expect.poll(() => medium.evaluate((el) => el.classList.contains("truncated") === (el.scrollWidth > el.clientWidth))).toBe(true);
  }
  await page.screenshot({ path: `test-results/pill-overflow-${colorScheme}.png` });
});


test("home during a sheet close cancels its old dismissal before a new sheet opens", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await setup(page, fixtures);
  await page.clock.install({ time: new Date("2026-10-28T17:00Z") });
  await page.clock.pauseAt(new Date("2026-10-28T17:01Z"));
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveClass(/closing/);
  await logo(page); await home(page);
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await page.clock.runFor(500);
  await expect(page.getByRole("dialog", { name: "Interests", exact: true })).toBeVisible();
  await logo(page); await home(page);
});
