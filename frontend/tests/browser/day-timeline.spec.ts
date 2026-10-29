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
  event("Another untimed", { start_time_utc: null, league: "EPL", sport: "soccer", event_type: "match" }),
  event("Multi-day", { league: "PGA_TOUR", sport: "golf", event_type: "tournament", end_calendar_date: "2026-09-12" }),
  event("Final date", { league: "LPGA_TOUR", sport: "golf", event_type: "tournament", tags: ["final date only"] }),
  event("Next day", { calendar_date: "2026-09-11", end_calendar_date: "2026-09-11", start_time_utc: "2026-09-11T14:15:00Z" }),
  event("Late game", { calendar_date: "2026-09-12", end_calendar_date: "2026-09-12", start_time_utc: "2026-09-13T04:59:00Z" }),
];
const panel = (page: Page) => page.getByRole("complementary", { name: "Day events" });
const pill = (page: Page, id: string) => panel(page).locator(`[data-event-id="${id}"]`);
async function setup(page: Page, extraEvents: ReturnType<typeof event>[] = [], baseEvents = events) {
  await page.clock.setFixedTime(new Date("2026-09-10T20:10:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["NFL", "NBA", "EPL", "PGA_TOUR", "LPGA_TOUR"] })));
  await page.route("**/data/*.json", async (route) => {
    const season = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    await route.fulfill({ json: { schema_version: "1", season, providers: [], available_seasons: [season], events: season === 2026 ? [...baseEvents, ...extraEvents] : [] } });
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
      const browserErrors: string[] = [];
      page.on("pageerror", (error) => browserErrors.push(error.message));
      await setup(page);
      const hours = panel(page).locator(".timeline-hour");
      await expect(hours).toHaveCount(25);
      await expect(hours.first()).toHaveText("12am");
      await expect(hours.last()).toHaveText("12am");
      const before = await gridGeometry(page);
      expect(before).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
      const scroll = panel(page).getByRole("region", { name: "Day timeline" });
      expect(await scroll.evaluate((element) => element.scrollTop)).toBeCloseTo((15 * 60 + 10) * 80 / 60 - 40, 0);
      const allDay = panel(page).getByRole("region", { name: "All-day events" });
      for (const id of ["Untimed", "Multi-day", "Final date"]) await expect(allDay).toContainText(id);
      await expect(allDay.locator("[data-event-id]")).toHaveCount(4);
      const gridTop = await panel(page).locator(".timeline-grid").evaluate((element) => element.getBoundingClientRect().top);
      await allDay.locator(".timeline-group-toggle").click();
      expect(await panel(page).locator(".timeline-grid").evaluate((element) => element.getBoundingClientRect().top)).toBe(gridTop);
      await expect(allDay.getByRole("button", { name: /Another untimed/ })).toBeVisible();
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
      await expect(pill(page, "Late game")).toBeInViewport({ ratio: 1 });
      await expect(pill(page, "Late game")).toHaveCSS("height", "44px");
      expect(browserErrors).toEqual([]);
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
      await route.fulfill({ json: { schema_version: "1", season, providers: [], available_seasons: [season], events: season === 2026 ? [event("Zoned", { calendar_date: scenario.instant.slice(0, 10), end_calendar_date: scenario.instant.slice(0, 10), start_time_utc: scenario.instant })] : [] } });
    });
    await page.goto("/");
    await page.locator(`#day-${scenario.date} .day-number`).click();
    expect(await panel(page).locator(".timeline-group").evaluate((element) => (element as HTMLElement).offsetTop)).toBe(scenario.minute * 80 / 60);
    expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
  });
});

test("interest changes remove hidden events from an open overflow list", async ({ page }) => {
  await setup(page);
  const nfl = panel(page).locator('.timeline-group[data-competition="NFL"]');
  await nfl.locator(".timeline-group-toggle").click();
  await nfl.getByRole("button", { name: /\+4 more/ }).click();
  await expect(panel(page).getByRole("region", { name: "More events" }).getByRole("listitem")).toHaveCount(4);
  await page.getByRole("button", { name: /Interests/ }).click();
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await chooser.getByRole("region", { name: "American football interests" }).locator("summary").click();
  await chooser.getByRole("checkbox", { name: "NFL", exact: true }).uncheck();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await expect(nfl).toHaveCount(0);
  await expect(panel(page).getByRole("region", { name: "More events" })).toHaveCount(0);
  await expect(panel(page)).not.toContainText("Same start");
});

