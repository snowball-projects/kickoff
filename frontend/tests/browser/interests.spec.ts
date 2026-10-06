import { expect, test, type Page } from "@playwright/test";

async function openMonth(page: Page, month: string) {
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: `Open ${month} 2026` }).click();
}

test("group choices are independent, mixed, collapsible and preserve saved leagues", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await expect(chooser).toBeVisible();
  await expect(chooser.getByRole("heading", { name: "Interests", exact: true })).toBeVisible();
  await expect(page.getByText("Follow your sports", { exact: true })).toHaveCount(0);
  for (const name of ["Soccer", "Motorsports", "American football", "Combat sports", "Golf", "Climbing and weightlifting"])
    await expect(chooser.getByRole("checkbox", { name: `Select all ${name}`, exact: true })).toBeVisible();
  const soccer = chooser.getByRole("region", { name: "Soccer interests" });
  const allSoccer = soccer.getByRole("checkbox", { name: "Select all Soccer", exact: true });
  await allSoccer.check();
  await soccer.locator("summary").click();
  await expect(soccer.getByRole("checkbox", { name: "England Premier League", exact: true })).toBeChecked();
  const championship = soccer.getByRole("checkbox", { name: "England EFL Championship · England", exact: true });
  await expect(championship).toBeChecked();
  await expect(soccer.getByRole("img", { name: "England", exact: true })).toHaveCount(2);
  await page.screenshot({ path: "test-results/soccer-flags-desktop.png" });
  await championship.uncheck();
  await expect(allSoccer).toHaveJSProperty("indeterminate", true);
  await allSoccer.check();
  await expect(championship).toBeChecked();
  await soccer.locator("summary").click();
  await allSoccer.uncheck();
  await chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true }).check();
  await chooser.locator("summary").filter({ hasText: /^Climbing and weightlifting$/ }).click();
  await chooser.getByRole("checkbox", { name: "IWF Worlds", exact: true }).check();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!).leagues)).toEqual(["F1", "NASCAR_CUP", "INDYCAR", "IWF_WORLDS"]);
  await page.reload();
  await expect(chooser).toHaveCount(0);
  await page.getByRole("button", { name: "Interests · 4", exact: true }).click();
  await expect(chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true })).toBeChecked();
  await expect(chooser.getByRole("checkbox", { name: "Select all Climbing and weightlifting", exact: true })).toHaveJSProperty("indeterminate", true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: "test-results/grouped-interests-mobile.png" });
});

test("uniform advanced selectors save together, cancel cleanly, and survive reopening on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  const advanced = chooser.locator("details.advanced");
  await expect(advanced.locator("select").first()).toBeHidden();
  await expect(chooser.getByText("More filters", { exact: true })).toHaveCount(0);
  await chooser.locator("summary").filter({ hasText: /^Golf$/ }).click();
  await expect(chooser.getByRole("region", { name: "Golf interests" }).getByRole("checkbox")).toHaveCount(3);
  await chooser.getByRole("checkbox", { name: "Select all Golf", exact: true }).check();
  await chooser.locator("summary").filter({ hasText: /^Combat sports$/ }).click();
  await expect(chooser.getByRole("checkbox", { name: "One", exact: true })).toBeVisible();
  await chooser.getByRole("checkbox", { name: "Boxing", exact: true }).check();
  await advanced.locator("summary").click();
  await expect(advanced.getByRole("combobox")).toHaveCount(3);
  await expect(advanced.locator("fieldset")).toHaveCount(0);
  await expect(advanced.getByRole("checkbox")).toHaveCount(0);
  await expect(chooser.getByText(/Selected reviewed bouts only|Full tour shows|Only published coverage appears/)).toHaveCount(0);
  await advanced.getByLabel("PGA Tour", { exact: true }).selectOption("majors_only");
  await advanced.getByLabel("LPGA Tour", { exact: true }).selectOption("majors_only");
  await advanced.getByLabel("Motorsport", { exact: true }).selectOption("full_weekend");
  const selectorStyles = await advanced.getByRole("combobox").evaluateAll((elements) => elements.map((element) => {
    const style = getComputedStyle(element);
    return [style.height, style.border, style.borderRadius, style.fontFamily, style.fontSize, style.padding];
  }));
  expect(selectorStyles[1]).toEqual(selectorStyles[0]);
  expect(selectorStyles[2]).toEqual(selectorStyles[0]);
  expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/advanced-options-mobile.png" });
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  const saved = await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"));
  expect(JSON.parse(saved!)).toMatchObject({
    golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "majors_only" },
    motorsport_view: "full_weekend",
  });
  expect(JSON.parse(saved!)).not.toHaveProperty("boxing_categories");
  await openMonth(page, "January");
  await expect(page.locator("#day-2026-01-18 .event-pill").filter({ hasText: "Sony Open" })).toHaveCount(0);
  await openMonth(page, "April");
  await expect(page.locator("#day-2026-04-09 .event-pill").filter({ hasText: "Masters Tournament" })).toHaveCount(1);
  await page.getByRole("button", { name: "Interests · 3", exact: true }).click();
  await advanced.locator("summary").click();
  await advanced.getByLabel("PGA Tour", { exact: true }).selectOption("full_tour");
  await chooser.getByRole("checkbox", { name: "Select all Golf", exact: true }).uncheck();
  await page.keyboard.press("Escape");
  await expect(chooser).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"))).toEqual(saved);
  await expect(page.getByRole("button", { name: "Interests · 3", exact: true })).toBeFocused();
  await page.getByRole("button", { name: "Interests · 3", exact: true }).click();
  await expect(chooser.getByRole("checkbox", { name: "Select all Golf", exact: true })).toBeChecked();
  await advanced.locator("summary").click();
  await expect(advanced.getByLabel("PGA Tour", { exact: true })).toHaveValue("majors_only");
  await advanced.getByLabel("Motorsport", { exact: true }).selectOption("race_only");
  await chooser.getByRole("button", { name: "Close", exact: true }).click();
  expect(await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"))).toEqual(saved);
  await page.reload();
  await page.getByRole("button", { name: "Interests · 3", exact: true }).click();
  await advanced.locator("summary").click();
  await expect(advanced.getByLabel("Motorsport", { exact: true })).toHaveValue("full_weekend");
  await expect(advanced.getByLabel("LPGA Tour", { exact: true })).toHaveValue("majors_only");
});

