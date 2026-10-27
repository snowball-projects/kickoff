import { expect, test, type Page } from "@playwright/test";

async function setup(page: Page, start: string, end: string) {
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["EPL"] })));
  const after = new Date(`${end}T12:00:00Z`);
  after.setUTCDate(after.getUTCDate() + 1);
  const events = [
    ["First covered fixture", start], ["Last covered fixture", end],
    ["Outside coverage", after.toISOString().slice(0, 10)],
  ].map(([title, date]) => ({
    event_id: title, title, calendar_date: date, end_calendar_date: date,
    season: date.slice(0, 4), source: "fixture", status: "scheduled", sport: "soccer", league: "EPL",
    competition_phase: "regular_season", event_type: "match", tags: [], participants: [],
    start_time_utc: null, start_time_local: null,
  }));
  const requests: number[] = [];
  const years = Array.from({ length: Number(end.slice(0, 4)) - Number(start.slice(0, 4)) + 5 }, (_, i) => Number(start.slice(0, 4)) - 2 + i);
  await page.route("**/data/*.json", (route) => {
    const year = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    requests.push(year);
    if (!years.includes(year)) return route.fulfill({ status: 404, body: "missing" });
    return route.fulfill({ json: {
      schema_version: "1", season: year, available_seasons: years,
      providers: [], events: events.filter((event) => event.season === String(year)),
    } });
  });
  await page.goto("/");
  return requests;
}

for (const [zone, instant, today, start, end] of [
  ["UTC", "2026-10-27T12:00:00Z", "2026-10-27", "2025-10-27", "2027-10-27"],
  ["Pacific/Honolulu", "2027-01-01T02:00:00Z", "2026-12-31", "2025-12-31", "2027-12-31"],
  ["Pacific/Kiritimati", "2027-01-01T02:00:00Z", "2027-01-01", "2026-01-01", "2028-01-01"],
  ["UTC", "2028-02-29T12:00:00Z", "2028-02-29", "2027-02-28", "2029-02-28"],
]) {
  test.describe(zone + " " + today, () => {
    test.use({ timezoneId: zone, reducedMotion: "reduce" });
    test("calendar, year overview and agenda share inclusive rolling endpoints", async ({ page }) => {
      await page.clock.setFixedTime(new Date(instant));
      const requests = await setup(page, start, end);
      await page.getByRole("button", { name: `Show ${today.slice(0, 4)} year calendar` }).click();
      await page.locator(".calendar-stage").press("PageUp");
      const firstMonth = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
        .format(new Date(`${start}T12:00:00Z`));
      await page.getByRole("button", { name: `Open ${firstMonth}` }).click();
      const first = page.locator(`#day-${start}`);
      await expect(first.locator(".event-pill")).toContainText("First covered fixture");
      await first.focus();
      await first.press("ArrowLeft");
      await expect(first).toBeFocused();
      await first.press("Shift+PageUp");
      await expect(first).toBeFocused();
      const feed = page.getByRole("region", { name: "Scrollable calendar" });
      await feed.evaluate((element) => element.scrollTo({ top: 0, behavior: "instant" }));
      await expect(page.locator(".day-cell[id]").first()).toHaveAttribute("id", `day-${start}`);
      await expect(first).toBeFocused();
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await page.getByRole("button", { name: `Show ${today.slice(0, 4)} year calendar` }).click();
      await page.locator(".calendar-stage").press("PageDown");
      const lastMonth = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
        .format(new Date(`${end}T12:00:00Z`));
      await page.getByRole("button", { name: `Open ${lastMonth}` }).click();
      const last = page.locator(`#day-${end}`);
      await expect(last.locator(".event-pill")).toContainText("Last covered fixture");
      await last.focus();
      await last.press("ArrowRight");
      await expect(last).toBeFocused();
      await last.press("Shift+PageDown");
      await expect(last).toBeFocused();
      await feed.evaluate((element) => element.scrollTo({ top: element.scrollHeight, behavior: "instant" }));
      await expect(page.locator(".day-cell[id]").last()).toHaveAttribute("id", `day-${end}`);
      await page.getByRole("group", { name: "Schedule view" }).getByRole("button", { name: "Agenda", exact: true }).click();
      await page.getByRole("button", { name: "Upcoming", exact: true }).click();
      await page.getByRole("button", { name: "Show more", exact: true }).click();
      await expect(page.locator(".agenda-row", { hasText: "Last covered fixture" })).toHaveCount(1);
      await expect(page.locator(".agenda-row", { hasText: "Outside coverage" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
      expect(requests).not.toContain(Number(end.slice(0, 4)) + 2);
    });
  });
}

test.describe("moving local window", () => {
  test.use({ timezoneId: "UTC", reducedMotion: "reduce" });
  test("midnight retires the first date and exposes the next endpoint without reload", async ({ page }) => {
    await page.clock.install({ time: new Date("2026-10-27T23:59:30Z") });
    await setup(page, "2025-10-27", "2027-10-27");
    await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
    await page.locator(".calendar-stage").press("PageUp");
    await page.getByRole("button", { name: "Open October 2025" }).click();
    await page.locator("#day-2025-10-27").click();
    await expect(page.getByRole("complementary", { name: "Day events" })).toBeVisible();
    await page.clock.fastForward(60_000);
    await expect(page.locator("#day-2025-10-27")).toHaveCount(0);
    await expect(page.locator("#day-2025-10-28")).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Day events" })).toHaveCount(0);
    await page.getByRole("button", { name: "Today", exact: true }).click();
    await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
    await page.locator(".calendar-stage").press("PageDown");
    await page.getByRole("button", { name: "Open October 2027" }).click();
    await expect(page.locator("#day-2027-10-28 .event-pill")).toContainText("Outside coverage");
  });
});
