import { expect, test } from "./test";
import { chooser, event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";

for (const width of [320, 1280]) test(`remaining league choices and supplied identity ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const team = (name: string, role: string) => ({ name, role, participant_id: name, short_name: name,
    entity_type: "team", logo_url: teamLogoUrl(`/i/teamlogos/soccer/500/${name}.png`),
    logo_source_url: "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.nwsl/scoreboard?dates=2026", logo_checked_date: "2026-11-02" });
  const home = team("Home", "home"), away = team("Away", "away");
  const leagues = ["FA_CUP", "LEAGUE_CUP", "LIGA_MX", "COPA_LIBERTADORES", "COPA_SUDAMERICANA", "NWSL", "WSL", "UEFA_WOMENS_CHAMPIONS_LEAGUE"];
  const events = leagues.map(league => event(`${league} game`, undefined, { league,
    participants: [home, away] }));
  events.push(event("G League fixture", undefined, { league: "G_LEAGUE", sport: "basketball" }),
    event("NBL fixture", undefined, { league: "NBL", sport: "basketball" }),
    event("UFL fixture", undefined, { league: "UFL", sport: "football" }));
  await mockTeamLogos(page);
  const requests: string[] = [];
  await setup(page, events, { firstVisit: true, requests });
  expect(requests.every(file => file === "manifest.json")).toBe(true);
  const dialog = chooser(page);
  await dialog.getByRole("button", { name: "Soccer", exact: true }).click();
  const tray = dialog.getByRole("region", { name: "Soccer interests", exact: true });
  for (const name of ["England FA Cup", "England League Cup", "Mexico Liga MX", "Copa Libertadores", "Copa Sudamericana", "NWSL", "England WSL", "Women's Champions League"]) {
    await expect(tray.getByRole("button", { name, exact: true })).toBeVisible();
  }
  await dialog.getByRole("button", { name: "Show my calendar", exact: true }).click();
  await page.getByRole("switch", { name: "Agenda view" }).click();
  await expect(page.locator(".agenda-row")).toHaveCount(8);
  expect([...requests].sort()).toEqual(["manifest.json", ...leagues.map(league => `2026-soccer-${league.toLowerCase().replaceAll("_", "-")}.json`)].sort());
  const logo = page.locator(".agenda-row img").first();
  await expect(logo).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(logo).toHaveJSProperty("naturalWidth", 56);
  await page.locator(".agenda-row button").first().click();
  await expect(page.getByRole("dialog").locator("h3 img")).toHaveCount(2);
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
