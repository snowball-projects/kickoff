import { expect, test } from "./test";
import { event, setup } from "./fixtures";

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`current-time marker ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("matches today's green, updates on the minute, and leaves events clickable", async ({ page }) => {
      const now = "2026-10-28T17:59:30Z";
      await page.clock.install({ time: new Date(now) });
      await setup(page, [event("At the line", "2026-10-28", { start_time_utc: "2026-10-28T18:00:00Z" })], { now });
      await page.locator("#day-2026-10-28 .day-number").click();
      const marker = page.locator(".timeline-now"), bubble = marker.locator("time");
      await expect(bubble).toHaveText("12:59");
      await expect(bubble).toHaveAttribute("aria-label", "Current time, 12:59pm");
      expect(await marker.evaluate((el) => parseFloat(getComputedStyle(el).top))).toBeCloseTo(779 * 80 / 60, 2);
      const green = await page.locator(".week-strip .selected.today").evaluate((el) => getComputedStyle(el).backgroundColor);
      await expect(marker).toHaveCSS("border-top-color", green);
      await expect(bubble).toHaveCSS("background-color", green);
      await expect(bubble).toBeInViewport();
      const bounds = await bubble.boundingBox();
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
      await page.clock.setSystemTime(new Date(now));
      await page.clock.runFor(29_000);
      await expect(bubble).toHaveText("12:59");
      await page.clock.runFor(2_000);
      await expect(bubble).toHaveText("1:00");
      await expect(marker).toHaveCSS("top", "1040px");
      await page.screenshot({ path: `test-results/current-time-${width}-${colorScheme}.png` });
      await page.locator('.timeline-events [data-event-id="At the line"]').click({ position: { x: 30, y: 1 } });
      await expect(page.getByRole("dialog")).toBeVisible();
    });
  });
}

for (const { zone, now, date, before, after, top } of [
  { zone: "America/Chicago", now: "2026-03-08T07:59:30Z", date: "2026-03-08", before: "1:59", after: "3:00", top: 240 },
  { zone: "America/Chicago", now: "2026-11-01T06:59:30Z", date: "2026-11-01", before: "1:59", after: "1:00", top: 80 },
  { zone: "Asia/Kathmandu", now: "2026-12-31T23:30:30Z", date: "2027-01-01", before: "5:15", after: "5:16", top: 316 * 80 / 60 },
]) {
  test.describe(`viewer clock ${zone} ${date}`, () => {
    test.use({ timezoneId: zone, reducedMotion: "reduce" });
    test("follows the current timezone's date and DST wall clock", async ({ page }) => {
      await page.clock.install({ time: new Date(now) });
      await setup(page, [event("Clock fixture", date)], { now });
      await page.locator(`#day-${date} .day-number`).click();
      await expect(page.locator(".timeline-now time")).toHaveText(before);
      await page.clock.setSystemTime(new Date(now));
      await page.clock.runFor(31_000);
      await expect(page.locator(".timeline-now time")).toHaveText(after);
      expect(await page.locator(".timeline-now").evaluate((el) => parseFloat(getComputedStyle(el).top))).toBeCloseTo(top, 2);
    });
  });
}

test("midnight removes yesterday's line, marks the new day, and returning to a tab refreshes the clock", async ({ page }) => {
  const now = "2026-10-29T04:59:30Z";
  await page.clock.install({ time: new Date(now) });
  await setup(page, [event("Before midnight"), event("After midnight", "2026-10-29")], { now });
  await page.locator("#day-2026-10-28 .day-number").click();
  await expect(page.locator(".timeline-now time")).toHaveText("11:59");
  await page.clock.setSystemTime(new Date(now));
  await page.clock.runFor(31_000);
  await expect(page.locator(".timeline-now")).toHaveCount(0);
  await expect(page.locator('.week-strip [data-date="2026-10-29"] .today')).toHaveCount(1);
  await page.locator('.week-strip [data-date="2026-10-29"]').click();
  await expect(page.locator(".timeline-now time")).toHaveText("12:00");
  await expect(page.locator(".timeline-now")).toHaveCSS("top", "0px");
  await expect(page.locator(".timeline-now time")).toBeInViewport();
  await page.clock.setSystemTime(new Date("2026-10-29T15:17:00Z"));
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.locator(".timeline-now time")).toHaveText("10:17");
  await page.clock.setSystemTime(new Date("2026-10-29T16:28:00Z"));
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await expect(page.locator(".timeline-now time")).toHaveText("11:28");
  await page.locator('.week-strip [data-date="2026-10-30"]').click();
  await expect(page.locator(".timeline-now")).toHaveCount(0);
});
