import { expect, test } from "@playwright/test";

test.use({ timezoneId: "UTC" });

test("official climbing disciplines, time rollover, withheld clocks and sources render", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-10-15T17:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v1", JSON.stringify(["IFSC_WORLD_CUP"])));
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
  await expect(detail).toContainText("Men's & Women's Speed finals");
  await expect(detail).toContainText("9:00 PM");
  await expect(detail.getByRole("link", { name: "Schedule source" }).first()).toHaveAttribute("href", /worldclimbing.com\/events\/world-climbing-series-santiago-2026$/);
});
