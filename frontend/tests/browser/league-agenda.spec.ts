import { expect, test } from "./test";
import { agendaToggle, event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";
const team = (role: string, name: string, short_name: string | null = null, record?: string, final_score?: number) => ({ name, short_name,
  participant_id: name, role, entity_type: "team", ...(["Jacksonville Jaguars", "Baltimore Ravens", "Seattle Seahawks", "New England Patriots"].includes(name) ? { logo_url: teamLogoUrl(`/i/teamlogos/nfl/500/${name.split(" ").at(-1)!.toLowerCase()}.png`), logo_source_url: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/1", logo_checked_date: "2026-11-03" } : {}), ...(record ? { record } : {}), ...(final_score != null ? { final_score } : {}) });
test.beforeEach(async ({ page }) => { await mockTeamLogos(page); });
const date = "2026-10-30";
const games = [
  event("Jaguars at Ravens", date, { league: "NFL", sport: "football", start_time_utc: `${date}T22:00:00Z`, week_label: "Week 9",
    participants: [team("away", "Jacksonville Jaguars", "Jaguars", "4-2"), team("home", "Baltimore Ravens", "Ravens", "4-3")] }),
  event("Untimed NFL", date, { league: "NFL", sport: "football", participants: [team("away", "Seattle Seahawks", "Seahawks"), team("home", "New England Patriots", "Patriots")] }),
  event("Hawks at Magic", date, { league: "NBA", sport: "basketball", status: "finished", participants: [team("away", "Atlanta Hawks", "Hawks", "3-3", 132), team("home", "Orlando Magic", "Magic", "3-3", 125)] }),
  event("NHL finished without scores", date, { league: "NHL", sport: "hockey", status: "finished", participants: [team("away", "Chicago Blackhawks", "Blackhawks"), team("home", "Boston Bruins", "Bruins")] }),
  event("Leeds at Forest", date, { league: "EPL", sport: "soccer", start_time_utc: `${date}T18:00:00Z`, round_or_stage: "Matchday 7", participants: [team("away", "Leeds United", "Leeds"), team("home", "Nottingham Forest")] }),
  event("Mexico Grand Prix", date, { league: "F1", sport: "motorsport", event_type: "race", start_time_utc: `${date}T19:00:00Z` }),
  event("World Cup · Gunsan · Boulder Qualification", date, { league: "IFSC_WORLD_CUP", sport: "climbing", round_or_stage: "qualification" }),
  event("Worlds · Men 73 kg", date, { league: "IWF_WORLDS", sport: "weightlifting", round_or_stage: "Group A" }),
  event("UFC Paris", date, { league: "UFC", sport: "combat" }),
];
for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`league agenda ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("league order, untimed first, source-backed team rows, centered sessions and NFL popup logos", async ({ page }) => {
      await setup(page, games, { now: `${date}T17:00:00Z` });
      await agendaToggle(page).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      await expect(agenda.locator(".agenda-league-heading")).toHaveText(["NFL", "NBA", "F1", "Premier League", "NHL", "UFC", "IWF Worlds", "World Cup"]);
      await expect(agenda.locator(".agenda-clock, .agenda-summary, .agenda-chevron")).toHaveCount(0);
      const nfl = agenda.getByRole("region", { name: "NFL", exact: true });
      await expect(nfl.locator(".agenda-team .team-name")).toHaveText(["Seahawks", "Patriots", "Jaguars", "Ravens"]);
      const row = nfl.locator(".agenda-row").last();
      await expect(row.locator(".team-record")).toHaveText(["4-2", "4-3"]);
      await expect(row.locator(".agenda-match-center")).toHaveText("Week 95:00 PM");
      await expect(nfl.locator(".team-logo")).toHaveCount(4);
      const nba = agenda.getByRole("region", { name: "NBA", exact: true });
      await expect(nba.locator(".agenda-match-center")).toHaveText("132–125Final");
      await expect(nba.locator("img")).toHaveCount(0);
      const nhl = agenda.getByRole("region", { name: "NHL", exact: true });
      await expect(nhl.locator(".agenda-match-center")).toBeEmpty();
      await expect(nhl.locator(".team-record, img")).toHaveCount(0);
      const soccer = agenda.getByRole("region", { name: "Premier League", exact: true });
      await expect(soccer.locator(".team-name")).toHaveText(["Leeds", "Nottingham Forest"]);
      await expect(soccer.locator(".team-record")).toHaveCount(0);
      await expect(agenda.getByRole("region", { name: "F1", exact: true })).toContainText("Mexico Grand Prix · Race");
      const climbing = agenda.getByRole("region", { name: "World Cup", exact: true });
      await expect(climbing.locator(".agenda-round, .agenda-time")).toHaveCount(0);
      await expect(agenda.getByRole("region", { name: "IWF Worlds", exact: true })).toContainText("Group A");
      await expect(agenda).not.toContainText(/TBD|record unavailable|past schedule/);
      await row.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `test-results/league-agenda-${width}-${colorScheme}.png` });
      await row.click();
      const popup = page.getByRole("dialog");
      await expect(popup.locator("h3")).toHaveText("Jacksonville Jaguars at Baltimore Ravens");
      await expect(popup.locator(".team-logo")).toHaveCount(2);
      for (const logo of await popup.locator(".team-logo").all()) await expect.poll(() => logo.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)).toBe(true);
      await page.screenshot({ path: `test-results/nfl-popup-${width}-${colorScheme}.png` });
      await page.keyboard.press("Escape");
      await expect(row.getByRole("button")).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}
