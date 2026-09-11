import { expect, test } from "@playwright/test";

test("golf season dates remain partial and separately selectable from majors", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Follow your sports" });
  await chooser.locator("summary").filter({ hasText: /^Golf$/ }).click();
  await chooser.getByRole("checkbox", { name: "PGA Tour · selected dates", exact: true }).check();
  await chooser.getByRole("checkbox", { name: "LPGA Tour · final dates", exact: true }).check();
  await expect(chooser.getByRole("checkbox", { name: "Golf · women's majors", exact: true })).not.toBeChecked();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  const biltmore = page.locator("#day-2026-09-20 .event-pill");
  await expect(biltmore).toContainText("Final date · Biltmore Championship");
  await expect(page.locator("#day-2026-09-19 .event-pill")).toHaveCount(0);
  await biltmore.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  await biltmore.hover();
  await expect(page.getByRole("tooltip")).toContainText("Final date only");
  await expect(page.getByRole("tooltip")).toContainText("opening date and tee times are not supplied");
  await page.getByPlaceholder("Search events").fill("Walmart");
  await page.getByRole("region", { name: "Search results" }).getByRole("button").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("LPGA Tour");
  await expect(detail).toContainText("Final date only");
  await expect(detail).toContainText("opening date and tee times are not supplied");
  await page.getByPlaceholder("Search events").fill("Players Championship");
  await page.getByRole("region", { name: "Search results" }).getByRole("button").click();
  await expect(detail).toContainText("through 2026-03-15");
  await expect(detail.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", /Q138632122/);
});

test("reviewed expansion works with scrolling, inclusive spans and attribution downloads", async ({ page, request }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Follow your sports" });
  await expect(chooser).toBeVisible();
  for (const name of ["American football", "Miscellaneous", "Golf"])
    await chooser.locator("summary").filter({ hasText: new RegExp(`^${name}$`) }).click();
  await expect(chooser.getByText("NFL · selected games", { exact: true })).toBeVisible();
  await expect(chooser.getByText("World Climbing", { exact: true })).toBeVisible();
  await expect(chooser.getByText("Golf · women's majors", { exact: true })).toBeVisible();
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByText("IWF Worlds", { exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await page.getByPlaceholder("Search events").fill("Weightlifting");
  const result = page.getByRole("region", { name: "Search results" }).getByRole("button");
  await expect(result).toHaveCount(1);
  await result.click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("Time TBD");
  await expect(detail).toContainText("through 2026-11-08");
  await expect(detail.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", /wikidata\.org.*oldid=2499700131/);
  await page.getByRole("button", { name: "Close day" }).click();
  await page.getByPlaceholder("Search events").fill("");
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
  await page.getByRole("button", { name: "About sportsbro and schedule coverage" }).click();
  const about = page.getByRole("dialog", { name: "About sportsbro", exact: true });
  await expect(about).toContainText("19 selected NFL opener, international and holiday games");
  await expect(about).toContainText("CC BY-SA 4.0");
  const download = about.getByRole("link", { name: "Download Wikipedia schedule data" });
  const href = await download.getAttribute("href");
  expect(href).toMatch(/2026-wikipedia-[a-f0-9]{64}\.json$/);
  const response = await request.get(href!);
  expect(response.ok()).toBeTruthy();
  const component = await response.json();
  expect(component.license).toBe("CC BY-SA 4.0");
  expect(component.events.filter((e: { league: string }) => e.league === "NFL")).toHaveLength(19);
});

test("expanded interest labels and date-only card details fit a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Follow your sports" });
  await expect(chooser).toBeVisible();
  await chooser.locator("summary").filter({ hasText: /^Combat sports$/ }).click();
  await expect(chooser.getByText("Boxing · selected unifications", { exact: true })).toBeVisible();
  expect(await chooser.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
  await page.screenshot({ path: "test-results/expansion-mobile.png" });
  await chooser.getByRole("button", { name: "Clear", exact: true }).click();
  await chooser.getByText("Boxing · selected unifications", { exact: true }).click();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await page.getByPlaceholder("Search events").fill("Navarrete");
  await page.getByRole("region", { name: "Search results" }).getByRole("button").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expect(detail).toContainText("three full titles");
  await expect(detail).toContainText("Time TBD");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
