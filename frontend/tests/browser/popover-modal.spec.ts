import { expect, test, type Locator, type Page } from "@playwright/test";

const fixture = {
  event_id: "preview-fixture", source: "offline-browser-fixture", sport: "soccer", league: "EPL",
  season: "2026", event_type: "match", title: "North City vs South United", subtitle: "Matchday notes remain in the day details",
  calendar_date: "2026-09-10", end_calendar_date: "2026-09-10", start_time_utc: "2026-09-10T18:00:00Z",
  start_time_local: null, status: "scheduled", venue: "Riverside Stadium", city: "London", country: "England",
  tags: [], participants: [], competition_phase: "regular_season", source_url: "https://example.org/schedule",
};

async function openCalendar(page: Page, status = "scheduled") {
  await page.clock.setFixedTime(new Date("2026-09-10T17:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v1", JSON.stringify(["EPL"])));
  await page.route("**/data/*.json", (route) => route.fulfill(new URL(route.request().url()).pathname.endsWith("/2026.json")
    ? { json: { schema_version: "1", season: 2026, providers: [], available_seasons: [2026], events: [{ ...fixture, status }] } }
    : { status: 404, body: "Unavailable" }));
  await page.goto("/");
  await expect(page.locator("#day-2026-09-10 .event-pill")).toHaveCount(1);
}

test("preview contains only event essentials; keyboard still opens notes and sources", async ({ page }) => {
  await openCalendar(page);
  const day = page.locator("#day-2026-09-10");
  await day.locator(".event-pill").hover();
  const preview = page.getByRole("tooltip");
  await expect(preview).toContainText(fixture.title);
  await expect(preview).toContainText("September 10, 2026");
  await expect(preview).toContainText("1:00 PM");
  await expect(preview).toContainText(fixture.venue);
  await expect(preview).not.toContainText(/scheduled|Open the day|Press Enter|Matchday notes/i);
  await expect(preview.locator(".league-label")).toHaveCount(0);
  await expect(preview.getByRole("link")).toHaveCount(0);
  await page.screenshot({ path: "test-results/compact-event-preview.png" });
  await page.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);
  await page.keyboard.press("Tab");
  await day.focus();
  await expect(day).toHaveAttribute("aria-describedby", "event-preview");
  await page.keyboard.press("Enter");
  const details = page.getByRole("complementary", { name: "Day events" });
  await expect(details).toContainText(fixture.subtitle);
  await expect(details.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", fixture.source_url);
});

for (const status of ["cancelled", "postponed", "unknown"]) {
  test(`preview preserves ${status} status`, async ({ page }) => {
    await openCalendar(page, status);
    await page.locator("#day-2026-09-10 .event-pill").hover();
    await expect(page.getByRole("tooltip").locator(".event-status")).toHaveText(status);
  });
}

async function checkChrome(dialog: Locator, page: Page) {
  const close = dialog.getByRole("button", { name: "Close", exact: true });
  const button = await close.boundingBox();
  const title = await dialog.getByRole("heading", { level: 2 }).boundingBox();
  const viewport = page.viewportSize()!;
  expect(button!.x).toBeGreaterThanOrEqual(0);
  expect(button!.y).toBeGreaterThanOrEqual(0);
  expect(button!.x + button!.width).toBeLessThanOrEqual(viewport.width);
  expect(button!.y + button!.height).toBeLessThanOrEqual(viewport.height);
  expect(button!.width).toBeGreaterThanOrEqual(44);
  expect(button!.height).toBeGreaterThanOrEqual(44);
  expect(title!.x + title!.width).toBeLessThanOrEqual(button!.x);
  expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await close.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
  })).toBe(true);
  return button;
}

for (const viewport of [
  { name: "desktop", width: 1280, height: 720 },
  { name: "mobile", width: 320, height: 640 },
  { name: "landscape", width: 667, height: 320 },
  // 1280×720 browser at 200% zoom has a 640×360 CSS-pixel layout viewport.
  { name: "200-percent-layout", width: 640, height: 360 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });
    for (const name of ["About kickoff", "Interests"]) {
      test(`${name} keeps its Close button in fixed chrome through long content and dismissal`, async ({ page }) => {
        await openCalendar(page);
        const opener = page.getByRole("button", { name: name === "Interests" ? /^Interests ·/ : "About kickoff and schedule coverage" });
        await opener.click();
        const dialog = page.getByRole("dialog", { name, exact: true });
        await checkChrome(dialog, page);
        const body = dialog.locator(".modal-body");
        // Exercise future growth as well as the actual About/Interests content.
        await body.evaluate((element) => {
          const extra = document.createElement("p");
          extra.textContent = "Additional coverage and interest options. ".repeat(100);
          element.append(extra);
        });
        const before = await checkChrome(dialog, page);
        await body.hover();
        await page.mouse.wheel(0, 900);
        await expect.poll(() => body.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
        await body.evaluate((element) => { element.scrollTop = element.scrollHeight; });
        const after = await checkChrome(dialog, page);
        expect(after!.y).toBe(before!.y);
        expect(await dialog.evaluate((element) => element.scrollTop)).toBe(0);
        await page.screenshot({ path: `test-results/${name.replaceAll(" ", "-").toLowerCase()}-${viewport.name}-scrolled.png` });
        await dialog.getByRole("button", { name: "Close", exact: true }).click();
        await expect(dialog).toHaveCount(0);
        await expect(opener).toBeFocused();
        await opener.click();
        await page.keyboard.press("Escape");
        await expect(dialog).toHaveCount(0);
        await expect(opener).toBeFocused();
        await opener.click();
        // A press inside then release outside must not dismiss accidentally.
        const title = await dialog.getByRole("heading", { level: 2 }).boundingBox();
        await page.mouse.move(title!.x + 4, title!.y + 4);
        await page.mouse.down();
        await page.mouse.move(2, 2);
        await page.mouse.up();
        await expect(dialog).toBeVisible();
        await page.mouse.click(2, 2);
        await expect(dialog).toHaveCount(0);
        await expect(opener).toBeFocused();
      });
    }
  });
}

test("keyboard focus stays in the modal and Close is usable after tabbing to its last link", async ({ page }) => {
  await openCalendar(page);
  const opener = page.getByRole("button", { name: "About kickoff and schedule coverage" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "About kickoff", exact: true });
  const close = dialog.getByRole("button", { name: "Close", exact: true });
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("link").last()).toBeFocused();
  await checkChrome(dialog, page);
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test.describe("touch modal", () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });
  test("About scroll and Close stay usable without opening a preview", async ({ page }) => {
    await openCalendar(page);
    await page.getByRole("button", { name: "About kickoff and schedule coverage" }).tap();
    const dialog = page.getByRole("dialog", { name: "About kickoff", exact: true });
    const cdp = await page.context().newCDPSession(page);
    const bounds = await dialog.locator(".modal-body").boundingBox();
    const x = bounds!.x + bounds!.width / 2;
    const y = bounds!.y + bounds!.height - 20;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    for (let step = 1; step <= 8; step++) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y - step * 35 }] });
    }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect.poll(() => dialog.locator(".modal-body").evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    await checkChrome(dialog, page);
    await page.screenshot({ path: "test-results/about-touch-scrolled.png" });
    await dialog.getByRole("button", { name: "Close", exact: true }).tap();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("tooltip")).toHaveCount(0);
  });
});
