import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { countryIdentity, hostCountry, commonHostCountry, nationalTeamCountries } = await loadModule("countries");
const { SPORT_ICONS } = await loadModule("sport-icons");

const { CATEGORY_KEYS, categoryForLeague, pillCountries, SOCCER_COUNTRIES, leagueVisual } = await loadModule("calendar-helpers");

test("sport shapes cover the shared category keys and future series use family identity", () => {
  assert.equal(Object.keys(SPORT_ICONS).length, Object.keys(CATEGORY_KEYS).length);
  assert.equal(new Set(Object.values(SPORT_ICONS)).size, Object.keys(CATEGORY_KEYS).length);
  for (const category of Object.values(CATEGORY_KEYS)) assert.ok(SPORT_ICONS[category]);
  assert.ok(SPORT_ICONS[categoryForLeague("NEW_SERIES", "motorsport")]);
  assert.equal(categoryForLeague("NEW_BOXING", "boxing"), categoryForLeague("UFC", "mma"));
  assert.equal(categoryForLeague("NEW_HOCKEY", "ice_hockey"), "hockey");
  assert.equal(categoryForLeague("NFL", "football"), "american-football");
  assert.equal(categoryForLeague("UNKNOWN", "unknown"), null);
});

test("host flags resolve explicit ISO codes and existing reviewed country names", () => {
  for (const [value, code] of [["CN", "CN"], ["China", "CN"], ["Czechia", "CZ"], ["United States", "US"], ["USA", "US"], ["Türkiye", "TR"], ["Great Britain", "GB"], ["French Polynesia", "PF"], ["Croatia", "HR"], ["Rwanda", "RW"]])
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

test("World Cup national flags and verified host countries keep their identities", () => {
  assert.equal(countryIdentity("England"), undefined);
  assert.equal(countryIdentity("Scotland"), undefined);
  for (const [name, code, flag] of [
    ["Mexico", "MX", "🇲🇽"],
    ["England", "GB-ENG", "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}"],
    ["Scotland", "GB-SCT", "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}"],
  ]) {
    const identity = nationalTeamCountries([{ name, country_code: code, entity_type: "national_team" }])[0];
    assert.equal(identity.country.name, name);
    assert.equal(identity.country.flag, flag);
  }
  assert.equal(hostCountry({ source: "openfootball", country: "MX", country_source_url: "https://www.fifa.com/" })?.code, "MX");
  assert.equal(hostCountry({ source: "openfootball", country: "Mexico" }), undefined);
});

test("Wales and Kosovo have native national flags; Northern Ireland has identity without a substitute", () => {
  assert.equal(countryIdentity("GB-WLS").name, "Wales");
  assert.equal(countryIdentity("GB-WLS").flag, "\u{1F3F4}\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}");
  assert.deepEqual(countryIdentity("GB-NIR"), { code: "GB-NIR", name: "Northern Ireland", flag: "" });
  assert.equal(countryIdentity("XK").flag, "🇽🇰");
  assert.deepEqual(nationalTeamCountries([{ name: "Northern Ireland", country_code: "GB-NIR", entity_type: "national_team" }]), []);
  for (const country_code of ["ZZ", "GB-ABC", "Wales"])
    assert.deepEqual(nationalTeamCountries([{ name: "Wales", country_code, entity_type: "national_team" }]), []);
});


test("league jurisdictions are not presented as verified event hosts", () => {
  assert.equal(hostCountry({ source: "openfootball", country: "France" }), undefined);
  assert.equal(commonHostCountry([{ source: "openfootball", country: "Germany" }]), undefined);
  assert.equal(hostCountry({ source: "world_climbing", country: "Japan" })?.code, "JP");
  assert.equal(hostCountry({ source: "f1db", country: "MC" })?.code, "MC");
});


test("pills use league jurisdictions for domestic soccer and all-event hosts elsewhere", () => {
  for (const [league, country] of Object.entries(SOCCER_COUNTRIES))
    assert.equal(pillCountries([{ league, source: "openfootball", country: "US" }, { league, country: null }])[0].flag, country.flag);
  const event = { league: "UFC", country: "Japan" };
  assert.equal(pillCountries([event, { ...event, country: "JP" }])[0]?.code, "JP");
  for (const country of [null, "", "China", "Unknown"])
    assert.deepEqual(pillCountries([event, { ...event, country }]), []);
  for (const league of ["NBA", "NFL", "NHL", "MLB"])
    assert.deepEqual(pillCountries([{ league, country: "US" }]), []);
  assert.equal(leagueVisual("CHAMPIONSHIP").shortLabel, "Championship");
  assert.equal(leagueVisual("BRASILEIRAO").shortLabel, "Brasileirão");
});


test("pill flags separate league jurisdiction, traveling hosts and international competitions", () => {
  const event = { league: "EPL", source: "espn", country: "Spain" };
  assert.deepEqual(pillCountries([event]).map(c => c.code), ["GB-ENG", "ES"]);
  assert.deepEqual(pillCountries([{ ...event, country: "GB" }]).map(c => c.code), ["GB-ENG"]);
  assert.deepEqual(pillCountries([event, { ...event, country: null }]).map(c => c.code), ["GB-ENG"]);
  for (const league of ["UEFA_CHAMPIONS_LEAGUE", "UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE",
    "UEFA_NATIONS_LEAGUE", "UEFA_WOMENS_CHAMPIONS_LEAGUE", "COPA_LIBERTADORES", "COPA_SUDAMERICANA"])
    assert.deepEqual(pillCountries([{ ...event, league }]), []);
  for (const league of ["NFL", "NBA", "NHL", "MLB"]) {
    assert.deepEqual(pillCountries([{ ...event, league }]).map(c => c.code), ["ES"]);
    assert.deepEqual(pillCountries([{ ...event, league }, { ...event, league, country: "US" }]), []);
  }
  for (const league of ["UFC", "F1", "MOTOGP", "WEC", "INDYCAR", "PGA_TOUR", "ATP", "IWF_WORLDS"])
    assert.deepEqual(pillCountries([{ ...event, league, country: "US" }]).map(c => c.code), ["US"]);
  assert.deepEqual(pillCountries([]), []);
});


test("MLS, NWSL and UFL hide routine hosts and show only a shared known foreign host", () => {
  for (const league of ["MLS", "NWSL", "UFL"]) {
    const event = { league, source: "espn", country: "ES" };
    for (const country of ["US", "CA", null, "", "Unknown"])
      assert.deepEqual(pillCountries([{ ...event, country }]), []);
    assert.deepEqual(pillCountries([event, { ...event, country: "Spain" }]).map(c => c.code), ["ES"]);
    assert.deepEqual(pillCountries([{ ...event, country: "GB" }]).map(c => c.code), ["GB"]);
    for (const country of ["US", "CA", "JP", null, "Unknown"])
      assert.deepEqual(pillCountries([event, { ...event, country }]), []);
    assert.deepEqual(pillCountries([{ ...event, source: "openfootball", country: "Spain" }]), []);
  }
});
