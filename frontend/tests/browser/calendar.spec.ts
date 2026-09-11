import { expect, test, type Page } from "@playwright/test";

// Every schedule request is answered locally. Missing years deliberately return
// 404, so navigation checks never depend on upstream fixtures or live schedules.
const events = Array.from({ length: 12 }, (_, index) => {
  const month = String(index + 1).padStart(2, "0");
  return [
    { league: "EPL", sport: "soccer", title: `Football fixture ${month}` },
    { league: "F1", sport: "motorsport", title: `Grand Prix ${month}` },
  ].map((event) => ({
    ...event,
    event_id: `${event.league}-${month}`,
    source: "offline-browser-fixture",
    season: "2026",
    event_type: event.league === "F1" ? "race" : "match",
    subtitle: null,
    calendar_date: `2026-${month}-10`,
    end_calendar_date: `2026-${month}-10`,
    start_time_utc: null,
    start_time_local: null,
    timezone: null,
    status: "scheduled",
    venue: null,
    city: null,
    region: null,
    country: event.league === "EPL" ? "England" : "Italy",
    round_or_stage: null,
    competition_phase: "regular_season",
    tags: [],
    participants: [],
    home_participant: null,
    away_participant: null,
    home_participant_name: null,
    away_participant_name: null,
    week_label: null,
    is_regular_season: true,
    is_postseason: false,
    is_exhibition: false,
    is_support_event: false,
  }));
}).flat();

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-10T17:00:00Z"));
  await page.addInitScript(() => {
    localStorage.setItem("sportsbro.interests.v1", JSON.stringify(["EPL", "F1"]));
  });
  await page.route("**/data/*.json", async (route) => {
    if (new URL(route.request().url()).pathname.endsWith("/2026.json")) {
      await route.fulfill({ json: {
        schema_version: "1",
        season: 2026,
        available_seasons: [2026],
        providers: [],
        updated_at: "2026-09-10T00:00:00Z",
        events,
      } });
    } else await route.fulfill({ status: 404, body: "Schedule unavailable" });
  });
  await page.goto("/");
  await expect(page.locator("#day-2026-09-10 .event-pill")).toHaveCount(2);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("September");
});

const feed = (page: Page) => page.getByRole("region", { name: "Scrollable calendar" });
const section = (page: Page, anchor: string) => page.locator(`[data-month="${anchor}"]`);
const heading = (page: Page) => page.getByRole("heading", { level: 1 });

async function nativeScrollTo(page: Page, anchor: string, offset = 0) {
  await feed(page).focus();
  await section(page, anchor).evaluate((element, amount) => {
    const root = element.closest(".month-feed")!;
    // Model user scrolling, including its interruption of an in-flight jump,
    // before applying an exact distance for repeatable recycling assertions.
    root.dispatchEvent(new WheelEvent("wheel", { bubbles: true }));
    root.scrollTo({ top: (element as HTMLElement).offsetTop + amount, behavior: "instant" });
  }, offset);
  await expect(heading(page)).toHaveText(new Intl.DateTimeFormat("en-US", { month: "long" }).format(new Date(`${anchor}T12:00:00Z`)));
}

async function monthPosition(page: Page, anchor: string) {
  return section(page, anchor).evaluate((element) => {
    const root = element.closest(".month-feed")!;
    return element.getBoundingClientRect().top - root.getBoundingClientRect().top;
  });
}

test("native wheel scrolling updates the month and year without replacing adjacent schedules", async ({ page }) => {
  const root = feed(page);
  await root.hover();
  const distance = await section(page, "2026-10-01").evaluate((element) =>
    (element as HTMLElement).offsetTop - element.closest(".month-feed")!.scrollTop + 40);
  await page.mouse.wheel(0, distance);
  await expect(heading(page)).toHaveText("October");
  await expect(page.getByRole("button", { name: "Show 2026 year calendar" })).toBeVisible();
  await page.mouse.wheel(0, -distance);
  await expect(heading(page)).toHaveText("September");

  await nativeScrollTo(page, "2027-01-01", 40);
  await expect(page.getByRole("button", { name: "Show 2027 year calendar" })).toBeVisible();
  await expect(section(page, "2027-01-01").locator(".month-status")).toContainText("No published schedule for 2027");
  await expect(section(page, "2027-01-01").locator(".event-pill")).toHaveCount(0);
  await expect(page.locator("#day-2026-12-10 .event-pill")).toHaveCount(2);
  await expect(page.locator("#day-2027-01-10")).toHaveAttribute("aria-label", /schedule unavailable/);
});

