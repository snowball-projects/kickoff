import { expect, test, type Page } from "@playwright/test";

const event = (id: string, fields = {}) => ({
  event_id: id, source: "offline-browser-fixture", season: "2026", status: "scheduled",
  competition_phase: "regular_season", league: "F1", sport: "motorsport", event_type: "race", title: id,
  calendar_date: "2026-09-10", end_calendar_date: "2026-09-10", start_time_utc: null,
  start_time_local: null, timezone: null, subtitle: null, venue: null, city: null, region: null,
  country: "Italy", round_or_stage: null, tags: [], participants: [], home_participant: null,
  away_participant: null, home_participant_name: null, away_participant_name: null, week_label: null,
  is_regular_season: true, is_postseason: false, is_exhibition: false, is_support_event: false, ...fields,
});
const events = [
  event("Race later", { start_time_utc: "2026-09-10T20:00:00Z" }),
  event("Race first", { start_time_utc: "2026-09-10T17:00:00Z" }),
  event("Race date only"),
  event("Hidden practice", { event_type: "practice" }),
  event("Single race", { calendar_date: "2026-09-11", end_calendar_date: "2026-09-11" }),
  event("Single hidden practice", { event_type: "practice", calendar_date: "2026-09-11", end_calendar_date: "2026-09-11" }),
  event("Only hidden practice", { event_type: "practice", calendar_date: "2026-09-12", end_calendar_date: "2026-09-12" }),
  ...Array.from({ length: 13 }, (_, index) => event(`Game ${index + 1}`, {
    league: "NFL", sport: "football", event_type: "game", start_time_utc: "2026-09-13T17:00:00Z",
    calendar_date: "2026-09-13", end_calendar_date: "2026-09-13",
  })),
];

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-10T17:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({
    leagues: ["F1", "NFL"], motorsport_view: "race_only",
    golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" },
  })));
  await page.route("**/data/*.json", async (route) => {
    const season = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    await route.fulfill({ json: { schema_version: "1", season, providers: [], available_seasons: [2026], events: season === 2026 ? events : [] } });
  });
  await page.goto("/");
});

async function motorsport(page: Page, value: string) {
  await page.getByRole("button", { name: /Interests/ }).click();
  const dialog = page.getByRole("dialog", { name: "Interests", exact: true });
  await dialog.locator("details.advanced summary").click();
  await dialog.getByRole("combobox", { name: "Motorsport", exact: true }).selectOption(value);
  await dialog.getByRole("button", { name: "Show my calendar" }).click();
}

test("month chips expand in place, stay flat and show only a muted inactive hidden count", async ({ page }) => {
  const day = page.locator("#day-2026-09-10");
  const chip = day.getByRole("button", { name: "F1 · 3 events · from 12:00", exact: true });
  await expect(chip).toHaveAttribute("aria-expanded", "false");
  await expect(day.locator(".hidden-events")).toHaveCount(0);
  await chip.focus();
  await page.keyboard.press("Enter");
  await expect(chip).toHaveAttribute("aria-expanded", "true");
  await expect(day.locator(".competition-event")).toHaveCount(3);
  await expect(day.locator(".competition-event .event-pill")).toHaveText(["F1Race first", "F1Race later", "F1Race date only"]);
  await expect(day.locator(".competition-event-time")).toHaveText(["12:00 PM", "3:00 PM", "Time TBD"]);
  await expect(day.locator(".hidden-events")).toHaveText("1 more event hidden by your filters");
  await expect(day.locator(".competition-events [aria-expanded]")).toHaveCount(0);
  expect(await day.locator(".hidden-events").evaluate((element) => {
    const style = getComputedStyle(element);
    return { size: style.fontSize, color: style.color, tabIndex: (element as HTMLElement).tabIndex };
  })).toEqual({ size: "10px", color: "rgb(107, 120, 111)", tabIndex: -1 });
  await day.locator(".hidden-events").click();
  await expect(page.getByRole("complementary", { name: "Day events" })).toHaveCount(0);
  await expect(chip).toHaveAttribute("aria-expanded", "true");
  await chip.focus();
  await page.keyboard.press(" ");
  await expect(chip).toHaveAttribute("aria-expanded", "false");
  await expect(day.locator(".hidden-events")).toHaveCount(0);
  await chip.click();
  await expect(day.locator(".competition-event")).toHaveCount(3);
  await day.locator(".competition-event").first().click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail.locator("article")).toHaveCount(3);
  await expect(detail).not.toContainText("Hidden practice");
  await expect(detail.locator(".competition-chip")).toHaveCount(0);
});

