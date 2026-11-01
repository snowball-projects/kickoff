import type { ApiParticipant, EventCard } from "./types";

// ISO 3166-1 alpha-2 codes. Names use the browser's built-in English region data;
// flags are native Unicode, so neither needs an asset or third-party request.
const ISO_CODES = "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split(" ");
export type Country = { code: string; name: string; flag: string };
const names = new Intl.DisplayNames(["en"], { type: "region" });
const normalize = (value: string) => value.trim().toLocaleLowerCase("en");
const countries = new Map(ISO_CODES.map((code) => [code, {
  code, name: names.of(code)!,
  flag: String.fromCodePoint(...[...code].map((letter) => 0x1f1e6 + letter.charCodeAt(0) - 65)),
}]));
const aliases = new Map([...countries.values()].map((country) => [normalize(country.name), country.code]));
// National subdivisions use explicit codes; country-name aliases remain ISO countries.
countries.set("GB-ENG", { code: "GB-ENG", name: "England", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" });
countries.set("GB-SCT", { code: "GB-SCT", name: "Scotland", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}" });
countries.set("GB-WLS", { code: "GB-WLS", name: "Wales", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}" });
// Northern Ireland has a national identity but no standard native emoji flag.
countries.set("GB-NIR", { code: "GB-NIR", name: "Northern Ireland", flag: "" });
// Unicode CLDR's explicit Kosovo territory code (not an ISO 3166-1 assignment).
countries.set("XK", { code: "XK", name: "Kosovo", flag: "🇽🇰" });
for (const [alias, code] of Object.entries({
  USA: "US", "United States of America": "US", UK: "GB", "Great Britain": "GB",
  "United Kingdom": "GB", Türkiye: "TR", Turkey: "TR", "Republic of Korea": "KR",
  "Korea, Republic of": "KR", "Czech Republic": "CZ",
})) aliases.set(normalize(alias), code);

export function countryIdentity(value: string | null | undefined): Country | undefined {
  if (!value) return undefined;
  const key = value.trim().toUpperCase();
  return countries.get(key) || countries.get(aliases.get(normalize(value)) || "");
}

export function hostCountry(event: Pick<EventCard, "country" | "source"> & Partial<Pick<EventCard, "country_source_url">>) {
  // openfootball supplies the league jurisdiction, not a verified venue country.
  return event.source === "openfootball" && !event.country_source_url ? undefined : countryIdentity(event.country);
}

export function commonHostCountry(events: Pick<EventCard, "country" | "source">[]) {
  const host = events.length ? hostCountry(events[0]) : undefined;
  return host && events.every((event) => hostCountry(event)?.code === host.code) ? host : undefined;
}

export function nationalTeamCountries(participants: ApiParticipant[]) {
  return participants.flatMap((participant) => {
    const country = participant.entity_type === "national_team" ? countryIdentity(participant.country_code) : undefined;
    return country?.flag ? [{ participant, country }] : [];
  });
}
