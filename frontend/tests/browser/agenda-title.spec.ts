import { expect, test } from "./test";
import { agendaToggle, event, setup } from "./fixtures";

const date = "2026-10-30";
const cases = [
  { league: "IWF_WORLDS", sport: "weightlifting", title: "IWF World Championships · Men's 75 kg, Group C", row: "Men's 75 kg, Group C" },
  { league: "NASCAR_CUP", sport: "motorsport", title: "NASCAR Cup Series at Martinsville", row: "Martinsville · Race", event_type: "race" },
  { league: "UFC", sport: "combat", title: "UFC 336: Van vs. Kape", row: "336: Van vs. Kape" },
  { league: "CLIMBING_EUROPE", sport: "climbing", title: "European Youth Championships · Augsburg · Men's U17 Lead Final", row: "Youth · Augsburg · Men's U17 Lead Final" },
  { league: "MASTERS_WORLDS", sport: "weightlifting", title: "World Masters Weightlifting Championships", row: "Naruto, Tokushima", city: "Naruto, Tokushima" },
  { league: "WEIGHTLIFTING_OCEANIA", sport: "weightlifting", title: "Oceania Championships / Universal Weightlifting Cup · Men's 60 kg", row: "Universal Weightlifting Cup · Men's 60 kg" },
  { league: "LPGA_TOUR", sport: "golf", title: "Blue Bay LPGA", row: "Blue Bay LPGA" },
  { league: "UFC", sport: "combat", title: "UFC", row: "", city: null, start_time_utc: `${date}T19:00:00Z` },
];

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`agenda event titles ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("rows omit competition identities and popups retain complete source titles", async ({ page }) => {
      await setup(page, cases.map((item, i) => event(`title-${i}`, date, { ...item, country: null, venue: null })), { now: `${date}T17:00:00Z` });
      await agendaToggle(page).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      for (const [i, item] of cases.entries()) {
        const row = page.locator(`[id="agenda-${date}-title-${i}"]`);
        await expect(row.locator(".agenda-title")).toHaveText(item.row);
        await row.getByRole("button").click();
        await expect(page.getByRole("dialog").locator("h3")).toHaveText(item.sport === "golf" ? `${item.title}, Round 1` : item.title);
        await page.keyboard.press("Escape");
      }
      await agenda.locator(".agenda-row").first().scrollIntoViewIfNeeded();
      await page.screenshot({ path: `test-results/agenda-titles-${width}-${colorScheme}.png` });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}