test("legacy mixed golf choices migrate without a second onboarding", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v1",
    JSON.stringify(["GOLF_MAJORS_MEN", "LPGA_TOUR", "GOLF_MAJORS_WOMEN"])));
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await expect(chooser).toHaveCount(0);
  await page.getByRole("button", { name: "Interests · 2", exact: true }).click();
  await chooser.locator("details.advanced summary").click();
  await expect(chooser.locator("details.advanced").getByLabel("PGA Tour", { exact: true })).toHaveValue("majors_only");
  await expect(chooser.locator("details.advanced").getByLabel("LPGA Tour", { exact: true })).toHaveValue("full_tour");
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  await page.reload();
  await expect(chooser).toHaveCount(0);
  await openMonth(page, "April");
  await expect(page.locator("#day-2026-04-09 .event-pill").filter({ hasText: "Masters Tournament" })).toHaveCount(1);
});

for (const categories of [["four_belt"], []]) {
  test(`legacy ${categories.length ? "narrow" : "empty"} boxing preferences include reviewed boxing and retire on save`, async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-10-24T17:00:00Z"));
    await page.addInitScript((boxing_categories) => {
      if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify({
        leagues: ["BOXING_MAJOR"],
        golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "full_tour" },
        motorsport_view: "full_weekend",
        boxing_categories,
      }));
    }, categories);
    await page.goto("/");
    const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
    await expect(chooser).toHaveCount(0);
    const boxing = page.locator("#day-2026-10-24 .event-pill");
    await expect(boxing).toHaveCount(1);
    await expect(boxing).toContainText("Navarrete");
    await page.getByRole("button", { name: "Interests · 1", exact: true }).click();
    await chooser.locator("details.advanced summary").click();
    await expect(chooser.getByRole("checkbox", { name: /Four-belt|Three-belt/ })).toHaveCount(0);
    await expect(chooser.locator("details.advanced").getByLabel("PGA Tour", { exact: true })).toHaveValue("majors_only");
    await expect(chooser.locator("details.advanced").getByLabel("Motorsport", { exact: true })).toHaveValue("full_weekend");
    await chooser.getByRole("button", { name: "Show my calendar" }).click();
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!));
    expect(saved).not.toHaveProperty("boxing_categories");
    expect(saved.leagues).toEqual(["BOXING_MAJOR"]);
    await page.reload();
    await expect(chooser).toHaveCount(0);
    await expect(boxing).toHaveCount(1);
    await expect(boxing).toContainText("Navarrete");
  });
}
