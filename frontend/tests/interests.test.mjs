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

test("climbing championships share one choice while cups and each published event family stay separate", async () => {
  const { interestGroups, interestChoices, toggleInterestGroup, leagueVisual } = await loadModule("calendar-helpers");
  const names = {
    IFSC_WORLD_CUP: "World Cups",
    IFSC_WORLDS: "World Championships",
    IFSC_YOUTH_WORLDS: "Youth World Championships",
    IFSC_PARA_WORLD_CUP: "Para World Cups",
    IFSC_PARA_WORLDS: "Para World Championships",
    CLIMBING_OLYMPIC_QUALIFIERS: "Olympic qualifiers",
    CLIMBING_CONTINENTAL_CUP: "Continental Cups",
    CLIMBING_YOUTH_CONTINENTAL_CUP: "Youth Continental Cups",
    CLIMBING_CHALLENGER: "Challenger",
    CLIMBING_NATIONS_GRAND_FINALE: "Nations Grand Finale",
    CLIMBING_ASIAN_GAMES: "Asian Games",
    CLIMBING_ASIAN_BEACH_GAMES: "Asian Beach Games",
    CLIMBING_EUROPEAN_GAMES: "European Games",
    CLIMBING_PAN_AM_GAMES: "Pan Am Games",
  };
  const continents = ["CLIMBING_EUROPE", "CLIMBING_ASIA", "CLIMBING_AFRICA", "CLIMBING_OCEANIA", "CLIMBING_PAN_AMERICA"];
  const published = [...Object.keys(names), ...continents];
  const groups = interestGroups(published.map((value) => ({ value })));
  assert.equal(groups.length, 1);
  assert.equal(groups[0].name, "Climbing");
  const choices = interestChoices(groups[0]);
  assert.deepEqual(choices.find((choice) => choice.name === "Continental championships"), {
    name: "Continental championships", leagues: continents,
  });
  assert.equal(choices.length, Object.keys(names).length + 1);
  for (const [league, name] of Object.entries(names))
    assert.deepEqual(choices.find((choice) => choice.name === name), { name, leagues: [league] });
  const saved = ["CLIMBING_ASIA", "WEIGHTLIFTING_EUROPE", "CLIMBING_CONTINENTAL_CUP"];
  const all = toggleInterestGroup(saved, continents);
  assert.deepEqual(all, [...saved, ...continents.filter((league) => league !== "CLIMBING_ASIA")]);
  assert.deepEqual(toggleInterestGroup(all, continents), ["WEIGHTLIFTING_EUROPE", "CLIMBING_CONTINENTAL_CUP"]);
  assert.deepEqual(interestChoices(interestGroups([{ value: "CLIMBING_EUROPE" }])[0]), [
    { name: "Continental championships", leagues: ["CLIMBING_EUROPE"] },
  ]);
  assert.equal(leagueVisual("CLIMBING_EUROPE").shortLabel, "European Championships");
  assert.equal(leagueVisual("IFSC_WORLDS").shortLabel, "World Championships");
  assert.deepEqual(interestChoices(interestGroups([{ value: "IFSC_YOUTH_WORLD_CHAMPIONSHIPS" }])[0]), [
    { name: "Youth World Championships", leagues: ["IFSC_YOUTH_WORLD_CHAMPIONSHIPS"] },
  ]);
});

test("new league IDs join their metadata's family, while unknown sports remain selectable", async () => {
  const { interestGroups, toggleInterestGroup } = await loadModule("calendar-helpers");
  const { interestLeagues } = await loadModule("interest-preferences");
  const choices = interestLeagues([
    { value: "NEW_SERIES", sport: "motorsport" }, { value: "NEW_TOUR", sport: "golf" },
    { value: "NEW_LEAGUE", sport: "soccer" }, { value: "UNRECOGNISED", sport: "other_sport" },
    { value: "GOLF_MAJORS_MEN", sport: "golf" }, { value: "PGA_TOUR" },
  ]);
  assert.deepEqual(interestGroups(choices), [
    { name: "Soccer", leagues: ["NEW_LEAGUE"] }, { name: "Motorsports", leagues: ["NEW_SERIES"] },
    { name: "Golf", leagues: ["PGA_TOUR", "NEW_TOUR"] }, { name: "Miscellaneous", leagues: ["UNRECOGNISED"] },
  ]);
  assert.equal(choices.find(({ value }) => value === "PGA_TOUR").sport, "golf");
  assert.deepEqual(toggleInterestGroup(["OLD_ID", "NEW_SERIES"], ["NEW_SERIES"]), ["OLD_ID"]);
});
