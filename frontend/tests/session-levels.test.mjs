import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const { sessionLevel, matchesInterestOptions, allPreferences, CLIMBING_LEVELS, WEIGHTLIFTING_LEVELS } = await loadModule("interest-preferences");
const session = (sport, league, tags = []) => ({ sport, league, tags });

test("climbing levels use each session's tags, with Para before Youth and Senior as the default", () => {
  for (const league of ["CLIMBING_EUROPE", "CLIMBING_ASIA", "IFSC_WORLD_CUP", "FUTURE_CLIMBING"]) {
    for (const tag of ["Youth", "U17", "U19", "U21"])
      assert.equal(sessionLevel(session("climbing", league, [tag])), "Youth");
    assert.equal(sessionLevel(session("climbing", league, ["Para", "Youth"])), "Para");
    assert.equal(sessionLevel(session("climbing", league, [])), "Senior");
  }
  for (const league of ["IFSC_PARA_WORLD_CUP", "IFSC_YOUTH_WORLDS", "CLIMBING_OLYMPIC_QUALIFIERS"])
    assert.equal(sessionLevel(session("climbing", league)), "Senior");
});

test("weightlifting levels use known leagues, while future leagues default to Senior unless tagged", () => {
  for (const [league, level] of [["IWF_YOUTH_WORLDS", "Youth"], ["IWF_JUNIOR_WORLDS", "Junior"], ["MASTERS_WORLDS", "Masters"],
    ["IWF_WORLDS", "Senior"], ["WEIGHTLIFTING_EUROPE", "Senior"], ["WEIGHTLIFTING_ASIA", "Senior"]])
    assert.equal(sessionLevel(session("weightlifting", league, ["Youth"])), level);
  assert.equal(sessionLevel(session("weightlifting", "FUTURE_LIFTING")), "Senior");
  for (const level of WEIGHTLIFTING_LEVELS)
    assert.equal(sessionLevel(session("weightlifting", "FUTURE_LIFTING", [level])), level);
  assert.equal(sessionLevel(session("soccer", "EPL")), null);
});

test("level, gender and discipline filters intersect without excluding unknown session facets", () => {
  for (const [sport, levels] of [["climbing", CLIMBING_LEVELS], ["weightlifting", WEIGHTLIFTING_LEVELS]]) {
    const league = sport === "climbing" ? "CLIMBING_EUROPE" : "FUTURE_LIFTING";
    const preferences = allPreferences([league]);
    assert.deepEqual(preferences[sport].levels, [...levels]);
    for (const level of levels) {
      const event = session(sport, league, [level]);
      const options = { ...preferences[sport], levels: [level], genders: ["Women"] };
      assert.equal(matchesInterestOptions(event, { [sport]: options }), true);
      assert.equal(matchesInterestOptions({ ...event, tags: [level, "Men"] }, { [sport]: options }), false);
      assert.equal(matchesInterestOptions(event, { [sport]: { ...options, levels: [] } }), false);
      assert.equal(matchesInterestOptions(event, { [sport]: { ...options, levels: levels.filter((item) => item !== level) } }), false);
    }
  }
  const event = session("climbing", "CLIMBING_EUROPE", ["Youth", "Men", "Women", "Lead", "Boulder"]);
  const options = { levels: ["Youth"], genders: ["Women"], disciplines: ["Boulder"] };
  assert.equal(matchesInterestOptions(event, { climbing: options }), true);
  assert.equal(matchesInterestOptions(event, { climbing: { ...options, disciplines: ["Speed"] } }), false);
});
