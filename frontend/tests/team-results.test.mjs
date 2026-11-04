import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { orderedTeams, completedTeams, teamOutcome } = await loadModule("team-results");
const team = (name, role, fields = {}) => ({ name, role, entity_type: "team", ...fields });
const home = team("Home", "home"), away = team("Away", "away");

test("American sports use away/home and soccer, rugby, cricket use home/away without mutating participants", () => {
  const participants = [home, away];
  for (const sport of ["football", "basketball", "baseball", "hockey"]) assert.deepEqual(orderedTeams({ sport, participants }), [away, home]);
  for (const sport of ["soccer", "rugby", "cricket"]) assert.deepEqual(orderedTeams({ sport, participants }), [home, away]);
  assert.deepEqual(participants, [home, away]);
});
test("roleless and partial team fixtures preserve the actual source participants and individual sports stay excluded", () => {
  const participants = [team("First", null), team("Second", null)];
  assert.deepEqual(orderedTeams({ sport: "cricket", participants }), participants);
  assert.deepEqual(orderedTeams({ sport: "cricket", participants: [home] }), [home]);
  assert.deepEqual(orderedTeams({ sport: "tennis", participants }), []);
});
test("drawn or lost legs keep explicit advancement without a match-winner claim", () => {
  const a = team("First", "home", { final_score: 1, result_winner: true, result_advance: true, aggregate_score: 3, shootout_score: 2 });
  const b = team("Second", "away", { final_score: 1, result_winner: false, result_advance: false, aggregate_score: 3, shootout_score: 1 });
  assert.deepEqual(teamOutcome(a, b, "soccer"), { winner: false, advances: true });
  assert.deepEqual(teamOutcome(b, a, "soccer"), { winner: false, advances: false });
  assert.deepEqual(teamOutcome({ ...a, result_advance: false }, b, "soccer"), { winner: false, advances: false });
  assert.deepEqual(teamOutcome({ ...a, final_score: 0 }, b, "soccer"), { winner: false, advances: true });
});
test("a winning leg and advancement remain independent source facts", () => {
  const a = team("Wins and advances", "home", { final_score: 2, result_winner: true, result_advance: true });
  const b = team("Other", "away", { final_score: 1, result_winner: false });
  assert.deepEqual(teamOutcome(a, b, "soccer"), { winner: true, advances: true });
  assert.deepEqual(teamOutcome({ ...a, result_advance: false }, b, "soccer"), { winner: true, advances: false });
});
test("source final scores establish ordinary team winners when both flags are absent", () => {
  const a = team("Source higher score", "home", { final_score: 2 });
  const b = team("Source lower score", "away", { final_score: 0 });
  for (const sport of ["football", "basketball", "baseball", "hockey", "soccer", "rugby"]) {
    assert.deepEqual(teamOutcome(a, b, sport), { winner: true, advances: false });
    assert.deepEqual(teamOutcome(b, a, sport), { winner: false, advances: false });
    assert.deepEqual(teamOutcome(a, { ...b, final_score: 2 }, sport), { winner: false, advances: false });
  }
});
test("explicit false and ambiguous aggregate/shootout outcomes never become score-inferred winners", () => {
  const a = team("Higher", "home", { final_score: 2 });
  const b = team("Lower", "away", { final_score: 1 });
  for (const [first, second] of [[{ ...a, result_winner: false }, b], [a, { ...b, result_winner: false }],
    [{ ...a, aggregate_score: 4 }, b], [a, { ...b, shootout_score: 0 }]]) {
    assert.deepEqual(teamOutcome(first, second, "soccer"), { winner: false, advances: false });
  }
  assert.deepEqual(teamOutcome({ ...a, final_score: undefined, result_winner: true }, b, "soccer"), { winner: false, advances: false });
});
test("cricket still needs its explicit source winner and individual sports are not score-inferred", () => {
  const a = team("Higher", null, { final_score: 180 });
  const b = team("Lower", null, { final_score: 170 });
  assert.deepEqual(teamOutcome(a, b, "cricket"), { winner: false, advances: false });
  assert.deepEqual(teamOutcome({ ...a, result_winner: true }, b, "cricket"), { winner: true, advances: false });
  assert.deepEqual(teamOutcome(a, b, "tennis"), { winner: false, advances: false });
});
test("final scores retain zero, require completed status and two actual participants", () => {
  const event = { sport: "soccer", status: "finished", participants: [{ ...home, final_score: 0 }, { ...away, final_score: 0 }] };
  assert.deepEqual(completedTeams(event), event.participants);
  assert.deepEqual(completedTeams({ ...event, status: "scheduled" }), []);
  assert.deepEqual(completedTeams({ ...event, participants: [home, away] }), []);
  assert.deepEqual(completedTeams({ ...event, participants: [event.participants[0]] }), []);
});


test("paired aggregate facts distinguish a leg winner from the penalty qualifier", () => {
  const home = team("Source leg winner", "home", { final_score: 2, result_winner: false, result_advance: false, aggregate_score: 3, shootout_score: 1 });
  const away = team("Source qualifier", "away", { final_score: 1, result_winner: true, result_advance: true, aggregate_score: 3, shootout_score: 2 });
  assert.deepEqual(teamOutcome(home, away, "soccer"), { winner: true, advances: false });
  assert.deepEqual(teamOutcome(away, home, "soccer"), { winner: false, advances: true });
  assert.deepEqual(teamOutcome({ ...home, final_score: 1 }, away, "soccer"), { winner: false, advances: false });
});