test("a changed browser-reported timezone rebuilds an open day without retaining old groups", async ({ page }) => {
  await setup(page);
  await panel(page).locator('.timeline-group[data-competition="NFL"] .timeline-group-toggle').click();
  // Simulate the device-reported default. Explicit IANA conversions stay native.
  await page.evaluate(() => {
    Intl.DateTimeFormat = new Proxy(Intl.DateTimeFormat, {
      apply(target, receiver, [locales, options]) {
        return Reflect.apply(target, receiver, [locales, { timeZone: "Asia/Tokyo", ...options }]);
      },
      construct(target, [locales, options]) {
        return Reflect.construct(target, [locales, { timeZone: "Asia/Tokyo", ...options }]);
      },
    });
  });
  await page.clock.runFor(60_000);
  await expect(page.locator(".footer-meta")).toContainText("Tokyo");
  await expect(panel(page).locator(".timeline-group")).toHaveCount(0);
  await expect(panel(page).getByRole("region", { name: "All-day events" })).toContainText("Untimed");
  expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
  await panel(page).getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-09-11 .day-number").click();
  const nfl = panel(page).locator('.timeline-group[data-competition="NFL"]');
  await expect(nfl.locator(".timeline-group-toggle")).toHaveAttribute("aria-expanded", "false");
  expect(await nfl.evaluate((element) => (element as HTMLElement).offsetTop)).toBe(200);
});


test("simultaneous expanded competitions keep separate collapse controls on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await setup(page, [event("Basketball same start", { league: "NBA", sport: "basketball" })],
    events.filter((item) => !/^Same start [2-6]$/.test(item.event_id)));
  const nfl = panel(page).locator('.timeline-group[data-competition="NFL"]');
  const nba = panel(page).locator('.timeline-group[data-competition="NBA"]');
  await nfl.locator(".timeline-group-toggle").click();
  await nba.locator(".timeline-group-toggle").click();
  const nflCollapse = nfl.getByRole("button", { name: "Collapse NFL", exact: true });
  const nbaCollapse = nba.getByRole("button", { name: "Collapse NBA", exact: true });
  const a = (await nflCollapse.boundingBox())!, b = (await nbaCollapse.boundingBox())!;
  expect(a.x >= b.x + b.width || b.x >= a.x + a.width).toBe(true);
  await nflCollapse.click();
  await expect(nfl.locator(".timeline-group-toggle")).toHaveAttribute("aria-expanded", "false");
  await expect(nbaCollapse).toHaveAttribute("aria-expanded", "true");
  await nbaCollapse.click();
  await expect(nba.locator(".timeline-group-toggle")).toHaveAttribute("aria-expanded", "false");
  expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
});


test("four unrelated same-start competitions stay readable as one flat overflow list on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  const fixtures = [["NFL", "football"], ["NBA", "basketball"], ["EPL", "soccer"], ["PGA_TOUR", "golf"]]
    .map(([league, sport]) => event(`${league} simultaneous`, { league, sport }));
  await setup(page, [], fixtures);
  const more = panel(page).locator(".timeline-global-more .timeline-more");
  await expect(more).toHaveCount(1);
  await expect(more).toContainText("+4 more");
  expect((await more.boundingBox())!.width).toBeGreaterThan(150);
  await more.click();
  const list = panel(page).getByRole("region", { name: "More events" });
  await expect(list.getByRole("listitem")).toHaveCount(4);
  await list.locator('[data-event-id="NFL simultaneous"]').click();
  await expect(panel(page).getByRole("region", { name: "Event details" }).getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", "https://example.com/schedule");
  await panel(page).getByRole("button", { name: "Close details" }).click();
  await panel(page).getByRole("button", { name: "Close details" }).click();
  await expect(more).toBeFocused();
  expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
});

