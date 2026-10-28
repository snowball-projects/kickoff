import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("group selection preserves other interests and exposes unfamiliar published leagues", async () => {
  const { interestGroups, toggleInterestGroup, leagueVisual, SOCCER_COUNTRIES } = await loadModule("calendar-helpers");
  assert.deepEqual(interestGroups(["F1", "EPL", "IFSC_WORLD_CUP", "NEW_LEAGUE"].map((value) => ({ value }))), [
    { name: "Soccer", leagues: ["EPL"] },
    { name: "Motorsports", leagues: ["F1"] },
    { name: "Climbing", leagues: ["IFSC_WORLD_CUP"] },
    { name: "Miscellaneous", leagues: ["NEW_LEAGUE"] },
  ]);
  assert.deepEqual(toggleInterestGroup(["F1", "NFL", "OLD_SAVED_LEAGUE"], ["F1", "INDYCAR"]), ["F1", "NFL", "OLD_SAVED_LEAGUE", "INDYCAR"]);
  assert.deepEqual(toggleInterestGroup(["F1", "NFL", "INDYCAR"], ["F1", "INDYCAR"]), ["NFL"]);
  assert.equal(leagueVisual("CHAMPIONSHIP").shortLabel, "EFL Championship · England");
  assert.equal(SOCCER_COUNTRIES.CHAMPIONSHIP.name, "England");
  assert.equal(SOCCER_COUNTRIES.UEFA_CHAMPIONS_LEAGUE, undefined);
});

test("published climbing and weightlifting types have separate categories and readable names", async () => {
  const { interestGroups, leagueVisual } = await loadModule("calendar-helpers");
  const competitions = ["IFSC_WORLD_CUP", "IWF_WORLDS", "IWF_JUNIOR_WORLDS", "IWF_YOUTH_WORLDS", "MASTERS_WORLDS",
    "WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_OCEANIA",
    "WEIGHTLIFTING_PAN_AMERICA", "WEIGHTLIFTING_COMMONWEALTH_GAMES", "WEIGHTLIFTING_ASIAN_GAMES", "WEIGHTLIFTING_PAN_AM_GAMES"];
  assert.deepEqual(interestGroups(competitions.map((value) => ({ value }))), [
    { name: "Climbing", leagues: ["IFSC_WORLD_CUP"] },
    { name: "Weightlifting", leagues: competitions.slice(1) },
  ]);
  assert.equal(leagueVisual("IWF_JUNIOR_WORLDS").shortLabel, "Junior Worlds");
  assert.equal(leagueVisual("MASTERS_WORLDS").shortLabel, "Masters Worlds");
});
