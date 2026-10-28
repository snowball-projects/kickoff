import { expect, test, type Page } from "@playwright/test";

const event = (id: string, date: string, extra = {}) => ({
  event_id: id, title: id, source: "offline-fixture", sport: "soccer", league: "EPL",
  season: date.slice(0, 4), event_type: "match", subtitle: null,
  calendar_date: date, end_calendar_date: date, start_time_utc: null, start_time_local: null,
  timezone: null, status: "scheduled", venue: "Town Stadium", city: "London", region: null,
  country: "England", round_or_stage: null, competition_phase: "regular_season", tags: [],
  participants: [], home_participant: null, away_participant: null,
  home_participant_name: null, away_participant_name: null, week_label: null,
  is_regular_season: true, is_postseason: false, is_exhibition: false, is_support_event: false,
  source_url: "https://example.com/schedule", ...extra,
});
const events = [
  event("Yesterday fixture", "2026-12-30"),
  event("Date-only fixture", "2026-12-31"),
  event("Evening fixture", "2026-12-31", { start_time_utc: "2027-01-01T00:00:00Z" }),
  event("Morning fixture", "2026-12-31", { start_time_utc: "2026-12-31T18:00:00Z" }),
  event("Unverified clock", "2026-12-31", { start_time_local: "2026-12-31T09:00:00" }),
  event("Tournament span", "2026-12-30", { end_calendar_date: "2027-01-02" }),
  event("Supplied postponed status", "2027-01-01", { status: "postponed" }),
  event("Final date marker", "2027-01-02", { tags: ["final date only"] }),
  event("Last day fixture", "2027-01-07"), event("Outside next week", "2027-01-08"),
  event("Other interest", "2026-12-31", { league: "NBA", sport: "basketball" }),
  event("Grand Prix", "2026-12-31", { league: "F1", sport: "motorsport", event_type: "race" }),
  event("Practice session", "2026-12-31", { league: "F1", sport: "motorsport", event_type: "practice" }),
  event("Masters Tournament", "2026-12-31", { league: "PGA_TOUR", sport: "golf" }),
  event("Regular tour stop", "2026-12-31", { league: "PGA_TOUR", sport: "golf" }),
];

async function setup(page: Page, options: {
  saveInterests?: boolean; missingYear?: number; publishedYears?: number[]; extraEvents?: ReturnType<typeof event>[];
} = {}) {
  if (options.saveInterests !== false) await page.addInitScript(() => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify({
      leagues: ["EPL"], golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" }, motorsport_view: "race_only",
    }));
  });
  await page.route("**/data/*.json", async (route) => {
    const year = Number(new URL(route.request().url()).pathname.match(/(\d{4})\.json$/)?.[1]);
    const publishedYears = options.publishedYears || [2026, 2027];
    if (!publishedYears.includes(year) || year === options.missingYear) return route.fulfill({ status: 404, body: "missing" });
    await route.fulfill({ json: {
      schema_version: "1", season: year, available_seasons: publishedYears, providers: [],
      updated_at: "2026-12-30T00:00:00Z", events: [...events, ...(options.extraEvents || [])].filter((item) => item.calendar_date.startsWith(String(year))),
    } });
  });
  await page.goto("/");
}
const viewSwitch = (page: Page, name: string) => page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name, exact: true });
const periodSwitch = (page: Page, name: string) => page.getByRole("group", { name: "Agenda days", exact: true }).getByRole("button", { name, exact: true });
const agenda = (page: Page) => page.getByRole("region", { name: "Agenda", exact: true });
const row = (page: Page, title: string) => agenda(page).getByRole("button").filter({ has: page.locator(".agenda-title", { hasText: new RegExp(`^${title}$`) }) });

test("local day buckets, date-only times, spans and next-week limits share calendar data", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z")); // Dec 31 in Chicago.
  await setup(page);
  await expect(viewSwitch(page, "Calendar")).toHaveAttribute("aria-pressed", "true");
  await viewSwitch(page, "Agenda").click();
  await expect(agenda(page)).toContainText("Thursday, December 31, 2026");
  await expect(row(page, "Evening fixture")).toContainText("6:00 PM");
  await expect(row(page, "Morning fixture")).toContainText("12:00 PM");
  await expect(row(page, "Date-only fixture")).toContainText("Time TBD");
  await expect(row(page, "Unverified clock")).toContainText("Time TBD");
  await expect(row(page, "Tournament span")).toContainText("Through Jan 2");
  await expect(row(page, "Other interest")).toHaveCount(0);
  await expect(agenda(page).locator(".agenda-title")).toHaveText([
    "Morning fixture", "Evening fixture", "Date-only fixture", "Tournament span", "Unverified clock",
  ]);
  await expect(agenda(page).getByText(/live|final score|scheduled/i)).toHaveCount(0);
  await periodSwitch(page, "Yesterday").click();
  await expect(row(page, "Yesterday fixture")).toBeVisible();
  await expect(row(page, "Evening fixture")).toHaveCount(0);
  await periodSwitch(page, "Upcoming").click();
  await expect(agenda(page)).toContainText("Jan 1 – Jan 7 · Next 7 days");
  await expect(row(page, "Supplied postponed status")).toContainText("postponed");
  await expect(row(page, "Final date marker")).toContainText("Final date only");
  await expect(row(page, "Last day fixture")).toHaveCount(1);
  await expect(row(page, "Outside next week")).toHaveCount(0);
  await expect(row(page, "Tournament span")).toHaveCount(2);
  await page.getByRole("button", { name: "Today", exact: true }).last().click();
  await expect(periodSwitch(page, "Today")).toHaveAttribute("aria-pressed", "true");
});

