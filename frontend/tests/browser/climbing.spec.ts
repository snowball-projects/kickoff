import { expandDayGroups, openDayEvent } from "./timeline-helpers";
import { expect, test } from "@playwright/test";

test.use({ timezoneId: "UTC" });

test("official climbing disciplines, time rollover, withheld clocks and sources render", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-10-15T17:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["IFSC_WORLD_CUP"], golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" }, motorsport_view: "race_only" })));
  await page.goto("/");
  await expect(page.locator("#day-2026-10-17 .event-pill")).toContainText("Men's Boulder Semi-final");
  await page.locator("#day-2026-10-18 .day-number").click();
  const detail = await openDayEvent(page, "Men's Boulder Final");
  await expect(detail).toContainText("Men's Boulder Final");
  await expect(detail).toContainText("1:00 AM");
  await expect(detail).toContainText("Women's Boulder Semi-final");
  await expect(detail.getByRole("link", { name: "Schedule source" }).first()).toHaveAttribute("href", /worldclimbing.com\/events\/world-climbing-series-salt-lake-city-2026$/);
  await page.getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-10-16 .day-number").click();
  await openDayEvent(page, "Women's Boulder Qualification");
  await expect(detail).toContainText("Women's Boulder Qualification");
  await expect(detail).toContainText("Time TBD");
  await expect(detail).toContainText("16:00");
  await expect(detail).toContainText("15:30");
  await page.getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-10-24 .day-number").click();
  await openDayEvent(page, "Men's Lead Qualification");
  await expect(detail).toContainText("Men's Lead Qualification");
  await expect(detail).toContainText("Men's Speed Final");
  await expect(detail).toContainText("Women's Speed Final");
  await expect(detail.locator(".timeline-clock").filter({ hasText: /^Session starts 9:00 PM/ })).toHaveCount(2);
  await expect(page.locator("#day-2026-10-24 .competition-chip")).toContainText("Santiago · 3 sessions");

  await expect(detail.getByRole("link", { name: "Schedule source" }).first()).toHaveAttribute("href", /worldclimbing.com\/events\/world-climbing-series-santiago-2026$/);
  await page.getByRole("button", { name: "Close day" }).click();
  await page.locator("#day-2026-10-25 .day-number").click();
  // Day groups expand independently from month groups.
  await expect(page.locator("#day-2026-10-25 .competition-chip")).toContainText("Santiago · 4 sessions");
  await expect(page.locator("#day-2026-10-25 .competition-events")).toHaveCount(0);
  await expandDayGroups(page);
  await expect(detail.locator(".timeline-pill[data-event-id]")).toHaveCount(4);
  for (const gender of ["Men's", "Women's"]) {
    await expect(detail).toContainText(`${gender} Lead Semi-final`);
    await expect(detail).toContainText(`${gender} Lead Final`);
  }
  await expect(detail.locator(".timeline-clock").filter({ hasText: /^Session starts 12:00 PM/ })).toHaveCount(2);
  await expect(detail.getByText("Time TBD", { exact: true })).toHaveCount(0);
  await expect(detail.locator(".timeline-clock").filter({ hasText: /^9:00 PM/ })).toHaveCount(1);
  await expect(detail.locator(".timeline-clock").filter({ hasText: /^10:00 PM/ })).toHaveCount(1);
  await page.screenshot({ path: "test-results/climbing-separated-rounds.png" });
});
