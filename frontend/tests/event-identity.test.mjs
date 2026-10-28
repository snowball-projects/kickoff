import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { countryIdentity, hostCountry, commonHostCountry, nationalTeamCountries } = await loadModule("countries");
const { SPORT_ICONS } = await loadModule("sport-icons");

const { CATEGORY_KEYS, categoryForLeague } = await loadModule("calendar-helpers");

test("ten sport shapes cover the shared category keys and future series use family identity", () => {
  assert.equal(Object.keys(SPORT_ICONS).length, 10);
  for (const category of Object.values(CATEGORY_KEYS)) assert.ok(SPORT_ICONS[category]);
  assert.ok(SPORT_ICONS[categoryForLeague("NEW_SERIES", "motorsport")]);
  assert.equal(categoryForLeague("NEW_BOXING", "boxing"), categoryForLeague("UFC", "mma"));
  assert.equal(categoryForLeague("NEW_HOCKEY", "ice_hockey"), "hockey");
  assert.equal(categoryForLeague("NFL", "football"), "american-football");
  assert.equal(categoryForLeague("UNKNOWN", "unknown"), null);
});

test("host flags resolve explicit ISO codes and existing reviewed country names", () => {
  for (const [value, code] of [["CN", "CN"], ["China", "CN"], ["Czechia", "CZ"], ["United States", "US"], ["USA", "US"], ["Türkiye", "TR"], ["Great Britain", "GB"], ["French Polynesia", "PF"]])
    assert.equal(countryIdentity(value)?.code, code);
  assert.equal(hostCountry({ country: "MC" })?.flag, "🇲🇨");
  for (const country of [null, "", "Unknown", "Neutral", "Europe", "US/Canada", "USA, Mexico and Canada", "ZZ", "XX"])
    assert.equal(hostCountry({ country }), undefined);
  assert.equal(hostCountry({ country: null, title: "Japanese Grand Prix", league: "NFL", venue: "London" }), undefined);
});

test("a competition group gets a host flag only when every event shares it", () => {
  assert.equal(commonHostCountry([{ country: "Japan" }, { country: "JP" }])?.code, "JP");
  for (const events of [[], [{ country: "Japan" }, { country: null }], [{ country: "Japan" }, { country: "China" }]])
    assert.equal(commonHostCountry(events), undefined);
});

test("only explicit national-team identities get participant flags", () => {
  const team = { name: "Japan", entity_type: "national_team", country_code: "JP" };
  assert.equal(nationalTeamCountries([team])[0].country.code, "JP");
  for (const participant of [{ ...team, entity_type: "team" }, { ...team, entity_type: "club" }, { ...team, country_code: null }, { name: "Japan", entity_type: "national_team" }])
    assert.deepEqual(nationalTeamCountries([participant]), []);
});
