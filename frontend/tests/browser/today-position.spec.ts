import { expect, test, type Page } from "@playwright/test";

const event = (date: string, index: number, league = "F1") => ({
  event_id: `${league}-${date}-${index}`, source: "offline-fixture", season: date.slice(0, 4),
  title: `${league} ${date} fixture ${index}`, calendar_date: date, end_calendar_date: date,
  league, sport: league === "F1" ? "motorsport" : "soccer", event_type: league === "F1" ? "race" : "match",
  status: "scheduled", competition_phase: "regular_season", tags: [], participants: [],
  start_time_utc: null, start_time_local: null,
});
const events = Array.from({ length: 122 }, (_, index) => {
  const date = new Date(Date.UTC(2026, 8, 1 + index)).toISOString().slice(0, 10);
  return [...Array.from({ length: 8 }, (_, i) => event(date, i)), event(date, 0, "EPL")];
}).flat();
const feed = (page: Page) => page.locator(".month-feed");
const view = (page: Page, name: string) => page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name, exact: true });
async function weekOffset(page: Page, date: string) {
  return page.locator(`#day-${date}`).evaluate((element) => {
    const root = element.closest(".month-feed")!;
    const box = element.getBoundingClientRect();
    return box.top + box.height / 2 - root.getBoundingClientRect().top - root.clientHeight / 2;
  });
}
async function setup(page: Page, waitForData?: Promise<void>, saved = true) {
  if (saved) await page.addInitScript(() => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["EPL", "F1"] }));
  });
  await page.route("**/data/*.json", async (route) => {
    const year = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    if (year === 2026) await waitForData;
    await route.fulfill({ json: { schema_version: "1", season: year, providers: [], available_seasons: [2026, 2027],
      events: events.filter((item) => item.season === String(year)) } });
  });
  await page.goto("/");
}
async function removeSoccer(page: Page) {
  await page.getByRole("button", { name: /^Interests/ }).click();
  const modal = page.getByRole("dialog", { name: "Interests", exact: true });
  await modal.getByRole("checkbox", { name: "Select all Soccer", exact: true }).uncheck();
  await modal.getByRole("button", { name: "Show my calendar", exact: true }).click();
}

