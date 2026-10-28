import { expect, test, type Page } from "@playwright/test";

async function openMonth(page: Page, month: string) {
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: `Open ${month} 2026` }).click();
  const calendar = page.getByRole("region", { name: "Scrollable calendar", exact: true });
  const section = calendar.getByRole("region", { name: `${month} 2026`, exact: true });
  // An absence assertion can pass while the old month is still scrolling.
  // Wait for the requested month before starting another year-view jump.
  await expect.poll(() => section.evaluate((element) => {
    const root = element.parentElement!;
    return Math.abs(root.scrollTop - (element as HTMLElement).offsetTop) < 2;
  })).toBe(true);
  await expect(page.getByRole("heading", { name: month, exact: true, level: 1 })).toBeVisible();
}

test("group choices are independent, mixed, collapsible and preserve saved leagues", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  await expect(chooser).toBeVisible();
  await expect(chooser.getByRole("heading", { name: "Interests", exact: true })).toBeVisible();
  await expect(page.getByText("Follow your sports", { exact: true })).toHaveCount(0);
  for (const name of ["Soccer", "Motorsports", "American football", "Combat sports", "Golf", "Climbing", "Weightlifting"])
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
  await chooser.locator("summary").filter({ hasText: /^Weightlifting$/ }).click();
  await chooser.getByRole("checkbox", { name: "IWF Worlds", exact: true }).check();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!).leagues)).toEqual(["F1", "NASCAR_CUP", "INDYCAR", "IWF_WORLDS"]);
  await page.reload();
  await expect(chooser).toHaveCount(0);
  await page.getByRole("button", { name: "Interests · 4", exact: true }).click();
  await expect(chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true })).toBeChecked();
  await expect(chooser.getByRole("checkbox", { name: "Select all Weightlifting", exact: true })).toHaveJSProperty("indeterminate", true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: "test-results/grouped-interests-mobile.png" });
});

test("in-group coverage checkboxes save together, cancel cleanly, and survive reopening on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  const golf = chooser.getByRole("region", { name: "Golf interests" });
  const motorsport = chooser.getByRole("region", { name: "Motorsports interests" });
  await expect(chooser.locator("details.advanced")).toHaveCount(0);
  await expect(chooser.getByRole("combobox")).toHaveCount(0);
  await expect(chooser.getByText("More filters", { exact: true })).toHaveCount(0);
  await chooser.locator("summary").filter({ hasText: /^Golf$/ }).click();
  await expect(chooser.getByRole("region", { name: "Golf interests" }).getByRole("checkbox")).toHaveCount(5);
  await chooser.getByRole("checkbox", { name: "Select all Golf", exact: true }).check();
  await chooser.locator("summary").filter({ hasText: /^Combat sports$/ }).click();
  await expect(chooser.getByRole("checkbox", { name: "One", exact: true })).toBeVisible();
  await chooser.getByRole("checkbox", { name: "Boxing", exact: true }).check();
  await motorsport.locator("summary").click();
  await expect(golf.getByRole("checkbox", { name: "PGA Tour", exact: true })).toBeChecked();
  await expect(golf.getByRole("checkbox", { name: "LPGA Tour", exact: true })).toBeChecked();
  await golf.getByRole("checkbox", { name: "PGA Tour majors only", exact: true }).check();
  await golf.getByRole("checkbox", { name: "LPGA Tour majors only", exact: true }).check();
  await page.screenshot({ path: "test-results/golf-options-mobile.png" });
  await motorsport.getByRole("checkbox", { name: "Races only", exact: true }).uncheck();
  expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/in-group-options-mobile.png" });
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  const saved = await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"));
  expect(JSON.parse(saved!)).toMatchObject({
    golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "majors_only" },
    motorsport_view: "full_weekend",
  });
  expect(JSON.parse(saved!)).not.toHaveProperty("boxing_categories");
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.getByRole("button", { name: "Show 2026 year calendar" })).toBeVisible();
  await openMonth(page, "January");
  await expect(page.locator("#day-2026-01-18 .event-pill").filter({ hasText: "Sony Open" })).toHaveCount(0);
  await openMonth(page, "April");
  await expect(page.locator("#day-2026-04-09 .event-pill").filter({ hasText: "Masters Tournament" })).toHaveCount(1);
  await page.getByRole("button", { name: "Interests · 3", exact: true }).click();
  await golf.locator("summary").click();
  await golf.getByRole("checkbox", { name: "PGA Tour majors only", exact: true }).uncheck();
  await chooser.getByRole("checkbox", { name: "Select all Golf", exact: true }).uncheck();
  await page.keyboard.press("Escape");
  await expect(chooser).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"))).toEqual(saved);
  await expect(page.getByRole("button", { name: "Interests · 3", exact: true })).toBeFocused();
  await page.getByRole("button", { name: "Interests · 3", exact: true }).click();
  await expect(chooser.getByRole("checkbox", { name: "Select all Golf", exact: true })).toBeChecked();
  await golf.locator("summary").click();
  await expect(golf.getByRole("checkbox", { name: "PGA Tour majors only", exact: true })).toBeChecked();
  await motorsport.locator("summary").click();
  await motorsport.getByRole("checkbox", { name: "Races only", exact: true }).check();
  await chooser.getByRole("button", { name: "Close", exact: true }).click();
  expect(await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"))).toEqual(saved);
  await page.reload();
  await page.getByRole("button", { name: "Interests · 3", exact: true }).click();
  await golf.locator("summary").click();
  await motorsport.locator("summary").click();
  await expect(motorsport.getByRole("checkbox", { name: "Races only", exact: true })).not.toBeChecked();
  await expect(golf.getByRole("checkbox", { name: "LPGA Tour majors only", exact: true })).toBeChecked();
});