for (const width of [1280, 390]) {
  test(`switching, focus, details, sources and modal dismissals at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
    await setup(page);
    const feed = page.getByRole("region", { name: "Scrollable calendar" });
    await page.locator('[data-month="2026-12-01"]').evaluate((element) => {
      const root = element.closest(".month-feed")!;
      root.dispatchEvent(new WheelEvent("wheel", { bubbles: true }));
      root.scrollTo({ top: (element as HTMLElement).offsetTop + 80, behavior: "instant" });
    });
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("December");
    await expect.poll(() => feed.evaluate((element) => element.scrollTop)).toBeGreaterThan(80);
    const before = await feed.evaluate((element) => element.scrollTop);
    for (let i = 0; i < 3; i++) {
      await viewSwitch(page, "Agenda").click();
      await expect(row(page, "Morning fixture")).toBeVisible();
      await viewSwitch(page, "Calendar").click();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("December");
      await expect.poll(() => feed.evaluate((element) => element.scrollTop)).toBeCloseTo(before, 0);
    }
    await viewSwitch(page, "Agenda").click();
    await page.keyboard.press("Tab");
    await row(page, "Morning fixture").focus();
    await expect(page.getByRole("tooltip")).toContainText("Morning fixture");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("tooltip")).toHaveCount(0);
    await row(page, "Morning fixture").press("Enter");
    const inspector = page.getByRole("complementary", { name: "Day events" });
    await expect(inspector).toBeVisible();
    await expect(inspector.getByRole("heading", { name: "Morning fixture", exact: true })).toBeVisible();
    await expect(inspector.locator("#details-Morning\\ fixture").getByRole("link", { name: "Schedule source ↗" })).toHaveAttribute("href", "https://example.com/schedule");
    await page.keyboard.press("Escape");
    await expect(inspector).toHaveCount(0);
    await expect(row(page, "Morning fixture")).toBeFocused();
    await row(page, "Date-only fixture").click();
    await page.getByRole("button", { name: "Close day", exact: true }).click();
    await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
    const about = page.getByRole("dialog", { name: "About kickoff", exact: true });
    await expect(about).toContainText("Published schedules, not live scores.");
    await page.keyboard.press("Escape");
    await expect(about).toHaveCount(0);
    await expect(page.getByRole("button", { name: "About kickoff and schedule coverage" })).toBeFocused();
    await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
    await about.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
    await page.mouse.click(4, 4);
    await expect(about).toHaveCount(0);
    await row(page, "Morning fixture").hover();
    await expect(page.getByRole("tooltip")).toBeVisible();
    await viewSwitch(page, "Calendar").click();
    await expect(page.getByRole("tooltip")).toHaveCount(0);
    await viewSwitch(page, "Agenda").click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.reload();
    await expect(viewSwitch(page, "Agenda")).toHaveAttribute("aria-pressed", "true");
    await expect(row(page, "Morning fixture")).toBeVisible();
  });
}

test("interest and advanced options are shared and cancellation is harmless", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  await setup(page);
  await viewSwitch(page, "Agenda").click();
  await page.getByRole("button", { name: "Interests · 1", exact: true }).click();
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true }).check();
  await chooser.getByRole("checkbox", { name: "Select all Golf", exact: true }).check();
  await chooser.locator("details.advanced summary").click();
  await chooser.locator("details.advanced").getByLabel("PGA Tour", { exact: true }).selectOption("majors_only");
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await expect(row(page, "Morning fixture")).toHaveCount(0);
  await expect(row(page, "Grand Prix")).toBeVisible();
  await expect(row(page, "Practice session")).toHaveCount(0);
  await expect(row(page, "Masters Tournament")).toBeVisible();
  await expect(row(page, "Regular tour stop")).toHaveCount(0);
  await viewSwitch(page, "Calendar").click();
  const pills = page.locator("#day-2026-12-31 .event-pill");
  await expect(pills).toHaveCount(2);
  await expect(pills).toContainText(["Grand Prix", "Masters Tournament"]);
  await viewSwitch(page, "Agenda").click();
  await page.getByRole("button", { name: "Interests · 2", exact: true }).click();
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(row(page, "Grand Prix")).toBeVisible();
  await page.getByRole("button", { name: "Interests · 2", exact: true }).click();
  await chooser.locator("details.advanced summary").click();
  await chooser.getByLabel("Motorsport", { exact: true }).selectOption("full_weekend");
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await expect(row(page, "Practice session")).toBeVisible();
  await page.getByRole("button", { name: "Interests · 2", exact: true }).click();
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  for (const period of ["Yesterday", "Today", "Upcoming"]) {
    await periodSwitch(page, period).click();
    await expect(agenda(page).getByText(/No published events match your interests/)).toBeVisible();
    await expect(agenda(page).locator(".agenda-row")).toHaveCount(0);
  }
});

test.describe("Tokyo day boundary", () => {
  test.use({ timezoneId: "Asia/Tokyo" });
  test("today and yesterday move timed events but keep date-only dates", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
    await setup(page);
    await viewSwitch(page, "Agenda").click();
    await expect(agenda(page)).toContainText("Friday, January 1, 2027");
    await expect(row(page, "Evening fixture")).toContainText("9:00 AM");
    await expect(row(page, "Date-only fixture")).toHaveCount(0);
    await periodSwitch(page, "Yesterday").click();
    await expect(row(page, "Date-only fixture")).toContainText("Time TBD");
    await expect(row(page, "Evening fixture")).toHaveCount(0);
  });
});

test("midnight updates today while an agenda remains open", async ({ page }) => {
  await page.clock.install({ time: new Date("2027-01-01T05:59:30Z") });
  await setup(page);
  await viewSwitch(page, "Agenda").click();
  await expect(agenda(page)).toContainText("December 31, 2026");
  await page.clock.fastForward(60_000);
  await expect(agenda(page)).toContainText("January 1, 2027");
  await expect(row(page, "Supplied postponed status")).toBeVisible();
  await expect(row(page, "Date-only fixture")).toHaveCount(0);
});

test("missing upcoming year shows coverage error alongside available boundary events", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  await setup(page, { missingYear: 2027 });
  await viewSwitch(page, "Agenda").click();
  await periodSwitch(page, "Upcoming").click();
  await expect(agenda(page)).toContainText("No published schedule for 2027.");
  await expect(row(page, "Tournament span")).toHaveCount(2);
  await expect(agenda(page).getByText(/No published events match/)).toHaveCount(0);
  await expect(agenda(page).getByRole("button", { name: "Retry", exact: true })).toBeVisible();
});

test("storage unavailable still permits switching without a view onboarding screen", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  await page.addInitScript(() => Object.defineProperty(window, "localStorage", { get() { throw new Error("disabled"); } }));
  await setup(page, { saveInterests: false });
  await page.getByRole("dialog", { name: "Interests", exact: true }).getByRole("button", { name: "Close", exact: true }).click();
  await viewSwitch(page, "Agenda").click();
  await expect(row(page, "Morning fixture")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await viewSwitch(page, "Calendar").click();
  await expect(page.getByRole("region", { name: "Scrollable calendar" })).toBeVisible();
});

test.describe("touch agenda", () => {
  test.use({ hasTouch: true, isMobile: true, viewport: { width: 320, height: 740 } });
  test("a tap opens details and dismissal restores the row without a hover overlay", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
    await setup(page);
    await viewSwitch(page, "Agenda").tap();
    await row(page, "Morning fixture").tap();
    const inspector = page.getByRole("complementary", { name: "Day events" });
    await expect(inspector).toBeVisible();
    await expect(page.getByRole("tooltip")).toHaveCount(0);
    await inspector.getByRole("button", { name: "Close day", exact: true }).tap();
    await expect(row(page, "Morning fixture")).toBeFocused();
    await expect(page.getByRole("tooltip")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});

test("Show more appends later event dates, skips empty months, preserves position and ends", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  await setup(page, { extraEvents: [
    ...Array.from({ length: 6 }, (_, i) => event(`Later fixture ${i + 9}`, `2027-01-${String(i + 9).padStart(2, "0")}`)),
    event("Spring fixture", "2027-04-12"), event("Summer fixture", "2027-07-01"),
  ] });
  await viewSwitch(page, "Agenda").click();
  await periodSwitch(page, "Upcoming").click();
  const scroll = agenda(page).locator(".agenda-scroll");
  await scroll.evaluate((element) => { element.scrollTop = 80; });
  const before = await scroll.evaluate((element) => element.scrollTop);
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(row(page, "Later fixture 14")).toHaveCount(1);
  await expect(agenda(page)).toContainText("Jan 1 – Jan 14");
  await expect(agenda(page).getByText("Next 7 days", { exact: false })).toHaveCount(0);
  expect(await scroll.evaluate((element) => element.scrollTop)).toBe(before);
  await expect(row(page, "Spring fixture")).toHaveCount(0);
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(row(page, "Summer fixture")).toHaveCount(1);
  await expect(agenda(page)).toContainText("Jan 1 – Jul 1");
  await expect(agenda(page).getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
  await expect(agenda(page).getByText("No later published events match your interests.", { exact: true })).toBeVisible();
  await expect(agenda(page).getByText(/Loading/)).toHaveCount(0);
  await row(page, "Summer fixture").scrollIntoViewIfNeeded();
  await row(page, "Summer fixture").click();
  await expect(page.getByRole("complementary", { name: "Day events" })).toContainText("Summer fixture");
  await page.getByRole("button", { name: "Close day", exact: true }).click();
  await expect(row(page, "Summer fixture")).toBeFocused();
});

test("filter changes preserve the expanded scope and reveal sparse later matches", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  await setup(page, { extraEvents: [event("Later NBA fixture", "2027-03-15", { league: "NBA", sport: "basketball" })] });
  await viewSwitch(page, "Agenda").click();
  await periodSwitch(page, "Upcoming").click();
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(row(page, "Outside next week")).toHaveCount(1);
  await page.getByRole("button", { name: "Interests · 1", exact: true }).click();
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByRole("checkbox", { name: "Select all Basketball", exact: true }).check();
  await chooser.getByRole("button", { name: "Show my calendar", exact: true }).click();
  await expect(agenda(page)).toContainText("Jan 1 – Jan 8");
  await expect(agenda(page).getByText("Next 7 days", { exact: false })).toHaveCount(0);
  await expect(row(page, "Outside next week")).toHaveCount(0);
  await expect(agenda(page).getByText("No published events match your interests in this range.", { exact: true })).toBeVisible();
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(row(page, "Later NBA fixture")).toHaveCount(1);
  await expect(agenda(page)).toContainText("Jan 1 – Mar 15");
  await expect(agenda(page).getByText("No later published events match your interests.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Interests · 1", exact: true }).click();
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar", exact: true }).click();
  await expect(agenda(page).getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
  await expect(agenda(page).getByText("Loading…", { exact: true })).toHaveCount(0);
});

test("discovery failures within rolling coverage terminate with Retry", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  const options = { publishedYears: [2026, 2027], missingYear: 2027 as number | undefined,
    extraEvents: [event("Future published fixture", "2027-02-10")] };
  await setup(page, options);
  await viewSwitch(page, "Agenda").click();
  await periodSwitch(page, "Upcoming").click();
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(agenda(page)).toContainText("No published schedule for 2027.");
  await expect(agenda(page).getByText(/Loading/)).toHaveCount(0);
  await expect(agenda(page).getByText("No later published events match your interests.", { exact: true })).toHaveCount(0);
  options.missingYear = undefined;
  await agenda(page).getByRole("button", { name: "Retry", exact: true }).click();
  await expect(agenda(page).getByRole("button", { name: "Show more", exact: true })).toBeEnabled();
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(row(page, "Future published fixture")).toHaveCount(1);
  await expect(agenda(page).getByText(/No published schedule for 2028|Loading/)).toHaveCount(0);
  await expect(agenda(page).getByText("No later published events match your interests.", { exact: true })).toBeVisible();
});

test("Show more ends when the selected interest has no later published events", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["NBA"] })));
  await setup(page);
  await viewSwitch(page, "Agenda").click();
  await periodSwitch(page, "Upcoming").click();
  await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
  await expect(agenda(page).getByText("No later published events match your interests.", { exact: true })).toBeVisible();
  await expect(agenda(page).getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
  await expect(agenda(page).getByText(/Loading/)).toHaveCount(0);
  await expect(agenda(page).locator(".agenda-row")).toHaveCount(0);
});

test.describe("last published year boundary", () => {
  test.use({ timezoneId: "Asia/Tokyo" });
  test("Show more retains the final source year's events that move into local January", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2027-01-01T02:00:00Z"));
    await setup(page, { extraEvents: [event("Last published timed fixture", "2027-12-31", {
      start_time_utc: "2027-12-31T23:30:00Z",
    })] });
    await viewSwitch(page, "Agenda").click();
    await periodSwitch(page, "Upcoming").click();
    await agenda(page).getByRole("button", { name: "Show more", exact: true }).click();
    await expect(row(page, "Last published timed fixture")).toContainText("8:30 AM");
    await expect(agenda(page).getByRole("heading", { name: "Saturday, January 1, 2028", exact: true })).toBeVisible();
    await expect(agenda(page).getByText(/No published schedule for 2028|Loading/)).toHaveCount(0);
    await expect(agenda(page).getByText("No later published events match your interests.", { exact: true })).toBeVisible();
  });
});