test("Today returns from a distant missing year, clears day/search, and keeps the current date highlighted", async ({ page }) => {
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: "Next year" }).click();
  await page.getByRole("button", { name: "Next year" }).click();
  await page.locator(".back-button").filter({ hasText: "Month" }).click();
  await expect(page.getByRole("button", { name: "Show 2028 year calendar" })).toBeVisible();
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(heading(page)).toHaveText("September");
  await expect(page.getByRole("button", { name: "Show 2026 year calendar" })).toBeVisible();
  await expect.poll(() => monthPosition(page, "2026-09-01")).toBeGreaterThanOrEqual(-1);
  await expect.poll(() => monthPosition(page, "2026-09-01")).toBeLessThanOrEqual(1);
  await expect(page.locator("#day-2026-09-10")).toHaveAttribute("aria-current", "date");
  await expect(page.locator("#day-2026-09-10")).toHaveClass(/is-today/);
  await page.getByRole("searchbox").fill("Football fixture");
  await expect(page.getByRole("region", { name: "Search results" })).toBeVisible();
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.getByRole("searchbox")).toHaveValue("");
  await expect(feed(page)).toBeVisible();
  await page.locator("#day-2026-09-10").click();
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Day events" })).toHaveCount(0);
});

test("day keyboard navigation crosses months and years and clamps leap-month dates", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 620 });
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: "Open January 2026" }).click();
  await page.locator("#day-2026-01-31").focus();
  await page.keyboard.press("PageDown");
  await expect(page.locator("#day-2026-02-28")).toBeFocused();
  await page.keyboard.press("PageUp");
  await expect(page.locator("#day-2026-01-28")).toBeFocused();
  await page.locator("#day-2026-01-01").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator("#day-2025-12-31")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#day-2026-01-01")).toBeFocused();
  await page.locator("#day-2026-01-31").focus();
  await page.keyboard.press("Shift+PageDown");
  await expect(page.locator("#day-2027-01-31")).toBeFocused();
  await expect(page.locator("#day-2027-01-31")).toBeInViewport({ ratio: 0.99 });
  await page.keyboard.press("Shift+PageDown");
  await expect(page.locator("#day-2028-01-31")).toBeFocused();
  await expect(page.locator("#day-2028-01-31")).toBeInViewport({ ratio: 0.99 });
  await page.keyboard.press("PageDown");
  await expect(page.locator("#day-2028-02-29")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#day-2028-03-01")).toBeFocused();
});

test("Today interrupts an in-progress smooth month navigation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const start = await feed(page).evaluate((element) => element.scrollTop);
  const target = await section(page, "2026-10-01").evaluate((element) => (element as HTMLElement).offsetTop);
  await page.getByRole("button", { name: "Next month" }).click();
  await expect.poll(async () => {
    const top = await feed(page).evaluate((element) => element.scrollTop);
    return top > start + 1 && top < target - 1;
  }, { intervals: [16] }).toBe(true);
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-09-01"))).toBeLessThanOrEqual(1);
  await expect(heading(page)).toHaveText("September");
  // Observe several animation frames after arrival, including the feed's idle
  // recenter interval, to catch a stale navigation restarting the old target.
  const stable = await feed(page).evaluate(async (element) => {
    const targetMonth = element.querySelector<HTMLElement>('[data-month="2026-09-01"]')!;
    for (let frame = 0; frame < 20; frame += 1) {
      await new Promise(requestAnimationFrame);
      if (Math.abs(element.scrollTop - targetMonth.offsetTop) > 1) return false;
    }
    return true;
  });
  expect(stable).toBe(true);
  await expect(heading(page)).toHaveText("September");
});

