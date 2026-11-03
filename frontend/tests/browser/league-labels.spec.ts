import { expect, test } from "./test";
import { event, setup } from "./fixtures";

test("month codes switch at 700px without changing full accessible names, golf titles or day titles", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 700, height: 1000 });
  await setup(page, [
    event("League fixture", "2026-10-28", { league: "CHAMPIONSHIP" }),
    event("Golf fixture", "2026-10-29", { league: "PGA_TOUR", sport: "golf", title: "The source tournament" }),
    event("Future fixture", "2026-10-30", { league: "FUTURE_LEAGUE" }),
  ]);
  const league = page.locator("#day-2026-10-28 .event-pill");
  const golf = page.locator("#day-2026-10-29 .event-pill");
  const future = page.locator("#day-2026-10-30 .event-pill");
  const accessibleName = await league.getAttribute("aria-label");
  expect(accessibleName).toContain("Championship");
  await expect(league.locator(".pill-label")).toBeVisible();
  await expect(league.locator(".pill-label")).toHaveText("Championship");
  await expect(league.locator(".pill-code")).toBeHidden();
  await expect(golf.locator(".pill-label")).toHaveText("The source tournament, Round 1");
  for (const width of [699, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(league.locator(".pill-label")).toBeHidden();
    await expect(league.locator(".pill-code")).toBeVisible();
    await expect(league.locator(".pill-code")).toHaveText("EFL");
    await expect(league).toHaveAttribute("aria-label", accessibleName!);
    await expect(golf.locator(".pill-code")).toHaveText("PGA");
    await expect(future.locator(".pill-text")).toHaveText("FUTURE LEAGUE");
    await expect(future.locator(".pill-code")).toHaveCount(0);
    expect(await league.evaluate((el) => getComputedStyle(el).fontSize)).toBe("11px");
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await expect(golf.locator(".pill-label")).toBeVisible();
  await expect(golf.locator(".pill-label")).toHaveText("The source tournament, Round 1");
  await league.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog").last()).toContainText("League fixture");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.locator("#day-2026-10-28 .day-number").press("Enter");
  await expect(page.locator(".all-day-strip .pill-text")).toHaveText("League fixture");
  await expect(page.locator(".all-day-strip .pill-code")).toHaveCount(0);
  await page.locator(".all-day-strip .event-pill").click();
  await expect(page.getByRole("dialog").last()).toContainText("League fixture");
});
