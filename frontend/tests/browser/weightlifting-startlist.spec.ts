import { expect, test } from "./test";
import { event, setup } from "./fixtures";

const source = "https://ewf.sport/wp-content/uploads/2026/04/EWF_Batumi_2026_Start_Book_rev2_260412_090457_compressed.pdf";
const athletes = Array.from({ length: 12 }, (_, index) => ({ name: index === 11 ? "SourceAthleteWithAnUnusuallyLongUnbrokenOfficialName" : `Source Athlete ${String(index).padStart(2, "0")}`,
  participant_id: String(index), entity_type: "athlete", role: null, entry_total_kg: 150 + index,
  start_list_nation: index === 11 ? "AIN" : "GER", ...(index === 11 ? {} : { country_code: "DE" }),
  start_list_category: index % 2 ? "Women's 48 kg, Group B" : "Women's 53 kg, Group C",
  start_list_guest: index === 10, start_list_source_url: source, start_list_checked_date: "2026-11-03" }));

for (const width of [320, 375, 1280]) for (const colorScheme of ["light", "dark"] as const) test(`sourced top-ten popup at ${width}px ${colorScheme}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
  await setup(page, [event("Official session", undefined, { title: "European Championships · Women's 48 kg B / 53 kg C",
    league: "WEIGHTLIFTING_EUROPE", sport: "weightlifting", tags: ["Women", "session"], participants: athletes })]);
  await page.locator("#day-2026-10-28 .event-pill").click();
  const list = page.getByRole("region", { name: "Start list", exact: true });
  await expect(list.locator("li")).toHaveCount(10);
  await expect(list.locator(".start-list-total")).toHaveText(Array.from({ length: 10 }, (_, i) => `${161 - i} kg`));
  await expect(list).toContainText("and 2 more");
  await expect(list.locator("li").first()).toContainText("SourceAthleteWithAnUnusuallyLongUnbrokenOfficialName AIN");
  await expect(list.locator("li").first().getByRole("img")).toHaveCount(0);
  await expect(list.getByRole("img", { name: "Germany", exact: true })).toHaveCount(9);
  await expect(list).toContainText("Guest");
  await expect(list.locator(".start-list-category")).toHaveCount(10);
  await expect(list.getByRole("link", { name: "Start list source" })).toHaveAttribute("href", source);
  await expect(list).toContainText("Checked 2026-11-03");
  await expect(page.locator(".event-details h3")).toContainText("European Championships");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("sessions without a confirmed roster do not invent an athlete section", async ({ page }) => {
  await setup(page, [event("Unconfirmed session", undefined, { league: "IWF_WORLDS", sport: "weightlifting", tags: ["Women", "session"] })]);
  await page.locator("#day-2026-10-28 .event-pill").click();
  await expect(page.getByRole("region", { name: "Start list", exact: true })).toHaveCount(0);
});