test("repeated month arrows advance from the pending destination during smooth scrolling", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const start = await feed(page).evaluate((element) => element.scrollTop);
  await page.getByRole("button", { name: "Next month" }).click();
  await page.evaluate(async (start) => {
    const root = document.querySelector<HTMLElement>(".month-feed")!;
    for (let frame = 0; frame < 60; frame += 1) {
      await new Promise(requestAnimationFrame);
      if (root.scrollTop > start + 1 && document.querySelector("h1")!.textContent === "September") {
        document.querySelector<HTMLButtonElement>('[aria-label="Next month"]')!.click();
        return;
      }
    }
    throw new Error("First month navigation did not enter the intermediate scroll state");
  }, start);
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-11-01"))).toBeLessThanOrEqual(1);
  await expect(heading(page)).toHaveText("November");
  await page.getByRole("button", { name: "Previous month" }).click();
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-10-01"))).toBeLessThanOrEqual(1);
});

test("resizing during a smooth Today jump reaches the current month in the new layout", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.setViewportSize({ width: 1000, height: 720 });
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: "Open June 2026" }).click();
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: "Next year" }).click();
  await page.locator(".back-button").filter({ hasText: "Month" }).click();
  await expect(page.getByRole("button", { name: "Show 2027 year calendar" })).toBeVisible();
  await expect(heading(page)).toHaveText("June");
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect.poll(() => feed(page).evaluate((element) => {
    const target = element.querySelector<HTMLElement>('[data-month="2026-09-01"]');
    if (!target) return false;
    const remaining = Math.abs(target.offsetTop - element.scrollTop);
    return remaining > 3 && remaining < element.clientHeight * 0.7 - 2;
  }), { intervals: [16] }).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-09-01"))).toBeLessThanOrEqual(2);
  await expect(heading(page)).toHaveText("September");
  await expect(page.getByRole("button", { name: "Show 2026 year calendar" })).toBeVisible();
  await expect(page.locator("#day-2026-09-10")).toBeInViewport({ ratio: 0.99 });
  await expect(page.locator("#day-2026-09-10")).toHaveAttribute("aria-current", "date");
});

test("search opens the matching day and closing restores focus to its calendar button", async ({ page }) => {
  await page.getByRole("searchbox").fill("Football fixture 04");
  await expect(page.getByRole("status")).toHaveText("1 matches in 2026");
  await page.getByRole("button", { name: /2026-04-10.*Football fixture 04/ }).click();
  const inspector = page.getByRole("complementary", { name: "Day events" });
  await expect(inspector.getByRole("heading", { name: "April 10", exact: true })).toBeFocused();
  await expect(inspector.getByRole("heading", { name: "Football fixture 04" })).toBeVisible();
  await expect(inspector.getByRole("heading", { name: "Grand Prix 04" })).toBeVisible();
  await expect(page.getByRole("searchbox")).toHaveValue("");
  await expect(heading(page)).toHaveText("April");
  await page.keyboard.press("Escape");
  await expect(inspector).toHaveCount(0);
  await expect(page.locator("#day-2026-04-10")).toBeFocused();
});

test("clearing search restores the month reached by scrolling", async ({ page }) => {
  await nativeScrollTo(page, "2026-11-01", 65);
  await page.getByRole("searchbox").fill("Football fixture");
  await expect(page.getByRole("status")).toHaveText("12 matches in 2026");
  await page.getByRole("searchbox").fill("");
  await expect(feed(page)).toBeVisible();
  await expect(heading(page)).toHaveText("November");
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-11-01"))).toBeLessThanOrEqual(1);
});

test("year overview opens a month and navigation arrows traverse the visible month", async ({ page }) => {
  await nativeScrollTo(page, "2026-11-01");
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await expect(page.locator(".mini-month")).toHaveCount(12);
  await expect(page.locator(".mini-today")).toHaveAttribute("aria-current", "date");
  await page.getByRole("button", { name: "Open June 2026" }).click();
  await expect(heading(page)).toHaveText("June");
  await expect.poll(() => monthPosition(page, "2026-06-01")).toBeLessThanOrEqual(1);
  await page.getByRole("button", { name: "Next month" }).click();
  await expect(heading(page)).toHaveText("July");
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-07-01"))).toBeLessThanOrEqual(1);
  await page.getByRole("button", { name: "Previous month" }).click();
  await expect(heading(page)).toHaveText("June");
});

