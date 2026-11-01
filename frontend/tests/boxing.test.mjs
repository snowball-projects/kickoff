import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
import { reviewedBundle } from "./reviewed-fixture.mjs";
const { interestGroups, leagueVisual, compareEvents } = await loadModule("calendar-helpers");
const bundle = reviewedBundle();

test("every published Zuffa card joins combat interests and inherits the existing combat visual", () => {
  const cards = bundle.events.filter((event) => event.league === "ZUFFA_BOXING");
  assert.equal(cards.length, 14);
  assert(cards.every((event) => event.sport === "boxing" && event.start_time_utc === null));
  const combat = interestGroups([{ value: "ZUFFA_BOXING", sport: "boxing" }, { value: "BOXING_MAJOR", sport: "boxing" }]);
  assert.deepEqual(combat, [{ name: "Combat sports", leagues: ["BOXING_MAJOR", "ZUFFA_BOXING"] }]);
  assert.deepEqual(combat[0].leagues.map((league) => leagueVisual(league).shortLabel), ["Boxing", "Zuffa Boxing"]);
  assert.equal(leagueVisual("ZUFFA_BOXING", "boxing").className, "category-combat");
  assert(compareEvents({ ...cards[0], league: "BOXING_MAJOR" }, cards[0]) < 0);
});

test("published title bouts retain independent checked facts and both source licenses", () => {
  const bouts = bundle.events.filter((event) => event.league === "BOXING_MAJOR");
  assert(bouts.some((event) => event.title.includes("Muratalla") && event.title.includes("Cruz")));
  assert(bouts.some((event) => event.title.includes("Yamanaka") && event.title.includes("Ugawa")));
  assert(bouts.every((event) => event.start_time_utc === null && event.facts_checked_date === "2026-10-31"));
  assert(bouts.some((event) => event.source.startsWith("boxing_")));
  assert(bouts.some((event) => event.source === "wikipedia" && event.source_url.includes("oldid=")));
  assert.equal(bundle.data_licenses.boxing_ibf, "Schedule facts; no data license granted");
  assert.equal(bundle.data_licenses.wikipedia, "CC BY-SA 4.0");
});