for (const majorsOnly of [true, false]) for (const racesOnly of [true, false]) {
  test(`saved coverage stays exact: PGA majors ${majorsOnly}, LPGA majors ${!majorsOnly}, races ${racesOnly}`, async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
    const saved = {
      leagues: ["PGA_TOUR", "LPGA_TOUR", "F1", "OLD_SAVED_LEAGUE"],
      golf_views: { PGA_TOUR: majorsOnly ? "majors_only" : "full_tour", LPGA_TOUR: majorsOnly ? "full_tour" : "majors_only" },
      motorsport_view: racesOnly ? "race_only" : "full_weekend",
      climbing: { genders: ["Men"], disciplines: ["Boulder"] }, weightlifting: { genders: ["Women"] },
    };
    await page.addInitScript((saved) => {
      if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify(saved));
    }, saved);
    await page.goto("/");
    const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
    for (let visit = 0; visit < 2; visit++) {
      await page.getByRole("button", { name: "Interests · 4", exact: true }).click();
      await chooser.getByRole("region", { name: "Golf interests" }).locator("summary").click();
      await chooser.getByRole("region", { name: "Motorsports interests" }).locator("summary").click();
      await expect(chooser.getByRole("checkbox", { name: "PGA Tour majors only", exact: true })).toBeChecked({ checked: majorsOnly });
      await expect(chooser.getByRole("checkbox", { name: "LPGA Tour majors only", exact: true })).toBeChecked({ checked: !majorsOnly });
      await expect(chooser.getByRole("checkbox", { name: "Races only", exact: true })).toBeChecked({ checked: racesOnly });
      await chooser.getByRole("button", { name: "Show my calendar" }).click();
      expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!))).toEqual(saved);
      await page.reload();
    }
    await page.getByRole("button", { name: "Interests · 4", exact: true }).click();
    await chooser.getByRole("button", { name: "Select all", exact: true }).click();
    await chooser.getByRole("button", { name: "Show my calendar" }).click();
    const all = await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!));
    expect(all.leagues).toContain("OLD_SAVED_LEAGUE");
    expect(all.golf_views).toEqual(saved.golf_views);
    expect(all.motorsport_view).toEqual(saved.motorsport_view);
    await page.getByRole("button", { name: /^Interests ·/ }).click();
    await chooser.getByRole("button", { name: "Clear", exact: true }).click();
    await chooser.getByRole("button", { name: "Show my calendar" }).click();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!).leagues)).toEqual([]);
    await page.reload();
    await expect(page.getByRole("button", { name: "Interests · 0", exact: true })).toBeVisible();
    await expect(page.locator(".event-pill")).toHaveCount(0);
  });
}

test("saving checkbox choices preserves month position, year view and agenda period", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  const save = () => chooser.getByRole("button", { name: "Show my calendar" }).click();
  const edit = () => page.getByRole("button", { name: /^Interests/ }).click();
  await chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true }).check();
  await save();
  await openMonth(page, "April");
  const calendar = page.getByRole("region", { name: "Scrollable calendar", exact: true });
  const scrollTop = await calendar.evaluate((element) => element.scrollTop);
  await edit();
  await chooser.getByRole("region", { name: "Motorsports interests" }).locator("summary").click();
  await chooser.getByRole("checkbox", { name: "Races only", exact: true }).uncheck();
  await save();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("April");
  await expect.poll(() => calendar.evaluate((element) => element.scrollTop)).toBeCloseTo(scrollTop, 0);
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await edit();
  await save();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("2026");
  await expect(page.getByRole("button", { name: "Open April 2026" })).toBeVisible();
  await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Agenda", exact: true }).click();
  const upcoming = page.getByRole("button", { name: "Upcoming", exact: true });
  await upcoming.click();
  await edit();
  await save();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Agenda");
  await expect(upcoming).toHaveAttribute("aria-pressed", "true");
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
    await chooser.getByRole("region", { name: "Golf interests" }).locator("summary").click();
    await chooser.getByRole("region", { name: "Motorsports interests" }).locator("summary").click();
    await expect(chooser.getByRole("checkbox", { name: /Four-belt|Three-belt/ })).toHaveCount(0);
    await expect(chooser.getByRole("checkbox", { name: "PGA Tour majors only", exact: true })).toBeChecked();
    await expect(chooser.getByRole("checkbox", { name: "Races only", exact: true })).not.toBeChecked();
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