test("changing interests updates pills while preserving the visible scroll position", async ({ page }) => {
  await nativeScrollTo(page, "2026-10-01", 125);
  const before = await monthPosition(page, "2026-10-01");
  await page.getByRole("button", { name: /Interests/ }).click();
  await page.locator("summary").filter({ hasText: /^Soccer$/ }).click();
  await page.getByRole("checkbox", { name: "England Premier League", exact: true }).uncheck();
  await page.getByRole("button", { name: "Show my calendar" }).click();
  await expect(page.locator("#day-2026-10-10 .event-pill")).toHaveCount(1);
  await expect(page.locator("#day-2026-10-10 .event-pill")).toContainText("Grand Prix 10");
  await expect(heading(page)).toHaveText("October");
  expect(Math.abs(await monthPosition(page, "2026-10-01") - before)).toBeLessThanOrEqual(1);
});

test("event hover preview is readable, hoverable, dismissible and keeps day clicks", async ({ page }) => {
  const day = page.locator("#day-2026-09-10");
  const pill = day.locator(".event-pill").filter({ hasText: "Grand Prix 09" });
  await pill.hover();
  const preview = page.getByRole("tooltip");
  await expect(preview).toContainText("Grand Prix 09");
  await expect(preview).toContainText("Time TBD");
  await expect(preview).toContainText("Italy");
  await expect(page.getByRole("complementary", { name: "Day events" })).toHaveCount(0);
  await preview.hover();
  await preview.getByText("Italy", { exact: true }).click();
  await page.waitForTimeout(220);
  await expect(preview).toBeVisible();
  const bounds = await preview.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(1280);
  await page.screenshot({ path: "test-results/event-preview-desktop.png" });
  await page.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);
  await page.getByRole("heading", { level: 1 }).hover();
  await pill.hover();
  await expect(preview).toBeVisible();
  await pill.click();
  await expect(preview).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Day events" })).toContainText("Grand Prix 09");
});

test("keyboard previews first event and Enter exposes every event and source", async ({ page }) => {
  await page.keyboard.press("Tab");
  const day = page.locator("#day-2026-09-10");
  await day.focus();
  const preview = page.getByRole("tooltip");
  await expect(preview).toBeVisible();
  await expect(day).toHaveAttribute("aria-describedby", "event-preview");
  await page.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);
  await expect(day).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#day-2026-09-11")).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(preview).toBeVisible();
  await page.keyboard.press("Enter");
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("Football fixture 09");
  await expect(detail).toContainText("Grand Prix 09");
  await expect(preview).toHaveCount(0);
});

test("scrolling dismisses an event preview before the month is recycled", async ({ page }) => {
  await page.locator("#day-2026-09-10 .event-pill").first().hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.mouse.wheel(0, 250);
  await expect(page.getByRole("tooltip")).toHaveCount(0);
});

test("keyboard month navigation restores the focused event preview after scrolling", async ({ page }) => {
  await page.keyboard.press("Tab");
  await page.locator("#day-2026-09-10").focus();
  await page.keyboard.press("PageDown");
  await expect(page.locator("#day-2026-10-10")).toBeFocused();
  await expect(page.getByRole("tooltip")).toContainText("October 10, 2026");
  await page.waitForTimeout(250);
  await expect(page.getByRole("tooltip")).toBeVisible();
});

test.describe("touch events", () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });
  test("a tap opens day details without a hover overlay", async ({ page }) => {
    await page.locator("#day-2026-09-10 .event-pill").first().tap();
    await expect(page.getByRole("tooltip")).toHaveCount(0);
    await expect(page.getByRole("complementary", { name: "Day events" })).toContainText("Grand Prix 09");
  });
});

test("long native traversal recenters without growing the DOM or moving the visual anchor", async ({ page }) => {
  for (const direction of [1, 1, 1, 1, -1, -1, -1, -1]) {
    const anchors = await page.locator("[data-month]").evaluateAll((items) => items.map((item) => (item as HTMLElement).dataset.month!));
    const anchor = anchors[direction === 1 ? 7 : 1];
    await nativeScrollTo(page, anchor, 73);
    await expect.poll(() => page.locator("[data-month]").first().getAttribute("data-month")).not.toBe(anchors[0]);
    await expect(page.locator("[data-month]")).toHaveCount(9);
    expect(Math.abs(await monthPosition(page, anchor) + 73)).toBeLessThanOrEqual(1);
    const ids = await page.locator(".month-feed [id^='day-']").evaluateAll((items) => items.map((item) => item.id));
    expect(new Set(ids).size).toBe(ids.length);
  }
});