test("fall-back groups align their collapsed clock with the first chronological event", async ({ page }) => {
  const fixtures = [event("First chronological", { calendar_date: "2026-11-01", end_calendar_date: "2026-11-01", start_time_utc: "2026-11-01T06:45:00Z" }),
    event("Later chronological", { calendar_date: "2026-11-01", end_calendar_date: "2026-11-01", start_time_utc: "2026-11-01T07:15:00Z" })];
  await setup(page, [], fixtures);
  await panel(page).getByRole("button", { name: "Close day" }).click();
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: "Open November 2026" }).click();
  await page.locator("#day-2026-11-01 .day-number").click();
  const group = panel(page).locator('.timeline-group[data-competition="NFL"]');
  await expect(group.locator(".timeline-group-toggle")).toContainText("1:45 AM");
  expect(await group.evaluate((element) => (element as HTMLElement).offsetTop)).toBe(140);
  await group.locator(".timeline-group-toggle").click();
  expect(await group.evaluate((element) => (element as HTMLElement).offsetTop)).toBe(100);
  expect(await group.locator(".timeline-collapse").evaluate((element) => (element as HTMLElement).offsetTop)).toBe(40);
  const top = await panel(page).locator(".timeline-grid").evaluate((element) => element.getBoundingClientRect().top);
  expect((await pill(page, "First chronological").boundingBox())!.y - top).toBe(140);
  expect((await pill(page, "Later chronological").boundingBox())!.y - top).toBe(100);
  expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
});

test("closing overflow or event details after collapsing restores a visible group toggle", async ({ page }) => {
  await setup(page);
  const group = panel(page).locator('.timeline-group[data-competition="NFL"]');
  await group.locator(".timeline-group-toggle").press("Enter");
  await group.getByRole("button", { name: /\+4 more/ }).click();
  await group.getByRole("button", { name: "Collapse NFL", exact: true }).click();
  await panel(page).getByRole("button", { name: "Close details" }).click();
  await expect(group.locator(".timeline-group-toggle")).toBeFocused();
  await group.locator(".timeline-group-toggle").press(" ");
  await pill(page, "Same start 1").click();
  await group.getByRole("button", { name: "Collapse NFL", exact: true }).click();
  await panel(page).getByRole("button", { name: "Close details" }).click();
  await expect(group.locator(".timeline-group-toggle")).toBeFocused();
  await expect(group.locator(".timeline-group-toggle")).toBeVisible();
});


test("cross-competition overflow retains expansion, collapse and a visible focus target", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await setup(page, [event("Basketball same start", { league: "NBA", sport: "basketball" })]);
  await panel(page).locator('.timeline-group[data-competition="NFL"] .timeline-group-toggle').click();
  await panel(page).locator(".timeline-global-more .timeline-more").click();
  const controls = panel(page).getByRole("group", { name: "Competitions", exact: true });
  await expect(panel(page).getByRole("region", { name: "More events" }).getByRole("listitem")).toHaveCount(8);
  await controls.getByRole("button", { name: "Expand NBA", exact: true }).click();
  await expect(panel(page).getByRole("region", { name: "More events" }).getByRole("listitem")).toHaveCount(7);
  const nfl = controls.getByRole("button", { name: "Collapse NFL", exact: true });
  const nba = controls.getByRole("button", { name: "Collapse NBA", exact: true });
  await expect(nfl).toBeVisible();
  await expect(nba).toBeVisible();
  await expect(nba).toHaveAttribute("aria-expanded", "true");
  await nfl.click();
  await panel(page).getByRole("button", { name: "Close details" }).click();
  await expect(panel(page).locator(".timeline-group-toggle:focus")).toBeVisible();
  expect(await gridGeometry(page)).toEqual(Array.from({ length: 25 }, (_, hour) => hour * 80));
});

test("keyboard focus follows a group replaced by shared-clock overflow and back", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await setup(page, [event("Basketball same start", { league: "NBA", sport: "basketball" })]);
  const group = panel(page).locator('.timeline-group[data-competition="NFL"]');
  const toggle = group.locator(".timeline-group-toggle");
  const hours = await gridGeometry(page);
  await toggle.focus();
  await toggle.press("Enter");
  const more = panel(page).locator(".timeline-global-more .timeline-more");
  await expect(more).toBeFocused();
  await page.keyboard.press("Enter");
  const controls = panel(page).getByRole("group", { name: "Competitions", exact: true });
  await controls.getByRole("button", { name: "Collapse NFL", exact: true }).press("Enter");
  await expect(controls.getByRole("button", { name: "Expand NFL", exact: true })).toBeFocused();
  await expect(more).toHaveCount(0);
  await expect(toggle).toBeVisible();
  await panel(page).getByRole("button", { name: "Close details" }).press("Enter");
  await expect(panel(page).locator(".timeline-group-toggle:focus")).toBeVisible();
  expect(await gridGeometry(page)).toEqual(hours);
});
