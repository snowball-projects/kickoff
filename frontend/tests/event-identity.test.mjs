import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { countryIdentity, hostCountry, commonHostCountry, nationalTeamCountries } = await loadModule("countries");
const { SPORT_ICONS, sportIconKey } = await loadModule("sport-icons");

test("ten sport shapes cover every current category and share family icons", () => {
  assert.equal(Object.keys(SPORT_ICONS).length, 10);
  for (const category of ["Soccer", "Motorsports", "American football", "Basketball", "Baseball", "Hockey", "Combat sports", "Golf", "Climbing", "Weightlifting"])
    assert.ok(SPORT_ICONS[sportIconKey(category)]);
  assert.equal(sportIconKey("mma"), sportIconKey("boxing"));
  assert.equal(sportIconKey("combat_sports"), sportIconKey("Combat sports"));
  assert.equal(sportIconKey("unknown"), undefined);
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
