import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { compareEvents, leagueGroups } = await loadModule("calendar-helpers");
const event = (league, fields = {}) => ({ league, title: league, event_id: league, competition_phase: "regular_season", start_time_utc: null, ...fields });

test("one ranking follows all eight tiers and their internal order", () => {
  const leagues = ["FIFA_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE",
    "NFL", "NBA", "F1", "EPL", "MLB", "NHL", "UFC", "BOXING_MAJOR", "LA_LIGA", "BUNDESLIGA", "SERIE_A", "LIGUE_1",
    "NASCAR_CUP", "INDYCAR", "IWF_WORLDS", "IFSC_WORLD_CUP", "PGA_TOUR", "LPGA_TOUR", "CHAMPIONSHIP", "EREDIVISIE", "PRIMEIRA_LIGA", "BRASILEIRAO",
    "PFL", "RIZIN", "ONE", "IFSC_PARA_WORLD_CUP", "IFSC_YOUTH_WORLD_CHAMPIONSHIPS", "IWF_JUNIOR_WORLDS", "IWF_YOUTH_WORLDS", "MASTERS_WORLDS",
    "WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_OCEANIA", "WEIGHTLIFTING_PAN_AMERICA",
    "WEIGHTLIFTING_COMMONWEALTH_GAMES", "WEIGHTLIFTING_ASIAN_GAMES", "WEIGHTLIFTING_PAN_AM_GAMES"];
  assert.deepEqual(leagues.toReversed().map((league) => event(league)).sort(compareEvents).map((e) => e.league), leagues);
});
test("finals and playoffs precede regular play; tier order beats time and titles", () => {
  const items = [event("FIFA_WORLD_CUP"), event("NFL", { competition_phase: "postseason" }),
    event("NBA", { competition_phase: "final" }), event("ONE", { competition_phase: "championship" }), event("EPL", { competition_phase: "group_stage" })];
  assert.deepEqual(items.sort(compareEvents).map((e) => e.league), ["NFL", "NBA", "ONE", "FIFA_WORLD_CUP", "EPL"]);
  const major = event("PGA_TOUR", { title: "Masters Tournament", competition_phase: "championship" });
  assert(compareEvents(major, event("NFL")) < 0);
});
test("league groups contain each event once and rank by their highest-priority event", () => {
  const items = [event("NFL"), event("ONE"), event("ONE", { event_id: "final", competition_phase: "final" })];
  assert.deepEqual(leagueGroups(items).map((g) => [g.league, g.items.length]), [["ONE", 2], ["NFL", 1]]);
});

test("current PGA majors and women's major records stay in their respective first-tier positions", () => {
  const men = event("PGA_TOUR", { title: "Masters Tournament", competition_phase: "championship" });
  const women = event("LPGA_TOUR", { title: "The Chevron Championship", competition_phase: "championship" });
  const regularWomen = event("LPGA_TOUR", { title: "Regular LPGA stop" });
  assert.deepEqual([regularWomen, event("UEFA_CHAMPIONS_LEAGUE"), women, event("NFL"), men]
    .sort(compareEvents).map((e) => e.league),
  ["PGA_TOUR", "LPGA_TOUR", "UEFA_CHAMPIONS_LEAGUE", "NFL", "LPGA_TOUR"]);
});

test("normalized UCL knockout, NFL postseason and final/championship phases outrank regular play", () => {
  const regular = event("FIFA_WORLD_CUP", { competition_phase: "group_stage" });
  const postseason = [event("UEFA_CHAMPIONS_LEAGUE", { competition_phase: "knockout" }),
    event("NFL", { competition_phase: "postseason" }), event("NBA", { competition_phase: "final" }),
    event("ONE", { competition_phase: "championship" })];
  assert.deepEqual([regular, ...postseason.toReversed()].sort(compareEvents), [...postseason, regular]);
});
