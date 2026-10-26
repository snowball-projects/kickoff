import { expect, test } from "@playwright/test";

test.use({ timezoneId: "UTC" });

test("official climbing disciplines, time rollover, withheld clocks and sources render", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-10-15T17:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["IFSC_WORLD_CUP"], golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" }, motorsport_view: "race_only" })));
  await page.goto("/");
  await expect(page.locator("#day-2026-10-17 .event-pill")).toContainText("Men's Boulder semi-final");
  await page.locator("#day-2026-10-18").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("Men's Boulder final");
  await expect(detail).toContainText("1:00 AM");
  await expect(detail).toContainText("Women's Boulder semi-final");
  await expect(detail.getByRole("link", { name: "Schedule source" }).first()).toHaveAttribute("href", /worldclimbing.com\/events\/world-climbing-series-salt-lake-city-2026$/);
  await page.getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-10-16").click();
  await expect(detail).toContainText("Women's Boulder qualification");
  await expect(detail).toContainText("Time TBD");
  await expect(detail).toContainText("16:00");
  await expect(detail).toContainText("15:30");
  await page.getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-10-24").click();
  await expect(detail).toContainText("Men's Lead qualification");
  await expect(detail).toContainText("Men's Speed final");
  await expect(detail).toContainText("Women's Speed final");
  await expect(detail.getByText("Session starts 9:00 PM", { exact: true })).toHaveCount(2);
  await expect(page.locator("#day-2026-10-24 .event-pill")).toHaveCount(3);

  await expect(detail.getByRole("link", { name: "Schedule source" }).first()).toHaveAttribute("href", /worldclimbing.com\/events\/world-climbing-series-santiago-2026$/);
  await page.getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-10-25").click();
  // Month cells retain their existing three-pill limit and disclose overflow.
  await expect(page.locator("#day-2026-10-25 .event-pill")).toHaveCount(3);
  await expect(page.locator("#day-2026-10-25 .more-events")).toHaveText("+1 more");
  await expect(detail.locator("article")).toHaveCount(4);
  for (const gender of ["Men's", "Women's"]) {
    await expect(detail).toContainText(`${gender} Lead semi-final`);
    await expect(detail).toContainText(`${gender} Lead final`);
  }
  await expect(detail.getByText("Session starts 12:00 PM", { exact: true })).toHaveCount(2);
  await expect(detail.getByText("Time TBD", { exact: true })).toHaveCount(2);
  await page.screenshot({ path: "test-results/climbing-separated-rounds.png" });
});
