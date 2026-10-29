import { expandDayGroups } from "./timeline-helpers";
import { expect, test, type Page } from "@playwright/test";

test.use({ timezoneId: "UTC" });

const chooser = (page: Page) => page.getByRole("dialog", { name: "Interests", exact: true });
const climbing = (page: Page) => chooser(page).getByRole("region", { name: "Climbing interests" });
const lifting = (page: Page) => chooser(page).getByRole("region", { name: "Weightlifting interests" });
async function edit(page: Page) {
  await page.getByRole("button", { name: /^Interests ·/ }).click();
  await climbing(page).locator("summary").click();
  await lifting(page).locator("summary").click();
}
async function save(page: Page) {
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
}
async function month(page: Page, name: string) {
  await page.getByRole("button", { name: "Show 2026 year calendar" }).click();
  await page.getByRole("button", { name: `Open ${name} 2026` }).click();
}

test("old selections retain senior-only Worlds; facets save, cancel and intersect in day and list views", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.setFixedTime(new Date("2026-10-24T17:00:00Z"));
  await page.addInitScript(() => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify({
      leagues: ["IFSC_WORLD_CUP", "IWF_WORLDS"],
      golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "full_tour" }, motorsport_view: "full_weekend",
    }));
  });
  await page.goto("/");
  await expect(chooser(page)).toHaveCount(0);
  await edit(page);
  await expect(climbing(page).getByRole("checkbox", { name: "World Cups", exact: true })).toBeChecked();
  await expect(lifting(page).getByRole("checkbox", { name: "IWF Worlds", exact: true })).toBeChecked();
  for (const name of ["Junior Worlds", "Youth Worlds", "Masters Worlds", "Continental championships", "Asian Games"])
    await expect(lifting(page).getByRole("checkbox", { name, exact: true })).not.toBeChecked();
  await expect(climbing(page).getByRole("group", { name: "Gender", exact: true }).getByRole("checkbox")).toHaveCount(2);
  await expect(climbing(page).getByRole("group", { name: "Discipline", exact: true }).getByRole("checkbox")).toHaveCount(3);
  await climbing(page).getByRole("checkbox", { name: "Men", exact: true }).uncheck();
  await climbing(page).getByRole("checkbox", { name: "Boulder", exact: true }).uncheck();
  await climbing(page).getByRole("checkbox", { name: "Speed", exact: true }).uncheck();
  await lifting(page).getByRole("checkbox", { name: "Men", exact: true }).uncheck();
  expect(await chooser(page).evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await save(page);
  const saved = await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"));
  expect(JSON.parse(saved!)).toMatchObject({ leagues: ["IFSC_WORLD_CUP", "IWF_WORLDS"],
    climbing: { genders: ["Women"], disciplines: ["Lead"] }, weightlifting: { genders: ["Women"] },
    golf_views: { PGA_TOUR: "majors_only" }, motorsport_view: "full_weekend" });
  await page.locator("#day-2026-10-25 .day-number").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expandDayGroups(page);
  await expect(detail.locator(".timeline-pill[data-event-id]")).toHaveCount(2);
  await expect(detail).toContainText("Women's Lead Semi-final");
  await expect(detail).toContainText("Women's Lead Final");
  await expect(detail).not.toContainText("Men's");
  await expect(detail).not.toContainText("Speed");
  await page.getByRole("button", { name: "Close day" }).click();
  await page.getByRole("button", { name: "Agenda", exact: true }).click();
  await page.getByRole("button", { name: "Upcoming", exact: true }).click();
  const list = page.getByRole("region", { name: "Agenda", exact: true });
  await expect(list).toContainText("Women's Lead Final");
  await expect(list).toContainText("Women's 49 kg");
  await expect(list).not.toContainText("Men's");
  await expect(list).not.toContainText("Speed");
  await edit(page);
  await lifting(page).getByRole("checkbox", { name: "Women", exact: true }).uncheck();
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => localStorage.getItem("kickoff.interests.v2"))).toEqual(saved);
  await page.reload();
  await edit(page);
  await expect(lifting(page).getByRole("checkbox", { name: "Women", exact: true })).toBeChecked();
  await lifting(page).getByRole("checkbox", { name: "Women", exact: true }).uncheck();
  await climbing(page).getByRole("checkbox", { name: "Women", exact: true }).uncheck();
  await save(page);
  await expect(list.locator(".agenda-row")).toHaveCount(0);
  await edit(page);
  await chooser(page).getByRole("button", { name: "Select all", exact: true }).click();
  for (const group of [climbing(page), lifting(page)]) {
    await expect(group.getByRole("checkbox", { name: "Men", exact: true })).toBeChecked();
    await expect(group.getByRole("checkbox", { name: "Women", exact: true })).toBeChecked();
  }
  await expect(climbing(page).getByRole("checkbox", { name: "Boulder", exact: true })).toBeChecked();
  await chooser(page).getByRole("button", { name: "Clear", exact: true }).click();
  await save(page);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!).leagues)).toEqual([]);
});

test("published climbing rounds replace spans while unknown gender stays visible", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-06-17T17:00:00Z"));
  await page.addInitScript(() => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify({
      leagues: ["IFSC_WORLD_CUP"], climbing: { genders: ["Women"], disciplines: ["Lead"] },
    }));
  });
  await page.goto("/");
  const innsbruck = page.locator("#day-2026-06-17 .event-pill");
  await expect(innsbruck).toHaveCount(0);
  await page.getByRole("button", { name: /^Interests ·/ }).click();
  await climbing(page).locator("summary").click();
  await climbing(page).getByRole("checkbox", { name: "Lead", exact: true }).uncheck();
  await climbing(page).getByRole("checkbox", { name: "Boulder", exact: true }).check();
  await save(page);
  await expect(innsbruck).toContainText("Innsbruck");
  await page.getByRole("button", { name: /^Interests ·/ }).click();
  await climbing(page).locator("summary").click();
  await climbing(page).getByRole("checkbox", { name: "Boulder", exact: true }).uncheck();
  await climbing(page).getByRole("checkbox", { name: "Speed", exact: true }).check();
  await save(page);
  await expect(innsbruck).toHaveCount(0);
  await month(page, "May");
  await expect(page.locator("#day-2026-05-08 .event-pill")).toHaveCount(0);
  await page.getByRole("button", { name: /^Interests ·/ }).click();
  await climbing(page).locator("summary").click();
  await climbing(page).getByRole("checkbox", { name: "Speed", exact: true }).uncheck();
  await climbing(page).getByRole("checkbox", { name: "Lead", exact: true }).check();
  await save(page);
  await expect(page.locator("#day-2026-05-08 .event-pill")).toContainText("Wujiang");
  await expect(page.locator("#day-2026-05-01 .event-pill")).toHaveCount(0);
});
