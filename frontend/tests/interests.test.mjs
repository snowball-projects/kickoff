import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("group selection preserves other interests and exposes unfamiliar published leagues", async () => {
  const { interestGroups, toggleInterestGroup, leagueVisual, SOCCER_COUNTRIES } = await loadModule("calendar-helpers");
  assert.deepEqual(interestGroups(["F1", "EPL", "IFSC_WORLD_CUP", "NEW_LEAGUE"].map((value) => ({ value }))), [
    { name: "Soccer", leagues: ["EPL"] },
    { name: "Motorsports", leagues: ["F1"] },
    { name: "Miscellaneous", leagues: ["IFSC_WORLD_CUP", "NEW_LEAGUE"] },
  ]);
  assert.deepEqual(toggleInterestGroup(["F1", "NFL", "OLD_SAVED_LEAGUE"], ["F1", "INDYCAR"]), ["F1", "NFL", "OLD_SAVED_LEAGUE", "INDYCAR"]);
  assert.deepEqual(toggleInterestGroup(["F1", "NFL", "INDYCAR"], ["F1", "INDYCAR"]), ["NFL"]);
  assert.equal(leagueVisual("CHAMPIONSHIP").shortLabel, "EFL Championship · England");
  assert.equal(SOCCER_COUNTRIES.CHAMPIONSHIP.name, "England");
  assert.equal(SOCCER_COUNTRIES.UEFA_CHAMPIONS_LEAGUE, undefined);
});
