import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const requested = JSON.parse(await readFile(new URL("./fixtures/league-labels.json", import.meta.url)));

test("all 107 requested league labels and codes keep their sport identities", async () => {
  const { leagueVisual, categoryForLeague } = await loadModule("calendar-helpers");
  assert.equal(requested.length, 107);
  assert.equal(new Set(requested.map(({ id }) => id)).size, 107);
  for (const { id, sport, label, code } of requested) {
    assert.equal(leagueVisual(id).shortLabel, label, id);
    assert.equal(leagueVisual(id).code, code, id);
    assert.equal(categoryForLeague(id), sport, id);
  }
  for (const sport of new Set(requested.map((item) => item.sport))) {
    const labels = requested.filter((item) => item.sport === sport).map((item) => item.label);
    assert.equal(new Set(labels).size, labels.length, sport);
    const codes = requested.filter((item) => item.sport === sport).map((item) => item.code);
    assert.equal(new Set(codes).size, codes.length, sport);
  }
  // Codes identify a league within its sport, not globally.
  assert.equal(leagueVisual("FIFA_WORLD_CUP").code, leagueVisual("IFSC_WORLD_CUP").code);
  for (const [id, label] of [["CURRIE_CUP", "Currie Cup"], ["CLIMBING_AFRICA", "African Championships"],
    ["IFSC_YOUTH_WORLD_CHAMPIONSHIPS", "YOUTH"], ["FUTURE_LEAGUE", "FUTURE LEAGUE"]]) {
    assert.equal(leagueVisual(id).shortLabel, label);
    assert.equal(leagueVisual(id).code, undefined);
  }
});

test("renamed display labels retain source competition aliases and level facts", async () => {
  const { agendaEventTitle } = await loadModule("agenda-title");
  for (const [league, title] of [
    ["CHAMPIONSHIP", "EFL Championship"], ["COPA_SUDAMERICANA", "Copa Sudamericana"],
    ["COPA_LIBERTADORES", "Copa Libertadores"], ["NPC", "National Provincial Championship"],
    ["UNITED_RUGBY_CHAMPIONSHIP", "United Rugby Championship"], ["PREMIERSHIP_RUGBY", "Gallagher Prem"],
    ["SUPER_RUGBY_PACIFIC", "Super Rugby Pacific"], ["RUGBY_TESTS", "International tests"],
    ["BRITISH_IRISH_LIONS", "British and Irish Lions"], ["MAJOR_LEAGUE_RUGBY", "Major League Rugby"],
    ["RUGBY_CHAMPIONSHIP", "The Rugby Championship"], ["UCI_WORLD_TOUR", "UCI World Tour"],
    ["VUELTA_A_ESPANA", "Vuelta a España"], ["WORLD_ATHLETICS_CHAMPIONSHIPS", "World Athletics Championships"],
    ["IFSC_WORLD_CUP", "World Climbing"], ["IFSC_PARA_WORLD_CUP", "PARA"],
    ["IFSC_YOUTH_WORLDS", "Youth World Championships"], ["IFSC_PARA_WORLDS", "Para World Championships"],
    ["IFSC_WORLDS", "World Championships"], ["CLIMBING_PAN_AMERICA", "Pan-American Championships"],
    ["WEIGHTLIFTING_PAN_AMERICA", "Pan-American Championships"],
  ]) {
    const event = { league, title: `${title} · Women's Final` };
    assert.equal(agendaEventTitle(event), "Women's Final", league);
    assert.equal(event.title, `${title} · Women's Final`);
  }
});
