import { expect, test, type Page } from "@playwright/test";

async function openMonth(page: Page, month: string) {
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: `Open ${month} 2026` }).click();
}

test("full PGA Tour spans stay separate from LPGA final-date markers and majors", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await chooser.locator("summary").filter({ hasText: /^Golf$/ }).click();
  await chooser.getByRole("checkbox", { name: "PGA Tour", exact: true }).check();
  await chooser.getByRole("checkbox", { name: "LPGA Tour", exact: true }).check();
  await expect(chooser.getByRole("checkbox", { name: "Golf · women's majors", exact: true })).toHaveCount(0);
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  for (const day of ["2026-09-17", "2026-09-20"])
    await expect(page.locator(`#day-${day} .event-pill`)).toContainText("Biltmore Championship");
  await expect(page.locator("#day-2026-09-20 .event-pill")).not.toContainText("Final date");
  await page.locator("#day-2026-09-27").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("LPGA Tour");
  await expect(detail).toContainText("Final date only");
  await expect(detail).toContainText("opening date and tee times are not supplied");
  await page.getByRole("button", { name: "Close day" }).click();
  await openMonth(page, "March");
  await page.locator("#day-2026-03-12").click();
  await expect(detail).toContainText("through 2026-03-15");
  await expect(detail.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", /espn\.com/);
});

test("reviewed expansion works with scrolling, inclusive spans and attribution downloads", async ({ page, request }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await expect(chooser).toBeVisible();
  for (const name of ["American football", "Climbing and weightlifting", "Golf"])
    await chooser.locator("summary").filter({ hasText: new RegExp(`^${name}$`) }).click();
  await expect(chooser.getByText("NFL", { exact: true })).toBeVisible();
  await expect(chooser.getByText("World Climbing", { exact: true })).toBeVisible();
  await expect(chooser.getByText("LPGA Tour", { exact: true })).toBeVisible();
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByText("IWF Worlds", { exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await openMonth(page, "October");
  await expect(page.locator("#day-2026-10-27 .event-pill")).toHaveCount(1);
  await page.locator("#day-2026-10-27").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("Time TBD");
  await expect(detail).toContainText("through 2026-11-08");
  await expect(detail.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", /wikidata\.org.*oldid=2499700131/);
  await page.getByRole("button", { name: "Close day" }).click();
  await expect(page.locator("#day-2026-10-31 .event-pill")).toHaveCount(1);
  await expect(page.locator("#day-2026-11-01 .event-pill")).toHaveCount(1);
  await page.locator("#day-2026-10-31 .event-pill").scrollIntoViewIfNeeded();
  // Let native navigation settle before a stationary hover, which is dismissed
  // while scrolling just like an already-open preview.
  await page.waitForTimeout(250);
  await page.locator("#day-2026-10-31 .event-pill").hover();
  await expect(page.getByRole("tooltip")).toContainText("October 27, 2026");
  await expect(page.getByRole("tooltip")).toContainText("November 8, 2026");
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("September");
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  const about = page.getByRole("dialog", { name: "About kickoff", exact: true });
  await expect(about).toContainText("Published schedules, not live scores");
  await expect(about).toContainText("CC BY-SA 4.0");
  await expect(about).toContainText("Full tour includes all published tournaments and majors");
  await expect(about).toContainText("LPGA coverage is selected dates");
  await expect(about).toContainText("selected reviewed four-belt undisputed bouts");
  await expect(about).toContainText("WBA, WBC, IBF or WBO");
  await expect(about).toContainText("Coverage is incomplete");
  await expect(about).toContainText("Verified times use your browser’s timezone automatically");
  const download = about.getByRole("link", { name: "Download Wikipedia schedule data" });
  const href = await download.getAttribute("href");
  expect(href).toMatch(/2026-wikipedia-[a-f0-9]{64}\.json$/);
  const response = await request.get(href!);
  expect(response.ok()).toBeTruthy();
  const component = await response.json();
  expect(component.license).toBe("CC BY-SA 4.0");
  expect(component.events.filter((e: { league: string }) => e.league === "NFL")).toHaveLength(0);
  await about.getByRole("button", { name: "Close", exact: true }).click();
  await expect(about).toHaveCount(0);
  await expect(page.getByRole("button", { name: "About kickoff and schedule coverage" })).toBeFocused();
});

test("expanded interest labels and date-only card details fit a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await expect(chooser).toBeVisible();
  await chooser.locator("summary").filter({ hasText: /^Combat sports$/ }).click();
  await expect(chooser.getByRole("checkbox", { name: "Boxing", exact: true })).toBeVisible();
  expect(await chooser.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
  await page.screenshot({ path: "test-results/expansion-mobile.png" });
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByRole("checkbox", { name: "Boxing", exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await openMonth(page, "October");
  await page.locator("#day-2026-10-24").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("three full titles");
  await expect(detail).toContainText("Time TBD");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test("calendar, advanced options and About kickoff fit a narrow mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v1", JSON.stringify(["F1"])));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("September");
  await expect(page.getByRole("searchbox")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^(Previous|Next) (month|year)$/ })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Interests · 1", exact: true }).click();
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await chooser.locator("details.advanced summary").click();
  await expect(chooser.getByRole("combobox")).toHaveCount(3);
  expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await chooser.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  const about = page.getByRole("dialog", { name: "About kickoff", exact: true });
  await expect(about).toBeVisible();
  expect(await about.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/about-mobile.png" });
  await page.keyboard.press("Escape");
  await expect(about).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Today", exact: true })).toBeVisible();
});
