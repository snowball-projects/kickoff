import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { interestGroups, categoryForLeague, leagueVisual, SOCCER_COUNTRIES } = await loadModule("calendar-helpers");
const { espnLogoUrl } = await loadModule("team-logo");
const groups = {
  Soccer: ["FA_CUP", "LEAGUE_CUP", "LIGA_MX", "COPA_LIBERTADORES", "COPA_SUDAMERICANA", "NWSL", "WSL", "UEFA_WOMENS_CHAMPIONS_LEAGUE"],
  Basketball: ["G_LEAGUE", "NBL"],
  Football: ["UFL"],
};
test("the eleven usable requested leagues appear in their existing sport groups", () => {
  const available = Object.values(groups).flat().map(value => ({ value }));
  const actual = interestGroups(available);
  for (const [name, leagues] of Object.entries(groups)) {
    assert.deepEqual(new Set(actual.find(group => group.name === name).leagues), new Set(leagues));
    for (const league of leagues) {
      const category = name === "Football" ? "american-football" : name.toLowerCase();
      assert.equal(categoryForLeague(league), category);
      assert.equal(leagueVisual(league).className, `category-${category}`);
      assert.ok(!leagueVisual(league).shortLabel.includes("_"));
    }
  }
  assert.ok(!actual.some(group => group.leagues.includes("CFL")));
  assert.equal(SOCCER_COUNTRIES.LIGA_MX.name, "Mexico");
  for (const league of ["FA_CUP", "LEAGUE_CUP", "WSL"]) assert.equal(SOCCER_COUNTRIES[league].name, "England");
  for (const league of ["COPA_LIBERTADORES", "COPA_SUDAMERICANA", "UEFA_WOMENS_CHAMPIONS_LEAGUE"]) assert.equal(SOCCER_COUNTRIES[league], undefined);
});
test("supplied team images use exactly the reviewed ESPN CDN path", () => {
  const valid = "https://a.espncdn.com/i/teamlogos/soccer/500/390.png";
  assert.equal(espnLogoUrl(valid), valid);
  const historical = "https://a.espncdn.com/guid/6381f392-8ff3-3be9-af92-3beeaa1361ef/logos/default.png";
  assert.equal(espnLogoUrl(historical), historical);
  for (const value of [undefined, "https://evil.test/a.png", "https://a.espncdn.com.evil.test/i/teamlogos/a.png", `${valid}?tracking=1`]) assert.equal(espnLogoUrl(value), null);
});
