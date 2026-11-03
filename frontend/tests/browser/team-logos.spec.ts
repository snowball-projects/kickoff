import { expect, test } from "./test";
import { agendaToggle, event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";

const leaguesBySport = {
  football: ["NFL", "COLLEGE_FOOTBALL", "UFL"],
  basketball: ["NBA", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL", "G_LEAGUE", "NBL"],
  baseball: ["MLB"], hockey: ["NHL"],
  soccer: ["EPL", "CHAMPIONSHIP", "BUNDESLIGA", "LA_LIGA", "SERIE_A", "LIGUE_1", "EREDIVISIE", "PRIMEIRA_LIGA", "BRASILEIRAO", "FA_CUP", "LEAGUE_CUP", "LIGA_MX", "WSL", "FIFA_WORLD_CUP", "FIFA_WOMENS_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE", "UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS", "COPA_LIBERTADORES", "COPA_SUDAMERICANA", "NWSL", "UEFA_WOMENS_CHAMPIONS_LEAGUE"],
  rugby: ["RUGBY_WORLD_CUP", "WOMENS_RUGBY_WORLD_CUP", "SIX_NATIONS", "RUGBY_CHAMPIONSHIP", "NATIONS_CHAMPIONSHIP", "RUGBY_CHAMPIONS_CUP", "RUGBY_CHALLENGE_CUP", "PREMIERSHIP_RUGBY", "UNITED_RUGBY_CHAMPIONSHIP", "TOP_14", "SUPER_RUGBY_PACIFIC", "CURRIE_CUP", "NPC", "URBA_TOP_14", "MAJOR_LEAGUE_RUGBY", "BRITISH_IRISH_LIONS", "RUGBY_TESTS"],
};
const team = (league: string, role: string) => ({ name: `${league} ${role}`, participant_id: role, short_name: role,
  role, entity_type: "team", logo_url: teamLogoUrl(`/i/teamlogos/fixture/500/${league}-${role}.png`),
  logo_source_url: "https://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.1/seasons/2026/teams/1", logo_checked_date: "2026-11-03" });

test.use({ reducedMotion: "reduce" });

for (const [sport, leagues] of Object.entries(leaguesBySport)) test(`one team-image contract across ${sport} leagues`, async ({ page }) => {
  const requests: { url: string; referrer?: string }[] = [];
  page.on("request", request => {
    if (request.url().startsWith("https://a.espncdn.com/")) requests.push({ url: request.url(), referrer: request.headers().referer });
  });
  await mockTeamLogos(page);
  await setup(page, leagues.map(league => event(`${league} match`, undefined, { league, sport,
    participants: [team(league, "home"), team(league, "away")] })));
  await agendaToggle(page).click();
  for (const league of leagues) {
    const row = page.locator(`[id="agenda-2026-10-28-${league} match"]`);
    await row.scrollIntoViewIfNeeded();
    await expect(row.locator(".team-logo")).toHaveCount(2);
    for (const image of await row.locator(".team-logo").all()) {
      await expect(image).toHaveAttribute("loading", "lazy");
      await expect(image).toHaveAttribute("referrerpolicy", "no-referrer");
      await expect(image).toHaveAttribute("width", "28");
      await expect(image).toHaveJSProperty("naturalWidth", 56);
    }
    await row.getByRole("button").click();
    await expect(page.locator(".event-details h3 .team-logo")).toHaveCount(2);
    await page.keyboard.press("Escape");
  }
  expect(requests.length).toBeGreaterThan(0);
  for (const request of requests) {
    const url = new URL(request.url);
    expect(url.pathname).toBe("/combiner/i");
    expect(url.searchParams.get("w")).toBe("56");
    expect(url.searchParams.get("h")).toBe("56");
    expect(request.referrer).toBeUndefined();
  }
});

test("missing and failed team images preserve text in agenda, popup and NFL month matchups", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.route("https://a.espncdn.com/**", route => route.fulfill({ status: 404, body: "no image" }));
  const away = { ...team("NFL", "away"), name: "Kansas City Chiefs", short_name: "Chiefs" };
  const home = { ...team("NFL", "home"), name: "Buffalo Bills", short_name: "Bills" };
  const unmatched = { name: "Unmatched club", role: "home", entity_type: "team" };
  await setup(page, [event("Chiefs at Bills", undefined, { league: "NFL", sport: "football", participants: [away, home] }),
    event("Unmatched source appointment", undefined, { league: "NBL", sport: "basketball", participants: [unmatched] }),
    event("Named individual", undefined, { league: "ATP", sport: "tennis", participants: [{ name: "Named individual", role: null, entity_type: "athlete" }] })]);
  const month = page.locator("#day-2026-10-28 .category-american-football");
  await expect(month.locator(".nfl-month-matchups > .nfl-matchup .nfl-team-name")).toHaveText(["Chiefs", "Bills"]);
  for (const text of await month.locator(".nfl-month-matchups > .nfl-matchup .nfl-team-name").all()) await expect(text).toBeVisible();
  await expect(month).toHaveAccessibleName(/Kansas City Chiefs at Buffalo Bills/);
  await agendaToggle(page).click();
  const nfl = page.locator('[id="agenda-2026-10-28-Chiefs at Bills"]');
  await expect(nfl.locator(".team-name")).toHaveText(["Chiefs", "Bills"]);
  for (const image of await nfl.locator(".team-logo").all()) await expect(image).toBeHidden();
  const unknown = page.locator('[id="agenda-2026-10-28-Unmatched source appointment"]');
  await expect(unknown).toContainText("Unmatched club");
  await expect(unknown.locator("img")).toHaveCount(0);
  const individual = page.locator('[id="agenda-2026-10-28-Named individual"]');
  await expect(individual).toContainText("Named individual");
  await expect(individual.locator("img")).toHaveCount(0);
  await nfl.getByRole("button").click();
  await expect(page.locator(".event-details h3")).toHaveText("Kansas City Chiefs at Buffalo Bills");
});

test("native lazy images do not download far-offscreen logos before scrolling", async ({ page }) => {
  const requested: string[] = [];
  await mockTeamLogos(page);
  page.on("request", request => { if (request.url().startsWith("https://a.espncdn.com/")) requested.push(request.url()); });
  const spacer = Array.from({ length: 100 }, (_, index) => event(`Session ${index}`, undefined, { league: "NFL", sport: "football", round_or_stage: `Source slot ${index}` }));
  await setup(page, [...spacer, event("Far team game", undefined, { league: "NBL", sport: "basketball", participants: [team("far", "home"), team("far", "away")] })]);
  await agendaToggle(page).click();
  const far = page.locator('[id="agenda-2026-10-28-Far team game"]');
  await expect(far.locator(".team-logo")).toHaveCount(2);
  expect(await far.evaluate(element => element.getBoundingClientRect().top)).toBeGreaterThan(6000);
  expect(requested).toEqual([]);
  await far.scrollIntoViewIfNeeded();
  for (const image of await far.locator(".team-logo").all()) await expect(image).toHaveJSProperty("naturalWidth", 56);
  expect(requested).toHaveLength(2);
});

test("source images do not turn clubs into national teams", async ({ page }) => {
  await mockTeamLogos(page);
  const national = { ...team("national", "away"), name: "Australia", entity_type: "national_team", country_code: "AU",
    country_source_url: "https://www.world.rugby/organisation/membership/", country_checked_date: "2026-11-03" };
  const club = { ...team("club", "home"), name: "Source club", entity_type: "team", logo_url: national.logo_url };
  await setup(page, [event("Australia at Source club", undefined, { league: "RUGBY_TESTS", sport: "rugby", country: null, participants: [national, club] })]);
  await agendaToggle(page).click();
  await page.locator(".agenda-row button").click();
  const heading = page.locator(".event-details h3");
  await expect(heading.locator(".team-logo")).toHaveCount(2);
  await expect(heading.locator(".event-flags .country-flag")).toHaveCount(1);
  await expect(heading.getByRole("img", { name: "Australia: Australia", exact: true })).toHaveCount(1);
});

test("logos just below the visible scroll area have no source until they intersect", async ({ page }) => {
  const requested: string[] = [];
  await mockTeamLogos(page);
  page.on("request", request => { if (request.url().startsWith("https://a.espncdn.com/")) requested.push(request.url()); });
  const spacer = Array.from({ length: 100 }, (_, index) => event(`Nearby session ${index}`, undefined, { league: "NFL", sport: "football", round_or_stage: `Source slot ${index}` }));
  await setup(page, [...spacer, event("Nearby team game", undefined, { league: "NBL", sport: "basketball", participants: [team("near", "home"), team("near", "away")] })]);
  await agendaToggle(page).click();
  const images = page.locator('[id="agenda-2026-10-28-Nearby team game"] .team-logo');
  await images.first().evaluate(element => {
    const scroller = document.getElementById("agenda-scroll")!;
    const bottom = Math.min(innerHeight, scroller.getBoundingClientRect().bottom);
    scroller.scrollTop += element.getBoundingClientRect().top - bottom - 2;
  });
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  expect(await images.first().evaluate(element => element.getBoundingClientRect().top - Math.min(innerHeight, document.getElementById("agenda-scroll")!.getBoundingClientRect().bottom))).toBeGreaterThan(0);
  for (const image of await images.all()) await expect(image).not.toHaveAttribute("src");
  expect(requested).toEqual([]);
  await page.locator("#agenda-scroll").evaluate(element => { element.scrollTop += 64; });
  for (const image of await images.all()) await expect(image).toHaveJSProperty("naturalWidth", 56);
  expect(requested).toHaveLength(2);
});

test("hidden NFL measurement images do not fetch extra teams", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 1000 });
  const requested: string[] = [];
  await mockTeamLogos(page);
  page.on("request", request => { if (request.url().startsWith("https://a.espncdn.com/")) requested.push(request.url()); });
  const games = ["first", "second", "third"].map((id, index) => event(id, undefined, { league: "NFL", sport: "football",
    participants: [team(id, "home"), team(id, "away")], start_time_utc: `2026-10-28T${17 + index}:00:00Z` }));
  await setup(page, games);
  const pill = page.locator("#day-2026-10-28 .event-pill");
  await expect(pill.locator(".nfl-month-matchups > .nfl-matchup")).toHaveCount(1);
  for (const image of await pill.locator(".nfl-month-matchups > .nfl-matchup .team-logo").all()) await expect(image).toHaveJSProperty("naturalWidth", 56);
  for (const image of await pill.locator(".nfl-measurements .team-logo").all()) await expect(image).not.toHaveAttribute("src");
  expect(requested).toHaveLength(2);
  expect(requested.every(url => new URL(url).searchParams.get("img")!.includes("first-"))).toBe(true);
});
