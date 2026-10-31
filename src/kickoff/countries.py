"""Venue countries explicitly named by the existing schedule sources."""

from __future__ import annotations

COUNTRY_LEAGUES = {
    "UFC",
    "PFL",
    "ONE",
    "RIZIN",
    "BOXING_MAJOR",
    "PGA_TOUR",
    "LPGA_TOUR",
    "UEFA_CHAMPIONS_LEAGUE",
    "UEFA_EUROPA_LEAGUE",
    "UEFA_CONFERENCE_LEAGUE",
    "UEFA_NATIONS_LEAGUE",
    "MLS",
}
ISO_CODES = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split()
)
# Source spellings, including explicitly named UK constituent countries.
COUNTRY_ALIASES = {
    "Puerto Rico": "PR",
    "Dominican Republic": "DO",
    "Bermuda": "BM",
    "USA": "US",
    "U.S.": "US",
    "United States": "US",
    "United States of America": "US",
    "England": "GB",
    "Scotland": "GB",
    "Wales": "GB",
    "Northern Ireland": "GB",
    "United Kingdom": "GB",
    "UK": "GB",
    "Spain": "ES",
    "Slovakia": "SK",
    "Germany": "DE",
    "Austria": "AT",
    "France": "FR",
    "Netherlands": "NL",
    "Norway": "NO",
    "Greece": "GR",
    "Italy": "IT",
    "Azerbaijan": "AZ",
    "Czechia": "CZ",
    "Czech Republic": "CZ",
    "Belgium": "BE",
    "Portugal": "PT",
    "Türkiye": "TR",
    "Turkey": "TR",
    "Hungary": "HU",
    "Kazakhstan": "KZ",
    "Denmark": "DK",
    "Cyprus": "CY",
    "Saudi Arabia": "SA",
    "Australia": "AU",
    "Mexico": "MX",
    "Canada": "CA",
    "United Arab Emirates": "AE",
    "China": "CN",
    "Brazil": "BR",
    "Qatar": "QA",
    "Macau": "MO",
    "Macao": "MO",
    "Serbia": "RS",
    "Japan": "JP",
    "Thailand": "TH",
    "Singapore": "SG",
    "South Africa": "ZA",
    "South Korea": "KR",
    "Republic of Korea": "KR",
    "Malaysia": "MY",
    "Taiwan": "TW",
    "Ireland": "IE",
    "Switzerland": "CH",
    "Sweden": "SE",
    "Finland": "FI",
    "Poland": "PL",
    "Indonesia": "ID",
    "Hong Kong": "HK",
    "Philippines": "PH",
    "Argentina": "AR",
    "Bahrain": "BH",
    "New Zealand": "NZ",
}
COUNTRIES = {name.casefold(): code for name, code in COUNTRY_ALIASES.items()}


def venue_country(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Venue country must be a source country name or ISO code")
    value = value.strip()
    if not value or value.casefold() in {"tbd", "tba", "unknown"}:
        return None
    code = value.upper() if value.upper() in ISO_CODES else COUNTRIES.get(value.casefold())
    return code or value
