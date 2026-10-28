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

test("continental choices combine published IDs while toggles preserve saved subsets and other interests", async () => {
  const { interestChoices, toggleInterestGroup, leagueVisual } = await loadModule("calendar-helpers");
  const continents = ["WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_PAN_AMERICA"];
  const choices = interestChoices({ name: "Weightlifting", leagues: ["IWF_WORLDS", ...continents, "WEIGHTLIFTING_ASIAN_GAMES"] });
  assert.deepEqual(choices, [
    { name: "IWF Worlds", leagues: ["IWF_WORLDS"] },
    { name: "Continental championships", leagues: continents },
    { name: "Asian Games", leagues: ["WEIGHTLIFTING_ASIAN_GAMES"] },
  ]);
  const saved = ["WEIGHTLIFTING_EUROPE", "IFSC_WORLD_CUP", "OLD_SAVED_LEAGUE"];
  const all = toggleInterestGroup(saved, choices[1].leagues);
  assert.deepEqual(all, [...saved, "WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_PAN_AMERICA"]);
  assert.deepEqual(toggleInterestGroup(all, choices[1].leagues), ["IFSC_WORLD_CUP", "OLD_SAVED_LEAGUE"]);
  assert.equal(leagueVisual("WEIGHTLIFTING_EUROPE").shortLabel, "European Championships");
  assert.deepEqual(interestChoices({ name: "Weightlifting", leagues: ["WEIGHTLIFTING_EUROPE"] }), [
    { name: "Continental championships", leagues: ["WEIGHTLIFTING_EUROPE"] },
  ]);
  assert.deepEqual(interestChoices({ name: "Climbing", leagues: ["IFSC_WORLD_CUP"] }), [
    { name: "World Cups", leagues: ["IFSC_WORLD_CUP"] },
  ]);
});
