import { commonHostCountry, countryIdentity, type Country } from "./countries";
import { eventInstant } from "./date-utils";
import type { EventCard } from "./types";
import { WEIGHTLIFTING_LEAGUE_LEVELS, type LeagueInterest } from "./interest-preferences";
import { isGolf } from "./golf";

const LEAGUE_META: Record<
  string,
  { shortLabel: string; code?: string; titleNames?: string[] }
> = {
  MOTOGP: { shortLabel: "MotoGP", code: "MGP" },
  WEC: { shortLabel: "WEC", code: "WEC" },
  TOUR_DE_FRANCE: { shortLabel: "Tour de France", code: "TDF" },
  GIRO_D_ITALIA: { shortLabel: "Giro d'Italia", code: "GIRO" },
  VUELTA_A_ESPANA: { shortLabel: "Vuelta", code: "VUEL", titleNames: ["Vuelta a España"] },
  UCI_WORLD_TOUR: { shortLabel: "WorldTour", code: "UWT", titleNames: ["UCI World Tour"] },
  DIAMOND_LEAGUE: { shortLabel: "Diamond League", code: "DL" },
  WORLD_ATHLETICS_CHAMPIONSHIPS: { shortLabel: "World Athletics", code: "WCH", titleNames: ["World Athletics Championships"] },
  IPL: { shortLabel: "IPL", code: "IPL" },
  CRICKET_WORLD_CUP: { shortLabel: "Cricket World Cup", code: "CWC" },
  FIFA_WOMENS_WORLD_CUP: { shortLabel: "Women's World Cup", code: "WWC", titleNames: ["FIFA Women's World Cup"] },
  EPL: { shortLabel: "Premier League", code: "EPL" },
  BUNDESLIGA: { shortLabel: "Bundesliga", code: "GER" },
  LA_LIGA: { shortLabel: "La Liga", code: "ESP" },
  SERIE_A: { shortLabel: "Serie A", code: "ITA" },
  LIGUE_1: { shortLabel: "Ligue 1", code: "FRA" },
  CHAMPIONSHIP: { shortLabel: "Championship", code: "EFL", titleNames: ["EFL Championship"] },
  EREDIVISIE: { shortLabel: "Eredivisie", code: "NED" },
  PRIMEIRA_LIGA: { shortLabel: "Primeira Liga", code: "POR" },
  BRASILEIRAO: { shortLabel: "Brasileirão", code: "BRA" },
  UFC: { shortLabel: "UFC", code: "UFC" },
  PFL: { shortLabel: "PFL", code: "PFL" },
  RIZIN: { shortLabel: "RIZIN", code: "RIZ" },
  ONE: { shortLabel: "ONE", code: "ONE", titleNames: ["One"] },
  BOXING_MAJOR: { shortLabel: "Boxing", code: "BOX" },
  ZUFFA_BOXING: { shortLabel: "Zuffa Boxing", code: "ZUF" },
  IWF_WORLDS: { shortLabel: "IWF Worlds", code: "WCH", titleNames: ["IWF World Championships"] },
  IWF_JUNIOR_WORLDS: { shortLabel: "Junior Worlds", code: "JWCH", titleNames: ["IWF World Junior Championships"] },
  IWF_YOUTH_WORLDS: { shortLabel: "Youth Worlds", code: "YWCH", titleNames: ["IWF World Youth Championships"] },
  MASTERS_WORLDS: { shortLabel: "Masters Worlds", code: "MWCH", titleNames: ["World Masters Weightlifting Championships"] },
  WEIGHTLIFTING_AFRICA: { shortLabel: "African Championships", code: "AFR", titleNames: ["African Weightlifting Championships"] },
  WEIGHTLIFTING_ASIA: { shortLabel: "Asian Championships", code: "ASIA", titleNames: ["Asian Weightlifting Championships"] },
  WEIGHTLIFTING_EUROPE: { shortLabel: "European Championships", code: "EUR", titleNames: ["European Weightlifting Championships"] },
  WEIGHTLIFTING_OCEANIA: { shortLabel: "Oceania Championships", code: "OCE" },
  WEIGHTLIFTING_PAN_AMERICA: { shortLabel: "Pan Am Championships", code: "PAN", titleNames: ["Pan-American Weightlifting Championships", "Pan-American Championships"] },
  WEIGHTLIFTING_COMMONWEALTH_GAMES: { shortLabel: "Commonwealth Games", code: "CWG", titleNames: ["Commonwealth Games weightlifting"] },
  WEIGHTLIFTING_ASIAN_GAMES: { shortLabel: "Asian Games", code: "AG", titleNames: ["Asian Games weightlifting"] },
  WEIGHTLIFTING_PAN_AM_GAMES: { shortLabel: "Pan Am Games", code: "PAG", titleNames: ["Pan American Games weightlifting"] },
  NFL: { shortLabel: "NFL", code: "NFL" },
  NBA: { shortLabel: "NBA", code: "NBA" },
  WNBA: { shortLabel: "WNBA", code: "WNBA" },
  NCAA_MENS_BASKETBALL: { shortLabel: "Men's college basketball", code: "MCBB" },
  NCAA_WOMENS_BASKETBALL: { shortLabel: "Women's college basketball", code: "WCBB" },
  COLLEGE_FOOTBALL: { shortLabel: "College football", code: "CFB" },
  UEFA_EUROPA_LEAGUE: { shortLabel: "Europa League", code: "UEL" },
  UEFA_CONFERENCE_LEAGUE: { shortLabel: "Conference League", code: "UECL" },
  UEFA_NATIONS_LEAGUE: { shortLabel: "Nations League", code: "UNL" },
  MLS: { shortLabel: "MLS", code: "MLS" },
  FA_CUP: { shortLabel: "FA Cup", code: "FA" },
  LEAGUE_CUP: { shortLabel: "League Cup", code: "EFLC", titleNames: ["Carabao Cup"] },
  LIGA_MX: { shortLabel: "Liga MX", code: "MEX" },
  COPA_LIBERTADORES: { shortLabel: "Libertadores", code: "LIB", titleNames: ["Copa Libertadores"] },
  COPA_SUDAMERICANA: { shortLabel: "Sudamericana", code: "SUD", titleNames: ["Copa Sudamericana"] },
  NWSL: { shortLabel: "NWSL", code: "NWSL" },
  WSL: { shortLabel: "WSL", code: "WSL", titleNames: ["Women's Super League"] },
  UEFA_WOMENS_CHAMPIONS_LEAGUE: { shortLabel: "Women's Champions League", code: "UWCL" },
  G_LEAGUE: { shortLabel: "G League", code: "GL" },
  NBL: { shortLabel: "NBL", code: "NBL" },
  UFL: { shortLabel: "UFL", code: "UFL" },
  MLB: { shortLabel: "MLB", code: "MLB" },
  NHL: { shortLabel: "NHL", code: "NHL" },
  F1: { shortLabel: "F1", code: "F1" },
  NASCAR_CUP: { shortLabel: "NASCAR", code: "NASC", titleNames: ["NASCAR Cup Series"] },
  INDYCAR: { shortLabel: "IndyCar", code: "INDY", titleNames: ["INDYCAR"] },
  FIFA_WORLD_CUP: { shortLabel: "World Cup", code: "WC", titleNames: ["FIFA World Cup", "FIFA"] },
  UEFA_CHAMPIONS_LEAGUE: { shortLabel: "Champions League", code: "UCL" },
  IFSC_WORLD_CUP: { shortLabel: "World Cup", code: "WC", titleNames: ["World Cup", "World Climbing World Cup", "World Climbing"] },
  IFSC_PARA_WORLD_CUP: { shortLabel: "Para World Cup", code: "PWC", titleNames: ["Para World Cup", "World Climbing Para Series", "PARA"] },
  IFSC_YOUTH_WORLD_CHAMPIONSHIPS: {
    shortLabel: "YOUTH", titleNames: ["Youth World Championships"]
  },
  IFSC_WORLDS: { shortLabel: "Worlds", code: "WCH", titleNames: ["World Championships"] },
  IFSC_YOUTH_WORLDS: { shortLabel: "Youth Worlds", code: "YWCH", titleNames: ["Youth World Championships"] },
  IFSC_PARA_WORLDS: { shortLabel: "Para Worlds", code: "PWCH", titleNames: ["Para World Championships"] },
  CLIMBING_EUROPE: { shortLabel: "European Championships", code: "EUR" },
  CLIMBING_ASIA: { shortLabel: "Asian Championships", code: "ASIA" },
  CLIMBING_AFRICA: { shortLabel: "African Championships" },
  CLIMBING_OCEANIA: { shortLabel: "Oceania Championships", code: "OCE" },
  CLIMBING_PAN_AMERICA: { shortLabel: "Pan Am Championships", code: "PAN", titleNames: ["Pan American Championships", "Pan-American Championships"] },
  CLIMBING_OLYMPIC_QUALIFIERS: { shortLabel: "Olympic qualifiers", code: "OQ", titleNames: ["World Climbing"] },
  CLIMBING_CONTINENTAL_CUP: { shortLabel: "Continental Cups", code: "CC", titleNames: ["World Climbing"] },
  CLIMBING_YOUTH_CONTINENTAL_CUP: { shortLabel: "Youth Continental Cups", code: "YCC", titleNames: ["World Climbing"] },
  CLIMBING_CHALLENGER: { shortLabel: "Challenger", code: "CHAL", titleNames: ["World Climbing Challenger"] },
  CLIMBING_NATIONS_GRAND_FINALE: { shortLabel: "Nations Grand Finale", code: "NGF", titleNames: ["World Climbing Nations Grand Finale"] },
  CLIMBING_ASIAN_GAMES: { shortLabel: "Asian Games", code: "AG" },
  CLIMBING_ASIAN_BEACH_GAMES: { shortLabel: "Asian Beach Games", code: "ABG" },
  CLIMBING_EUROPEAN_GAMES: { shortLabel: "European Games", code: "EG" },
  CLIMBING_PAN_AM_GAMES: { shortLabel: "Pan Am Games", code: "PAG", titleNames: ["Pan American Games"] },
  CLIMBING_SOUTH_AM_GAMES: { shortLabel: "South American Games", code: "SAG" },
  PGA_TOUR: { shortLabel: "PGA Tour", code: "PGA" },
  LPGA_TOUR: { shortLabel: "LPGA Tour", code: "LPGA" },
  DP_WORLD_TOUR: { shortLabel: "DP World Tour", code: "DPWT" },
  LIV_GOLF: { shortLabel: "LIV Golf", code: "LIV" },
  ATP: { shortLabel: "ATP", code: "ATP" },
  WTA: { shortLabel: "WTA", code: "WTA" },
  RUGBY_WORLD_CUP: { shortLabel: "Rugby World Cup", code: "RWC" },
  WOMENS_RUGBY_WORLD_CUP: { shortLabel: "Women's Rugby World Cup", code: "WRWC" },
  SIX_NATIONS: { shortLabel: "Six Nations", code: "6N" },
  RUGBY_CHAMPIONSHIP: { shortLabel: "Rugby Championship", code: "TRC", titleNames: ["The Rugby Championship"] },
  NATIONS_CHAMPIONSHIP: { shortLabel: "Nations Championship", code: "NC" },
  RUGBY_CHAMPIONS_CUP: { shortLabel: "Champions Cup", code: "ECC" },
  RUGBY_CHALLENGE_CUP: { shortLabel: "Challenge Cup", code: "CHAL" },
  PREMIERSHIP_RUGBY: { shortLabel: "Premiership", code: "PREM", titleNames: ["Gallagher Prem"] },
  UNITED_RUGBY_CHAMPIONSHIP: { shortLabel: "URC", code: "URC", titleNames: ["United Rugby Championship"] },
  TOP_14: { shortLabel: "Top 14", code: "T14" },
  SUPER_RUGBY_PACIFIC: { shortLabel: "Super Rugby", code: "SRP", titleNames: ["Super Rugby Pacific"] },
  CURRIE_CUP: { shortLabel: "Currie Cup" },
  NPC: { shortLabel: "NPC", code: "NPC", titleNames: ["National Provincial Championship"] },
  URBA_TOP_14: { shortLabel: "URBA Top 14", code: "URBA" },
  MAJOR_LEAGUE_RUGBY: { shortLabel: "MLR", code: "MLR", titleNames: ["Major League Rugby"] },
  BRITISH_IRISH_LIONS: { shortLabel: "Lions tour", code: "BIL", titleNames: ["British and Irish Lions"] },
  RUGBY_TESTS: { shortLabel: "Tests", code: "TEST", titleNames: ["International tests"] },
};

