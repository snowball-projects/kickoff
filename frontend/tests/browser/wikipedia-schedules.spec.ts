import { expect, test } from "./test";
import { agendaToggle, chooser, event, setup } from "./fixtures";

const date = "2026-10-28";
const events = [
  event("motogp", date, { league: "MOTOGP", sport: "motorsport", event_type: "race", title: "Thailand motorcycle Grand Prix" }),
  event("prologue", date, { league: "WEC", sport: "motorsport", event_type: "practice", title: "Prologue" }),
  event("stage", date, { league: "TOUR_DE_FRANCE", sport: "cycling", event_type: "stage", title: "Tour de France · Stage 1 · Barcelona", round_or_stage: "Stage 1" }),
  event("meeting", date, { league: "DIAMOND_LEAGUE", sport: "athletics", title: "Weltklasse Zürich", end_calendar_date: "2026-10-29" }),
  event("cricket", date, { league: "IPL", sport: "cricket", event_type: "match", title: "IPL · Sunrisers Hyderabad vs Royal Challengers Bengaluru",
    start_time_utc: `${date}T14:00:00Z`, start_time_source: "wikipedia", start_time_source_url: "https://en.wikipedia.org/w/index.php?title=2026_Indian_Premier_League&oldid=1382256076" }),
];

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`Wikipedia sports ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("new sport trays, distinct icons, published prologue and sourced clocks remain usable", async ({ page }) => {
      await setup(page, events, { firstVisit: true });
      for (const name of ["Motorsports", "Cycling", "Athletics", "Cricket"]) {
        await chooser(page).getByRole("button", { name, exact: true }).click();
      }
      for (const sport of ["cycling", "athletics", "cricket"]) {
        await expect(chooser(page).locator(`.sport-icon[data-sport="${sport}"]`)).toHaveCount(1);
      }
      await page.screenshot({ path: `test-results/wikipedia-interests-${width}-${colorScheme}.png` });
      await chooser(page).getByRole("button", { name: "Show my calendar", exact: true }).click();
      // Month cells deliberately summarize crowded dates. Day view exposes all
      // selected families, including those behind the month's +N control.
      await page.locator(`#day-${date} .day-number`).click();
      const day = page.getByRole("region", { name: "Day events", exact: true });
      for (const sport of ["cycling", "athletics", "cricket"]) await expect(day.locator(`.event-pill.category-${sport}`).first()).toBeVisible();
      await day.locator(".event-pill.category-cricket").scrollIntoViewIfNeeded();
      await page.screenshot({ path: `test-results/wikipedia-day-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Back to October", exact: true }).click();
      await agendaToggle(page).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      await expect(agenda).toContainText("Prologue");
      await expect(agenda).toContainText("Stage 1");
      const cricket = page.locator(`[id="agenda-${date}-cricket"]`);
      await expect(cricket.locator(".agenda-time")).toHaveText("9:00 AM");
      await cricket.getByRole("button").click();
      await expect(page.getByRole("dialog").locator("h3")).toHaveText("IPL · Sunrisers Hyderabad vs Royal Challengers Bengaluru");
      await expect(page.getByRole("dialog").getByRole("link", { name: /Time source:/ })).toHaveAttribute("href", /oldid=1382256076/);
      await page.keyboard.press("Escape");
      await agenda.locator(".agenda-row").first().scrollIntoViewIfNeeded();
      await page.screenshot({ path: `test-results/wikipedia-agenda-${width}-${colorScheme}.png` });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}