test("a focusable calendar supports native Page Down and reduced-motion Today", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await feed(page).focus();
  const start = await feed(page).evaluate((element) => element.scrollTop);
  await page.keyboard.press("PageDown");
  await expect.poll(() => feed(page).evaluate((element) => element.scrollTop)).toBeGreaterThan(start);
  await nativeScrollTo(page, "2026-12-01");
  await page.evaluate(() => {
    const calls: string[] = [];
    const original = Element.prototype.scrollTo;
    Object.assign(window, { calendarScrollBehaviors: calls });
    Element.prototype.scrollTo = function (first?: number | ScrollToOptions, second?: number) {
      if (this.matches(".month-feed") && typeof first === "object") calls.push(first.behavior || "auto");
      const scroll = original.bind(this);
      if (typeof first === "number") scroll(first, second || 0);
      else scroll(first);
    };
  });
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-09-01"))).toBeLessThanOrEqual(1);
  await expect(heading(page)).toHaveText("September");
  const behaviors = await page.evaluate(() => Reflect.get(window, "calendarScrollBehaviors") as string[]);
  expect(behaviors).toContain("auto");
  expect(behaviors).not.toContain("smooth");
});

test("delayed scroll delivery completes the jump at its destination before resizing", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.setViewportSize({ width: 1000, height: 720 });
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: "Open June 2026" }).click();
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-06-01"))).toBeLessThanOrEqual(2);
  await page.evaluate(() => {
    const root = document.querySelector<HTMLElement>(".month-feed")!;
    const scrollTo = root.scrollTo.bind(root);
    root.scrollTo = ((options: ScrollToOptions) => {
      scrollTo(options);
      // Exercise the ordering seen when staging scroll delivery precedes the
      // animation-frame callback's idle scheduling, without changing the motion.
      if (options.behavior === "smooth") {
        root.dispatchEvent(new Event("scroll"));
        // A busy main thread can deliver the idle timer before the compositor's
        // next scroll event. Hold that delivery through the resize below.
        root.addEventListener("scroll", (event) => event.stopImmediatePropagation(), { capture: true });
      }
    }) as typeof root.scrollTo;
  });
  await page.getByRole("button", { name: "Today", exact: true }).click();
  // Silence in scroll delivery must finish at the destination, never preserve
  // an intermediate offset as a completed jump. No animation-duration guess.
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-09-01"))).toBeLessThanOrEqual(2);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(async () => Math.abs(await monthPosition(page, "2026-09-01"))).toBeLessThanOrEqual(2);
  await expect(heading(page)).toHaveText("September");
});

async function stallSmoothJump(page: Page) {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.evaluate(() => {
    const root = document.querySelector<HTMLElement>('.month-feed')!;
    const scrollTo = root.scrollTo.bind(root);
    root.scrollTo = ((options: ScrollToOptions) => {
      if (options.behavior === 'smooth') {
        scrollTo({ top: root.scrollTop + 100, behavior: 'instant' });
      } else scrollTo(options);
    }) as typeof root.scrollTo;
  });
}

test('a stalled browser jump reaches its bounded destination within the deadline', async ({ page }) => {
  await stallSmoothJump(page);
  await page.getByRole('button', { name: 'Next month' }).click();
  await expect.poll(async () => Math.abs(await monthPosition(page, '2026-10-01')), { timeout: 5000 }).toBeLessThanOrEqual(2);
  await expect(heading(page)).toHaveText('October');
});

test('manual wheel interruption prevents a stalled jump from snapping later', async ({ page }) => {
  await stallSmoothJump(page);
  await page.getByRole('button', { name: 'Next month' }).click();
  await feed(page).hover();
  await page.mouse.wheel(0, 60);
  // Observe past the programmatic fallback deadline after explicit user input.
  await page.waitForTimeout(2200);
  await expect.poll(async () => Math.abs(await monthPosition(page, '2026-10-01'))).toBeGreaterThan(100);
});
