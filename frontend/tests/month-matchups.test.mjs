import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { orderedTeams, monthMatchupName, desktopMonthGames } = await loadModule("month-matchups");
const { leagueGroups, pillGroups } = await loadModule("calendar-helpers");
const team = (name, role) => ({ name, role, entity_type: "team", logo_url: `https://example.test/${name}.png` });
const game = (id = "game", fields = {}) => ({ event_id: id, league: "NFL", sport: "football", title: "Original source title",
  competition_phase: "regular_season", start_time_utc: null, start_time_local: null, calendar_date: "2040-01-01",
  participants: [team("Home team", "home"), team("Away team", "away")], ...fields });

test("each team sport orders explicit roles while unassigned roles keep source order and full accessible names", () => {
  for (const [league, sport, names] of [["NFL", "football", ["Away team", "Home team"]],
    ["NBA", "basketball", ["Away team", "Home team"]], ["MLB", "baseball", ["Away team", "Home team"]],
    ["NHL", "hockey", ["Away team", "Home team"]], ["EPL", "soccer", ["Home team", "Away team"]],
    ["SIX_NATIONS", "rugby", ["Home team", "Away team"]], ["IPL", "cricket", ["Home team", "Away team"]]]) {
    const event = game("roles", { league, sport });
    assert.deepEqual(orderedTeams(event).map((team) => team.name), names);
    assert.equal(monthMatchupName(event), names.join(sport === "soccer" || sport === "rugby" || sport === "cricket" ? " vs " : " at "));
    assert.equal(event.title, "Original source title");
  }
  const unassigned = game("cricket", { league: "IPL", sport: "cricket", participants: [team("First source team", null), team("Second source team", null)] });
  assert.deepEqual(orderedTeams(unassigned).map((team) => team.name), ["First source team", "Second source team"]);
  assert.equal(monthMatchupName(unassigned), "Original source title; First source team; Second source team");
  assert.deepEqual(orderedTeams(game("golf", { league: "PGA_TOUR", sport: "golf" })), []);
  assert.equal(orderedTeams(game("home-only", { participants: [team("Home team", "home")] })).length, 1);
});

test("light days count every same-league game, and heavy days retain generic league labels", () => {
  for (const count of [1, 2, 3, 4]) {
    const items = Array.from({ length: count }, (_, index) => game(String(index), { league: "NBA", sport: "basketball" }));
    assert.deepEqual(desktopMonthGames(items, "2026-10-28", "America/Chicago"), count <= 3 ? items : []);
  }
  assert.deepEqual(desktopMonthGames([game("missing", { participants: [] })], "2026-10-28", "America/Chicago"), []);
});

test("NFL Sunday chooses only a unique last reliable kickoff on the viewer's cell date", () => {
  const early = game("early", { start_time_utc: "2026-11-01T18:00:00Z" });
  const late = game("late", { start_time_utc: "2026-11-02T01:00:00Z" });
  assert.deepEqual(desktopMonthGames([late, early], "2026-11-01", "America/Chicago"), [late]);
  const saturdayUtc = game("sat-utc", { start_time_utc: "2026-10-31T23:00:00Z" });
  const sundayUtc = game("sun-utc", { start_time_utc: "2026-11-01T02:00:00Z" });
  assert.deepEqual(desktopMonthGames([saturdayUtc, sundayUtc], "2026-11-01", "Asia/Tokyo"), [sundayUtc]);
  assert.deepEqual(desktopMonthGames([early, late, game("unknown")], "2026-11-01", "America/Chicago"), []);
  assert.deepEqual(desktopMonthGames([early, late, game("tie", { start_time_utc: late.start_time_utc })], "2026-11-01", "America/Chicago"), []);
  assert.deepEqual(desktopMonthGames([early, game("wall", { start_time_local: "2026-11-01T23:00:00" })], "2026-11-01", "America/Chicago"), []);
  assert.deepEqual(desktopMonthGames([early, late], "2026-11-01", "Asia/Tokyo"), []);
});

test("month league grouping joins golf without changing day tournament splitting or source titles", () => {
  const golf = [game("a", { league: "PGA_TOUR", sport: "golf", title: "Tournament A" }),
    game("b", { league: "PGA_TOUR", sport: "golf", title: "Tournament B" })];
  assert.equal(leagueGroups(golf).length, 1);
  assert.equal(pillGroups(golf).length, 2);
  assert.deepEqual(leagueGroups(golf)[0].items.map((event) => event.title), ["Tournament A", "Tournament B"]);
});
