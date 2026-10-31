import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("group selection preserves other interests", async () => {
  const { interestGroups, toggleInterestGroup, leagueVisual, SOCCER_COUNTRIES } = await loadModule("calendar-helpers");
  assert.deepEqual(interestGroups(["F1", "EPL", "IFSC_WORLD_CUP"].map((value) => ({ value }))), [
    { name: "Soccer", leagues: ["EPL"] },
    { name: "Motorsports", leagues: ["F1"] },
    { name: "Climbing", leagues: ["IFSC_WORLD_CUP"] },
  ]);
  assert.deepEqual(toggleInterestGroup(["F1", "NFL", "OLD_SAVED_LEAGUE"], ["F1", "INDYCAR"]), ["F1", "NFL", "OLD_SAVED_LEAGUE", "INDYCAR"]);
  assert.deepEqual(toggleInterestGroup(["F1", "NFL", "INDYCAR"], ["F1", "INDYCAR"]), ["NFL"]);
  assert.equal(leagueVisual("CHAMPIONSHIP").shortLabel, "EFL Championship");
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

test("each climbing and weightlifting competition has its own league pill", async () => {
  const { interestChoices } = await loadModule("calendar-helpers");
  for (const [name, leagues, labels] of [
    ["Climbing", ["IFSC_WORLD_CUP", "CLIMBING_EUROPE", "CLIMBING_ASIA"], ["World Cups", "European Championships", "Asian Championships"]],
    ["Weightlifting", ["IWF_WORLDS", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_ASIA"], ["IWF Worlds", "European Championships", "Asian Championships"]],
  ]) assert.deepEqual(interestChoices({ name, leagues }), leagues.map((league, i) => ({ name: labels[i], leagues: [league] })));
});

test("published league metadata joins the ten sports; golf remains the two ESPN tours", async () => {
  const { interestGroups, toggleInterestGroup } = await loadModule("calendar-helpers");
  const choices = [
    { value: "NEW_SERIES", sport: "motorsport" }, { value: "NEW_TOUR", sport: "golf" },
    { value: "NEW_LEAGUE", sport: "soccer" }, { value: "UNRECOGNISED", sport: "other_sport" },
    { value: "PGA_TOUR", sport: "golf" },
  ];
  assert.deepEqual(interestGroups(choices), [
    { name: "Soccer", leagues: ["NEW_LEAGUE"] }, { name: "Motorsports", leagues: ["NEW_SERIES"] },
    { name: "Golf", leagues: ["PGA_TOUR"] },
  ]);
  assert.equal(choices.find(({ value }) => value === "PGA_TOUR").sport, "golf");
  assert.deepEqual(toggleInterestGroup(["OLD_ID", "NEW_SERIES"], ["NEW_SERIES"]), ["OLD_ID"]);
});