for (const timezoneId of ["Europe/London", "Asia/Tokyo"]) {
  test.describe(timezoneId, () => {
    test.use({ timezoneId, reducedMotion: "reduce" });
    const today = timezoneId === "Asia/Tokyo" ? "2026-10-01" : "2026-09-30";
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 620 }]) {
      test(`first open and Today center the local week after delayed data at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.clock.setFixedTime(new Date("2026-09-30T16:30:00Z"));
        let release!: () => void;
        await setup(page, new Promise<void>((resolve) => { release = resolve; }));
        await expect.poll(async () => Math.abs(await weekOffset(page, today))).toBeLessThanOrEqual(2);
        // Loading can outlast the native-navigation fallback deadline.
        await page.waitForTimeout(2200);
        release();
        await expect(page.locator(`#day-${today} .competition-chip`)).toHaveCount(1);
        await expect.poll(async () => Math.abs(await weekOffset(page, today))).toBeLessThanOrEqual(2);
        const chip = page.locator(`#day-${today} .competition-chip`);
        await chip.click();
        await expect(chip).toHaveAttribute("aria-expanded", "true");
        await page.getByRole("button", { name: "Today", exact: true }).click();
        await expect.poll(async () => Math.abs(await weekOffset(page, today))).toBeLessThanOrEqual(2);
        await page.setViewportSize({ width: viewport.width === 390 ? 1000 : 390, height: 844 });
        await expect.poll(async () => Math.abs(await weekOffset(page, today))).toBeLessThanOrEqual(2);
        await expect(page.locator(`#day-${today}`)).toHaveAttribute("aria-current", "date");
        await expect(page.getByRole("heading", { level: 1 })).toHaveText(today.startsWith("2026-10") ? "October" : "September");
      });
    }
    test("saving interests preserves Calendar date, viewport, expansion and year view; cancel and reload retain selections", async ({ page }) => {
      await page.clock.setFixedTime(new Date("2026-09-22T12:00:00Z"));
      await setup(page);
      const date = "2026-11-18";
      const cell = page.locator(`#day-${date}`);
      await expect(cell.locator(".competition-chip")).toHaveCount(1);
      await cell.locator(".competition-chip").click();
      await cell.locator(".day-number").click();
      await expect(page.getByRole("complementary", { name: "Day events" })).toBeVisible();
      await cell.evaluate((element) => {
        const root = element.closest(".month-feed")!;
        root.dispatchEvent(new WheelEvent("wheel", { bubbles: true }));
        root.scrollTo({ top: (element as HTMLElement).offsetTop + 35, behavior: "instant" });
      });
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("November");
      const offset = await cell.evaluate((element) => element.getBoundingClientRect().top);
      await removeSoccer(page);
      await expect(cell.locator(".month-single")).toHaveCount(0);
      await expect(cell.locator(".competition-chip")).toHaveAttribute("aria-expanded", "true");
      await expect.poll(() => cell.evaluate((element) => element.getBoundingClientRect().top)).toBeCloseTo(offset, 0);
      await expect(view(page, "Calendar")).toHaveAttribute("aria-pressed", "true");
      await expect(cell).toHaveClass(/selected/);
      await expect(page.getByRole("complementary", { name: "Day events" })).toBeVisible();
      await page.getByRole("button", { name: "Close day", exact: true }).click();
      await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
      await page.getByRole("button", { name: /^Interests/ }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Show my calendar" }).click();
      await expect(page.locator(".year-grid")).toBeVisible();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("2026");
      await page.getByRole("button", { name: /^Interests/ }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Clear", exact: true }).click();
      await page.keyboard.press("Escape");
      await expect(page.locator(".year-grid")).toBeVisible();
      await page.reload();
      await expect(page.getByRole("button", { name: "Interests · 1", exact: true })).toBeVisible();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect.poll(async () => Math.abs(await weekOffset(page, "2026-09-22"))).toBeLessThanOrEqual(2);
    });
    test("saving interests preserves Agenda period, expanded range, row position and selected day", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 720 });
      await page.clock.setFixedTime(new Date("2026-09-22T12:00:00Z"));
      await setup(page);
      await view(page, "Agenda").click();
      await page.getByRole("group", { name: "Agenda days" }).getByRole("button", { name: "Upcoming", exact: true }).click();
      await page.getByRole("button", { name: "Show more", exact: true }).click();
      await expect(page.locator(".agenda-range")).toHaveText("Sep 23 – Oct 6");
      const row = page.locator('[id="agenda-2026-10-02-F1-2026-10-02-3"]');
      await row.scrollIntoViewIfNeeded();
      await row.click();
      await expect(page.getByRole("complementary", { name: "Day events" })).toBeVisible();
      // Close details to expose the scroll surface on mobile, then keep a day
      // selected on desktop while testing changes to rows above the viewport.
      await page.getByRole("button", { name: "Close day", exact: true }).click();
      await page.setViewportSize({ width: 1280, height: 720 });
      await row.click();
      await row.evaluate((element) => {
        const root = element.closest(".agenda-scroll")!;
        root.scrollTop += element.getBoundingClientRect().top - root.getBoundingClientRect().top - 30;
      });
      const before = await row.evaluate((element) => element.getBoundingClientRect().top);
      await removeSoccer(page);
      await expect(page.locator(".agenda-row .league-epl")).toHaveCount(0);
      await expect(page.locator(".agenda-range")).toHaveText("Sep 23 – Oct 6");
      await expect(view(page, "Agenda")).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByRole("button", { name: "Upcoming", exact: true })).toHaveAttribute("aria-pressed", "true");
      await expect.poll(() => row.evaluate((element) => element.getBoundingClientRect().top)).toBeCloseTo(before, 0);
      await expect(page.getByRole("complementary", { name: "Day events" })).toContainText("October 2");
      await page.getByRole("button", { name: /^Interests/ }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Clear", exact: true }).click();
      await page.keyboard.press("Escape");
      await expect(page.locator(".agenda-range")).toHaveText("Sep 23 – Oct 6");
      await page.reload();
      await expect(view(page, "Agenda")).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByRole("button", { name: "Interests · 1", exact: true })).toBeVisible();
    });
  });
}

test("Today uses the new local date after midnight without moving a browsed month", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-09-30T23:59:30Z") });
  await setup(page);
  await page.locator('[data-month="2026-11-01"]').evaluate((element) => {
    const root = element.closest(".month-feed")!;
    root.dispatchEvent(new WheelEvent("wheel", { bubbles: true }));
    root.scrollTo({ top: (element as HTMLElement).offsetTop + 30, behavior: "instant" });
  });
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("November");
  // Chicago is still on September 30. Cross its midnight, then explicitly jump.
  await page.clock.fastForward(7 * 60 * 60 * 1000);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("November");
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.locator("#day-2026-10-01")).toHaveAttribute("aria-current", "date");
  await expect.poll(async () => Math.abs(await weekOffset(page, "2026-10-01"))).toBeLessThanOrEqual(2);
  await expect(feed(page)).toBeVisible();
});
