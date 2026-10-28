import { expect, test, type Page } from "@playwright/test";

const event = (id: string, fields = {}) => ({
  event_id: id, source: "offline-browser-fixture", season: "2026", status: "scheduled",
  competition_phase: "regular_season", league: "NFL", sport: "football", event_type: "game", title: id,
  calendar_date: "2026-09-10", end_calendar_date: "2026-09-10", start_time_utc: "2026-09-10T17:30:00Z",
  start_time_local: null, timezone: null, subtitle: "Reviewed event notes", venue: "Fixture stadium", city: null, region: null,
  country: null, round_or_stage: null, tags: [], participants: [], home_participant: null,
  away_participant: null, home_participant_name: null, away_participant_name: null, week_label: null,
  source_url: "https://example.com/schedule", is_regular_season: true, is_postseason: false, is_exhibition: false, is_support_event: false, ...fields,
});
const events = [
  ...Array.from({ length: 6 }, (_, index) => event(`Same start ${index + 1}`)),
  event("Later game", { start_time_utc: "2026-09-10T19:00:00Z", status: "postponed" }),
  event("Basketball", { league: "NBA", sport: "basketball", start_time_utc: "2026-09-10T18:15:00Z" }),
  event("Untimed", { start_time_utc: null, league: "EPL", sport: "soccer", event_type: "match" }),
  event("Multi-day", { league: "PGA_TOUR", sport: "golf", event_type: "tournament", end_calendar_date: "2026-09-12" }),
  event("Final date", { league: "LPGA_TOUR", sport: "golf", event_type: "tournament", tags: ["final date only"] }),
  event("Next day", { calendar_date: "2026-09-11", end_calendar_date: "2026-09-11", start_time_utc: "2026-09-11T14:15:00Z" }),
  event("Late game", { calendar_date: "2026-09-12", end_calendar_date: "2026-09-12", start_time_utc: "2026-09-12T23:59:00Z" }),
];
const panel = (page: Page) => page.getByRole("complementary", { name: "Day events" });
const pill = (page: Page, id: string) => panel(page).locator(`[data-event-id="${id}"]`);
async function setup(page: Page) {
  await page.clock.setFixedTime(new Date("2026-09-10T20:10:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["NFL", "NBA", "EPL", "PGA_TOUR", "LPGA_TOUR"] })));
  await page.route("**/data/*.json", async (route) => {
    const season = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    await route.fulfill({ json: { schema_version: "1", season, providers: [], available_seasons: [2026], events: season === 2026 ? events : [] } });
  });
  await page.goto("/");
  await page.locator("#day-2026-09-10 .day-number").click();
}
async function gridGeometry(page: Page) {
  return panel(page).locator(".timeline-hour").evaluateAll((rows) => rows.map((row) => (row as HTMLElement).offsetTop));
}
for (const width of [1280, 320]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, hasTouch: width === 320 });
    test("fixed hours, exact clocks, flat groups, overflow, previews and details", async ({ page }) => {
      await setup(page);
      const hours = panel(page).locator(".timeline-hour");
      await expect(hours).toHaveCount(25);
      await expect(hours.first()).toHaveText("12am");
      await expect(hours.last()).toHaveText("12am");
      const before = await gridGeometry(page);
      expect(before).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
      const scroll = panel(page).getByRole("region", { name: "Day timeline" });
      expect(await scroll.evaluate((element) => element.scrollTop)).toBeCloseTo((14 * 60 + 10) * 80 / 60 - 40, 0);
      const allDay = panel(page).getByRole("region", { name: "All-day events" });
      for (const id of ["Untimed", "Multi-day", "Final date"]) await expect(allDay).toContainText(id);
      await expect(allDay.locator("[data-event-id]")).toHaveCount(3);
      const group = panel(page).locator('.timeline-group[data-competition="NFL"]');
      expect(await group.evaluate((element) => (element as HTMLElement).offsetTop)).toBe(750 * 80 / 60);
      await group.getByRole("button", { name: /NFL/ }).click();
      await expect(group).toHaveClass(/is-expanded/);
      await expect(group.locator(".timeline-slot").first().getByRole("button")).toHaveCount(3);
      await expect(group.getByRole("button", { name: /\+4 more/ })).toBeVisible();
      const bg = await group.evaluate((element) => getComputedStyle(element).backgroundColor);
      expect(bg).toMatch(/0\.2|20%/);
      expect(await gridGeometry(page)).toEqual(before);
      const slot = group.locator(".timeline-slot").last();
      expect(await slot.evaluate((element) => (element as HTMLElement).offsetTop)).toBe(120);
      await expect(pill(page, "Later game")).toContainText("postponed");
      await expect(group).not.toContainText("scheduled");
      await group.getByRole("button", { name: /\+4 more/ }).click();
      const more = panel(page).getByRole("region", { name: "More events" });
      await expect(more.getByRole("listitem")).toHaveCount(4);
      await more.locator('[data-event-id="Same start 6"]').click();
      const detail = panel(page).getByRole("region", { name: "Event details" });
      await expect(detail).toContainText("Reviewed event notes");
      await expect(detail.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", "https://example.com/schedule");
      await expect(detail.locator(".event-status")).toHaveCount(0);
      await detail.getByRole("button", { name: "Close details" }).click();
      await group.getByRole("button", { name: "Collapse NFL", exact: true }).focus();
      await page.keyboard.press("Enter");
      await expect(group.locator(".timeline-group-toggle")).toHaveAttribute("aria-expanded", "false");
      await page.keyboard.press(" ");
      await expect(group).toHaveClass(/is-expanded/);
      expect(await gridGeometry(page)).toEqual(before);
      // Keyboard focus has the same preview and source access as pointer hover.
      await pill(page, "Same start 1").focus();
      await expect(page.getByRole("tooltip")).toContainText("Same start 1");
      await pill(page, "Same start 1").press("Enter");
      await expect(detail).toContainText("Same start 1");
      await expect(page.getByRole("tooltip")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/day-timeline-${width}-${colorScheme}.png` });
      await panel(page).getByRole("button", { name: "Close day" }).click();
      await page.locator("#day-2026-09-11 .day-number").click();
      expect(await scroll.evaluate((element) => element.scrollTop)).toBeCloseTo(555 * 80 / 60 - 40, 0);
      await panel(page).getByRole("button", { name: "Close day" }).click();
      await page.locator("#day-2026-09-10 .day-number").click();
      await expect(panel(page).locator(".timeline-group-toggle", { hasText: "NFL" })).toHaveAttribute("aria-expanded", "false");
      expect(await gridGeometry(page)).toEqual(before);
      await panel(page).getByRole("button", { name: "Close day" }).click();
      await page.locator("#day-2026-09-12 .day-number").click();
      await expect(pill(page, "Late game")).toBeInViewport();
      await expect(pill(page, "Late game")).toHaveCSS("height", "44px");
    });
  });
}
for (const scenario of [
  { zone: "Asia/Tokyo", date: "2026-09-11", instant: "2026-09-10T17:30:00Z", minute: 150 },
  { zone: "America/Chicago", date: "2026-03-08", instant: "2026-03-08T08:30:00Z", minute: 210 },
  { zone: "America/Chicago", date: "2026-11-01", instant: "2026-11-01T07:30:00Z", minute: 90 },
]) test.describe(scenario.zone + scenario.date, () => {
  test.use({ timezoneId: scenario.zone });
  test("viewer-local dates and DST clocks retain a 24-hour grid", async ({ page }) => {
    await page.clock.setFixedTime(new Date(scenario.instant));
    await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["NFL"] })));
    await page.route("**/data/*.json", async (route) => {
      const season = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
      await route.fulfill({ json: { schema_version: "1", season, providers: [], available_seasons: [2026], events: season === 2026 ? [event("Zoned", { calendar_date: scenario.instant.slice(0, 10), end_calendar_date: scenario.instant.slice(0, 10), start_time_utc: scenario.instant })] : [] } });
    });
    await page.goto("/");
    await page.locator(`#day-${scenario.date} .day-number`).click();
    expect(await panel(page).locator(".timeline-group").evaluate((element) => (element as HTMLElement).offsetTop)).toBe(scenario.minute * 80 / 60);
    expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
  });
});
