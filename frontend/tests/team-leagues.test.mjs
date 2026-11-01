import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { interestGroups, categoryForLeague, leagueVisual, compareEvents } = await loadModule("calendar-helpers");

const groups = {
  Soccer: ["UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS"],
  Football: ["COLLEGE_FOOTBALL"],
  Basketball: ["WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL"],
};
test("new ESPN leagues share their existing sport trays, icons and palette", () => {
  const available = Object.values(groups).flat().map(value => ({ value }));
  const actual = interestGroups(available);
  for (const [name, leagues] of Object.entries(groups)) {
    assert.deepEqual(actual.find(group => group.name === name).leagues, leagues);
    const category = name === "Soccer" ? "soccer" : name === "Football" ? "american-football" : "basketball";
    for (const league of leagues) {
      assert.equal(categoryForLeague(league), category);
      assert.equal(leagueVisual(league).className, `category-${category}`);
      assert.ok(!leagueVisual(league).shortLabel.includes("_"));
    }
  }
});

test("college tournaments, bowls and soccer knockouts precede regular professional games", () => {
  const event = (league, competition_phase) => ({ league, competition_phase, title: league,
    event_id: league, start_time_utc: null });
  for (const league of Object.values(groups).flat())
    assert.ok(compareEvents(event(league, "postseason"), event("NFL", "regular_season")) < 0);
});
