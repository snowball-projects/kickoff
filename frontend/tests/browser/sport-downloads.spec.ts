import { expect, test } from "./test";
import { agendaToggle, chooser, event, setup } from "./fixtures";

const catalog = [2025, 2026, 2027].flatMap((year) => [
  event(`NFL ${year}`, `${year}-10-28`, { sport: "football", league: "NFL" }),
  event(`Soccer ${year}`, `${year}-10-28`, { sport: "soccer", league: "EPL" }),
]);
const sport = (page: Parameters<typeof setup>[0], name: string) => chooser(page).getByRole("button", { name, exact: true });
const save = (page: Parameters<typeof setup>[0]) => chooser(page).getByRole("button", { name: "Show my calendar", exact: true });
const openInterests = (page: Parameters<typeof setup>[0]) => page.getByRole("button", { name: "Interests", exact: true }).click();

test.use({ reducedMotion: "reduce" });

test("empty first visit fetches only metadata; staged choices download only after saving", async ({ page }) => {
  const requests: string[] = [];
  await setup(page, catalog, { firstVisit: true, requests });
  await expect(sport(page, "Football")).toBeEnabled();
  await expect(sport(page, "Soccer")).toBeEnabled();
  expect(requests).toEqual(["manifest.json"]);
  await sport(page, "Football").click();
  await expect(save(page)).toBeEnabled();
  expect(requests).toEqual(["manifest.json"]);
  await save(page).click();
  await expect(page.locator("#day-2026-10-28 .event-pill")).toHaveText("NFL");
  expect([...requests].sort()).toEqual(["manifest.json", ...[2025, 2026, 2027].map((year) => `${year}-football.json`)].sort());

  await openInterests(page);
  await sport(page, "Soccer").click();
  expect(requests.filter((file) => file.endsWith("-soccer.json"))).toEqual([]);
  await save(page).click();
  await expect(page.locator("#day-2026-10-28 .event-pill")).toHaveCount(2);
  expect(requests.filter((file) => file.endsWith("-soccer.json")).sort()).toEqual([2025, 2026, 2027].map((year) => `${year}-soccer.json`));
  const beforeRemoval = [...requests];
  await openInterests(page);
  await sport(page, "Football").click();
  await save(page).click();
  await expect(page.locator("#day-2026-10-28 .event-pill .pill-text")).toHaveText("Premier League");
  expect(requests).toEqual(beforeRemoval);
  await agendaToggle(page).click();
  await expect(page.locator(".agenda-row")).toHaveCount(1);
  await expect(page.locator(".agenda-row")).toContainText("Soccer 2026");
});

test("all selected sports retain every event while downloading each published file once", async ({ page }) => {
  const requests: string[] = [];
  await setup(page, [...catalog,
    event("Basketball fixture", undefined, { sport: "basketball", league: "NBA" }),
    event("Golf fixture", undefined, { sport: "golf", league: "PGA_TOUR" }),
  ], { requests });
  await agendaToggle(page).click();
  await expect(page.locator(".agenda-row")).toHaveCount(4);
  for (const title of ["NFL 2026", "Soccer 2026", "Basketball fixture", "Golf fixture"])
    await expect(page.getByRole("region", { name: "Agenda", exact: true })).toContainText(title);
  expect([...requests].sort()).toEqual(["manifest.json", "2026-basketball.json", "2026-golf.json",
    ...[2025, 2026, 2027].flatMap((year) => [`${year}-football.json`, `${year}-soccer.json`])].sort());
  await openInterests(page);
  await expect(sport(page, "Football")).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  expect(new Set(requests).size).toBe(requests.length);
});

test("held sport files never block Interests and late results cannot restore a removed sport", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const requests: string[] = [];
  await setup(page, catalog, { saved: { leagues: ["NFL"] }, requests,
    holdFiles: { "2026-football.json": held }, wait: false });
  await expect.poll(() => requests.includes("2026-football.json")).toBe(true);
  await openInterests(page);
  await expect(sport(page, "Football")).toBeEnabled();
  await expect(sport(page, "Soccer")).toBeEnabled();
  await expect(save(page)).toBeEnabled();
  await sport(page, "Football").click();
  await sport(page, "Soccer").click();
  await save(page).click();
  await expect(page.locator("#day-2026-10-28 .event-pill .pill-text")).toHaveText("Premier League");
  const settled = page.waitForResponse("**/data/2026-football.json");
  release();
  await settled;
  await agendaToggle(page).click();
  await expect(page.locator(".agenda-row")).toHaveCount(1);
  await expect(page.locator(".agenda-row")).toContainText("Soccer 2026");
  await expect(page.locator(".calendar-status")).not.toContainText("Loading");
});