export const SOCCER_COUNTRIES: Record<string, { name: string; flag: string }> = {
  EPL: { name: "England", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  CHAMPIONSHIP: { name: "England", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  BUNDESLIGA: { name: "Germany", flag: "🇩🇪" },
  LA_LIGA: { name: "Spain", flag: "🇪🇸" },
  SERIE_A: { name: "Italy", flag: "🇮🇹" },
  LIGUE_1: { name: "France", flag: "🇫🇷" },
  EREDIVISIE: { name: "Netherlands", flag: "🇳🇱" },
  PRIMEIRA_LIGA: { name: "Portugal", flag: "🇵🇹" },
  BRASILEIRAO: { name: "Brazil", flag: "🇧🇷" },
  FA_CUP: { name: "England", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  LEAGUE_CUP: { name: "England", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  WSL: { name: "England", flag: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  LIGA_MX: { name: "Mexico", flag: "🇲🇽" },
};

export const NO_FLAG_LEAGUES = new Set(["NBA", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL", "COLLEGE_FOOTBALL", "NFL", "NHL", "MLB", "NASCAR_CUP", "INDYCAR"]);

// A common venue is not a league jurisdiction for these international leagues.
const NO_PILL_FLAG_LEAGUES = new Set([
  "UEFA_CHAMPIONS_LEAGUE", "UEFA_EUROPA_LEAGUE",
  "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "UEFA_WOMENS_CHAMPIONS_LEAGUE",
  "COPA_LIBERTADORES", "COPA_SUDAMERICANA",
]);
const NORTH_AMERICAN_LEAGUES = new Set(["MLS", "NWSL", "UFL", "NFL", "NBA", "WNBA", "NHL", "MLB", "COLLEGE_FOOTBALL",
  "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL", "G_LEAGUE"]);

export function pillCountries(items: EventCard[]): Country[] {
  if (!items.length) return [];
  const league = items[0].league;
  if (NO_PILL_FLAG_LEAGUES.has(league)) return [];
  const domestic = SOCCER_COUNTRIES[league];
  const jurisdiction = domestic ? countryIdentity(domestic.name === "England" ? "GB-ENG" : domestic.name) : undefined;
  const host = commonHostCountry(items);
  const foreign = host && (!NORTH_AMERICAN_LEAGUES.has(league) || !["US", "CA"].includes(host.code));
  const distinct = host && jurisdiction && host.code !== jurisdiction.code
    && !(jurisdiction.code.startsWith("GB-") && host.code === "GB");
  return jurisdiction ? [jurisdiction, ...(distinct ? [host!] : [])] : foreign ? [host!] : [];
}

const SPORT_GROUPS = [
  { name: "Soccer", leagues: [...Object.keys(SOCCER_COUNTRIES), "FIFA_WORLD_CUP", "FIFA_WOMENS_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE", "UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS", "COPA_LIBERTADORES", "COPA_SUDAMERICANA", "NWSL", "UEFA_WOMENS_CHAMPIONS_LEAGUE"] },
  { name: "Motorsports", leagues: ["F1", "NASCAR_CUP", "INDYCAR", "MOTOGP", "WEC"] },
  { name: "Football", leagues: ["NFL", "COLLEGE_FOOTBALL", "UFL"] },
  { name: "Basketball", leagues: ["NBA", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL", "G_LEAGUE", "NBL"] },
  { name: "Baseball", leagues: ["MLB"] },
  { name: "Hockey", leagues: ["NHL"] },
  { name: "Combat sports", leagues: ["UFC", "PFL", "RIZIN", "ONE", "BOXING_MAJOR", "ZUFFA_BOXING"] },
  { name: "Golf", leagues: ["PGA_TOUR", "LPGA_TOUR", "DP_WORLD_TOUR", "LIV_GOLF"] },
  { name: "Tennis", leagues: ["ATP", "WTA"] },
  { name: "Rugby", leagues: ["RUGBY_WORLD_CUP", "WOMENS_RUGBY_WORLD_CUP", "SIX_NATIONS", "RUGBY_CHAMPIONSHIP",
    "NATIONS_CHAMPIONSHIP", "RUGBY_CHAMPIONS_CUP", "RUGBY_CHALLENGE_CUP", "PREMIERSHIP_RUGBY",
    "UNITED_RUGBY_CHAMPIONSHIP", "TOP_14", "SUPER_RUGBY_PACIFIC", "CURRIE_CUP", "NPC", "URBA_TOP_14",
    "MAJOR_LEAGUE_RUGBY", "BRITISH_IRISH_LIONS", "RUGBY_TESTS"] },
  { name: "Cycling", leagues: ["TOUR_DE_FRANCE", "GIRO_D_ITALIA", "VUELTA_A_ESPANA", "UCI_WORLD_TOUR"] },
  { name: "Athletics", leagues: ["DIAMOND_LEAGUE", "WORLD_ATHLETICS_CHAMPIONSHIPS"] },
  { name: "Cricket", leagues: ["IPL", "CRICKET_WORLD_CUP"] },
  { name: "Climbing", leagues: ["IFSC_WORLD_CUP", "IFSC_WORLDS", "IFSC_YOUTH_WORLDS", "IFSC_YOUTH_WORLD_CHAMPIONSHIPS",
    "IFSC_PARA_WORLD_CUP", "IFSC_PARA_WORLDS", "CLIMBING_EUROPE", "CLIMBING_ASIA", "CLIMBING_AFRICA", "CLIMBING_OCEANIA",
    "CLIMBING_PAN_AMERICA", "CLIMBING_OLYMPIC_QUALIFIERS", "CLIMBING_CONTINENTAL_CUP", "CLIMBING_YOUTH_CONTINENTAL_CUP",
    "CLIMBING_CHALLENGER", "CLIMBING_NATIONS_GRAND_FINALE", "CLIMBING_ASIAN_GAMES", "CLIMBING_ASIAN_BEACH_GAMES",
    "CLIMBING_EUROPEAN_GAMES", "CLIMBING_PAN_AM_GAMES", "CLIMBING_SOUTH_AM_GAMES"] },
  { name: "Weightlifting", leagues: Object.keys(WEIGHTLIFTING_LEAGUE_LEVELS) },
];

export function interestGroups(leagues: LeagueInterest[]) {
  const available = new Map(leagues.map((league) => [league.value, league]));
  const groups = SPORT_GROUPS.map((group) => ({
    name: group.name,
    leagues: group.leagues.filter((league) => available.delete(league)),
  }));
  for (const { value, sport } of available.values()) {
    const category = categoryForLeague(value, sport);
    const group = groups.find(({ name }) => CATEGORY_KEYS[name as keyof typeof CATEGORY_KEYS] === category);
    if (group && group.name !== "Golf") group.leagues.push(value);
  }
  return groups.filter((group) => group.leagues.length);
}

export function toggleInterestGroup(selected: string[], leagues: string[]) {
  const allSelected = leagues.every((league) => selected.includes(league));
  return allSelected
    ? selected.filter((league) => !leagues.includes(league))
    : [...new Set([...selected, ...leagues])];
}
export const CATEGORY_KEYS = {
  Soccer: "soccer", Motorsports: "motorsport", "Football": "american-football",
  Basketball: "basketball", Baseball: "baseball", Hockey: "hockey", "Combat sports": "combat",
  Golf: "golf", Tennis: "tennis", Rugby: "rugby", Cycling: "cycling", Athletics: "athletics", Cricket: "cricket", Climbing: "climbing", Weightlifting: "weightlifting",
} as const;
export type CategoryKey = typeof CATEGORY_KEYS[keyof typeof CATEGORY_KEYS];

const SPORT_CATEGORIES: Record<string, CategoryKey> = {
  soccer: "soccer", motorsport: "motorsport", motorsports: "motorsport",
  football: "american-football", american_football: "american-football", "american-football": "american-football",
  basketball: "basketball", baseball: "baseball", hockey: "hockey", ice_hockey: "hockey",
  combat: "combat", combat_sports: "combat", mma: "combat", boxing: "combat",
  golf: "golf", tennis: "tennis", rugby: "rugby", cycling: "cycling", athletics: "athletics", cricket: "cricket", climbing: "climbing", weightlifting: "weightlifting",
};

// New competitions inherit their event's sport; adding a league never allocates a colour.
// Unknown families stay neutral until deliberately assigned a family colour.
export function categoryForLeague(league: string, sport?: string): CategoryKey | null {
  const group = SPORT_GROUPS.find((group) => group.leagues.includes(league));
  if (group) return CATEGORY_KEYS[group.name as keyof typeof CATEGORY_KEYS];
  return SPORT_CATEGORIES[sport?.toLowerCase() || ""] || null;
}

// Source competition identities can differ from the compact section label.
// Keep them as metadata so all agenda rows use the same title rule.
export function leagueTitleNames(league: string, sport?: string) {
  return [...(LEAGUE_META[league]?.titleNames || []), leagueVisual(league, sport).shortLabel, league.replaceAll("_", " ")];
}

export function leagueVisual(league: string, sport?: string) {
  const category = categoryForLeague(league, sport);
  return {
    ...(LEAGUE_META[league] || {
      shortLabel: league.replaceAll("_", " ")
    }),
    className: category ? `category-${category}` : "category-unknown",
  };
}


// One order for every view. A final/playoff takes precedence over regular play.
const TIERS = [
  ["FIFA_WORLD_CUP", "FIFA_WOMENS_WORLD_CUP", "WORLD_ATHLETICS_CHAMPIONSHIPS", "CRICKET_WORLD_CUP", "PGA_MAJOR", "LPGA_MAJOR", "TENNIS_MAJOR", "RUGBY_WORLD_CUP", "WOMENS_RUGBY_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE"],
  ["NFL", "NBA", "F1", "EPL"],
  ["MLB", "NHL", "UFC", "BOXING_MAJOR", "COLLEGE_FOOTBALL"],
  ["LA_LIGA", "BUNDESLIGA", "SERIE_A", "LIGUE_1", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL"],
  ["NASCAR_CUP", "INDYCAR", "MOTOGP", "WEC", "TOUR_DE_FRANCE", "GIRO_D_ITALIA", "VUELTA_A_ESPANA", "IWF_WORLDS", "IFSC_WORLD_CUP"],
  ["PGA_TOUR", "LPGA_TOUR", "DP_WORLD_TOUR", "LIV_GOLF", "UCI_WORLD_TOUR", "DIAMOND_LEAGUE", "IPL", "ATP", "WTA", "SIX_NATIONS", "RUGBY_CHAMPIONSHIP",
    "NATIONS_CHAMPIONSHIP", "RUGBY_CHAMPIONS_CUP", "PREMIERSHIP_RUGBY", "UNITED_RUGBY_CHAMPIONSHIP", "TOP_14",
    "SUPER_RUGBY_PACIFIC", "CHAMPIONSHIP", "EREDIVISIE", "PRIMEIRA_LIGA", "BRASILEIRAO", "UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS", "FA_CUP", "LEAGUE_CUP", "LIGA_MX", "COPA_LIBERTADORES", "COPA_SUDAMERICANA", "NWSL", "WSL", "UEFA_WOMENS_CHAMPIONS_LEAGUE", "G_LEAGUE", "NBL", "UFL"],
  ["RUGBY_CHALLENGE_CUP", "CURRIE_CUP", "NPC", "URBA_TOP_14", "MAJOR_LEAGUE_RUGBY", "BRITISH_IRISH_LIONS", "RUGBY_TESTS"],
  ["PFL", "RIZIN", "ONE", "ZUFFA_BOXING"],
  ["IFSC_PARA_WORLD_CUP", "IFSC_PARA_WORLDS", "IFSC_YOUTH_WORLD_CHAMPIONSHIPS", "IFSC_YOUTH_WORLDS",
    "IWF_JUNIOR_WORLDS", "IWF_YOUTH_WORLDS", "MASTERS_WORLDS",
    "WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_OCEANIA",
    "WEIGHTLIFTING_PAN_AMERICA", "WEIGHTLIFTING_COMMONWEALTH_GAMES", "WEIGHTLIFTING_ASIAN_GAMES", "WEIGHTLIFTING_PAN_AM_GAMES"],
];
const RANKS = new Map(TIERS.flatMap((tier, index) => tier.map((league, order) => [league, index * 100 + order] as const)));
const MAJOR_LEAGUES: Record<string, string> = { PGA_TOUR: "PGA_MAJOR", LPGA_TOUR: "LPGA_MAJOR", ATP: "TENNIS_MAJOR", WTA: "TENNIS_MAJOR" };
function eventRank(event: EventCard) {
  const league = event.competition_phase === "championship" ? MAJOR_LEAGUES[event.league] || event.league : event.league;
  return RANKS.get(league) ?? 899;
}
const POSTSEASON_PHASES = new Set(["postseason", "knockout", "final", "championship"]);
export function compareEvents(a: EventCard, b: EventCard): number {
  const playoff = (event: EventCard) => POSTSEASON_PHASES.has(event.competition_phase);
  return Number(playoff(b)) - Number(playoff(a)) || eventRank(a) - eventRank(b)
    || (eventInstant(a) ?? Infinity) - (eventInstant(b) ?? Infinity)
    || a.title.localeCompare(b.title) || a.event_id.localeCompare(b.event_id);
}
export function leagueGroups(items: EventCard[]) {
  const groups = new Map<string, EventCard[]>();
  for (const event of [...items].sort(compareEvents)) {
    if (!groups.has(event.league)) groups.set(event.league, []);
    groups.get(event.league)!.push(event);
  }
  return [...groups].map(([league, items]) => ({ league, items }));
}

export function pillGroups(items: EventCard[]) {
  return leagueGroups(items).flatMap((group) => isGolf(group.items[0])
    ? group.items.map((event) => ({ league: group.league, items: [event] })) : [group]);
}