test("filters control 0/1/2+ chips and reset expansion, while day and agenda stay ungrouped", async ({ page }) => {
  const today = page.locator("#day-2026-09-10");
  await today.locator(".competition-chip").click();
  await expect(page.locator("#day-2026-09-11 .month-single")).toContainText("Single race");
  await expect(page.locator("#day-2026-09-11 .competition-chip")).toHaveCount(0);
  await expect(page.locator("#day-2026-09-12 .event-pill")).toHaveCount(0);
  await motorsport(page, "full_weekend");
  await expect(today.locator(".competition-chip")).toHaveAttribute("aria-expanded", "false");
  await expect(today.locator(".competition-chip")).toContainText("4 events · from 12:00");
  await expect(page.locator("#day-2026-09-11 .competition-chip")).toContainText("2 events · Time TBD");
  await expect(page.locator("#day-2026-09-12 .month-single")).toContainText("Only hidden practice");
  await today.locator(".competition-chip").click();
  await expect(today.locator(".competition-event")).toHaveCount(4);
  await expect(today.locator(".hidden-events")).toHaveCount(0);
  await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Agenda", exact: true }).click();
  const agenda = page.getByRole("region", { name: "Agenda", exact: true });
  await expect(agenda.locator(".agenda-row")).toHaveCount(4);
  await expect(agenda.locator(".competition-chip")).toHaveCount(0);
  await motorsport(page, "race_only");
  await expect(agenda.locator(".agenda-row")).toHaveCount(3);
  await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Calendar", exact: true }).click();
  await expect(today.locator(".competition-chip")).toContainText("3 events");
  await page.getByRole("button", { name: /Interests/ }).click();
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await expect(page.locator(".month-feed .event-pill")).toHaveCount(0);
});

test("NFL label counts games; keyboard navigation still works after expanding", async ({ page }) => {
  const day = page.locator("#day-2026-09-13");
  await expect(day.locator(".competition-chip")).toHaveText("NFL · 13 games · from 12:00+");
  await day.locator(".competition-chip").click();
  await expect(day.locator(".competition-event")).toHaveCount(13);
  await day.focus();
  await page.keyboard.press("PageDown");
  await expect(page.locator("#day-2026-10-13")).toBeFocused();
  await page.keyboard.press("PageUp");
  await expect(day).toBeFocused();
  await day.locator(".competition-chip").click();
  await expect(day.locator(".competition-event")).toHaveCount(0);
});

test.describe("mobile", () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });
  test("tap expands all rows without clipping or horizontal overflow", async ({ page }) => {
    const day = page.locator("#day-2026-09-13");
    const before = (await day.boundingBox())!.height;
    await day.locator(".competition-chip").tap();
    await expect(day.locator(".competition-event")).toHaveCount(13);
    expect((await day.boundingBox())!.height).toBeGreaterThan(before);
    expect(await day.evaluate((element) => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await day.locator(".competition-event").last().tap();
    await expect(page.getByRole("complementary", { name: "Day events" }).locator("article")).toHaveCount(13);
  });
});

for (const fixture of [{ zone: "Europe/London", clock: "18:00" }, { zone: "Asia/Tokyo", clock: "02:00" }]) {
  test.describe(fixture.zone, () => {
    test.use({ timezoneId: fixture.zone });
    test("chip clocks and counts use viewer-local days", async ({ page }) => {
      if (fixture.zone === "Europe/London") {
        await expect(page.locator("#day-2026-09-10 .competition-chip")).toContainText(`3 events · from ${fixture.clock}`);
      } else {
        await expect(page.locator("#day-2026-09-10 .month-single")).toContainText("Race date only");
        await expect(page.locator("#day-2026-09-11 .competition-chip")).toContainText(`3 events · from ${fixture.clock}`);
      }
    });
  });
}