test("a failed football file leaves metadata usable and switching to soccer clears the stale error", async ({ page }) => {
  const requests: string[] = [];
  await setup(page, catalog, { saved: { leagues: ["NFL"] }, requests, failedFiles: ["2026-football.json"] });
  await expect(page.locator(".calendar-status")).toContainText("could not be loaded");
  await openInterests(page);
  await expect(sport(page, "Soccer")).toBeEnabled();
  await expect(save(page)).toBeEnabled();
  await sport(page, "Football").click();
  await sport(page, "Soccer").click();
  await save(page).click();
  await expect(page.locator("#day-2026-10-28 .event-pill .pill-text")).toHaveText("Premier League");
  await expect(page.locator(".calendar-status")).not.toContainText("could not be loaded");
  expect(requests.filter((file) => file === "manifest.json")).toHaveLength(1);
  expect(requests.filter((file) => file === "2026-football.json").length).toBeGreaterThanOrEqual(1);
});

test("retry refreshes a failed sport download without fetching unselected sports", async ({ page }) => {
  const requests: string[] = [];
  const options = { saved: { leagues: ["NFL"] }, requests, failedFiles: ["2026-football.json"] };
  await setup(page, catalog, options);
  await expect(page.locator(".calendar-status")).toContainText("could not be loaded");
  await page.clock.install({ time: new Date("2026-10-28T17:00:00Z") });
  const failedRequests = requests.filter((file) => file === "2026-football.json").length;
  await page.clock.fastForward(120_000);
  expect(requests.filter((file) => file === "2026-football.json")).toHaveLength(failedRequests);
  options.failedFiles = [];
  await page.locator(".calendar-status").getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator("#day-2026-10-28 .event-pill")).toHaveText("NFL");
  await expect(page.locator(".calendar-status")).not.toContainText("could not be loaded");
  expect(requests.filter((file) => file === "manifest.json")).toHaveLength(2);
  expect(requests.filter((file) => file === "2026-football.json")).toHaveLength(failedRequests + 1);
  expect(requests.some((file) => file.endsWith("-soccer.json"))).toBe(false);
});

test.describe("split files at year boundaries", () => {
  test.use({ timezoneId: "Asia/Tokyo" });
  test("an unpublished year retains timed neighboring events and inclusive date-only spans", async ({ page }) => {
    const requests: string[] = [];
    await setup(page, [
      event("Boundary kickoff", "2026-12-31", { sport: "football", league: "NFL", start_time_utc: "2026-12-31T23:00:00Z" }),
      event("Inclusive tournament", "2026-12-30", { sport: "golf", league: "PGA_TOUR", end_calendar_date: "2027-01-02" }),
      event("Unselected basketball", "2026-12-31", { sport: "basketball", league: "NBA" }),
    ], { now: "2027-01-01T00:00:00Z", missing: 2027, saved: { leagues: ["NFL", "PGA_TOUR"] }, requests });
    await page.locator("#day-2027-01-01 .day-number").click();
    await expect(page.locator(".day-timeline-stage")).toContainText("No published schedule for 2027.");
    await expect(page.locator(".timeline-events .event-pill")).toHaveText("Boundary kickoff");
    await expect(page.locator(".all-day-strip")).toContainText("Inclusive tournament");
    await page.locator(".timeline-events .event-pill").click();
    await expect(page.getByRole("dialog")).toContainText("8:00 AM");
    await page.keyboard.press("Escape");
    await page.locator('.week-strip [data-date="2027-01-02"]').click();
    await expect(page.locator(".all-day-strip")).toContainText("Inclusive tournament");
    await page.locator('.week-strip [data-date="2027-01-03"]').click();
    await expect(page.locator(".all-day-strip .event-pill")).toHaveCount(0);
    expect(requests.some((file) => file.endsWith("-basketball.json"))).toBe(false);
    expect(requests).toContain("2026-football.json");
    expect(requests).toContain("2026-golf.json");
    expect(requests.some((file) => /^2027-/.test(file))).toBe(false);
  });
});

test.describe("published downloads without JavaScript", () => {
  test.use({ javaScriptEnabled: false });
  test("the noscript link opens a working per-sport download index with source metadata", async ({ page }) => {
    await page.goto("/");
    const downloads = page.getByRole("link", { name: "Published schedules and sources", exact: true });
    await expect(downloads).toHaveAttribute("href", "./data/");
    await downloads.click();
    await expect(page).toHaveTitle("kickoff schedule data");
    await expect(page.getByRole("link", { name: "Manifest, sources and licenses (JSON)", exact: true })).toHaveAttribute("href", "manifest.json");
    const links = page.locator('li a[href$=".json"]');
    expect(await links.count()).toBeGreaterThan(0);
    const files = await links.evaluateAll((anchors) => anchors.map((anchor) => anchor.getAttribute("href")!));
    expect(files.every((file) => /^\d{4}-.+\.json$/.test(file))).toBe(true);
    const response = await page.request.get(new URL(files[0], page.url()).href);
    expect(response.ok()).toBe(true);
    const bundle = await response.json();
    expect(bundle.events.length).toBeGreaterThan(0);
    expect(bundle.sources.length).toBeGreaterThan(0);
    expect(bundle.data_license_notice).toBeTruthy();
  });
});
