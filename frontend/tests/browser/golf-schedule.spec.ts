import { reviewedBundle } from "../reviewed-fixture.mjs";
import { expect, test } from "./test";
import { setup } from "./fixtures";

const events = reviewedBundle().events.filter((event: { event_id: string }) => event.event_id === "espn-lpga_tour-401835174");
for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`ESPN LPGA schedule ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("full tournament span uses one ESPN source with no invented country", async ({ page }) => {
      await setup(page, events, { now: "2026-10-30T17:00:00Z" });
      for (const day of ["29", "30", "31"])
        await expect(page.locator(`#day-2026-10-${day} .event-pill`)).toHaveCount(1);
      await expect(page.locator("#day-2026-11-01 .event-pill")).toHaveCount(1);
      const cell = page.locator("#day-2026-10-30");
      await expect(cell.locator(".event-pill .country-flag")).toHaveCount(0);
      await cell.locator(".day-number").click();
      const pill = page.locator(".all-day-strip .event-pill");
      await expect(pill).toContainText("Maybank Championship");
      await pill.click();
      const sheet = page.getByRole("dialog");
      await expect(sheet.getByRole("link", { name: "Schedule source", exact: false }))
        .toHaveAttribute("href", "https://www.espn.com/golf/leaderboard?tournamentId=401835174");
      await expect(sheet).not.toContainText("Final date");
      await expect(sheet.locator(".country-flag")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/espn-golf-${width}-${colorScheme}.png` });
    });
  });
}
