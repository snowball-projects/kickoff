import { commonHostCountry } from "./countries";
import { eventInstant } from "./date-utils";
import type { EventCard } from "./types";
import { WEIGHTLIFTING_LEAGUE_LEVELS, type LeagueInterest } from "./interest-preferences";
import { isGolf } from "./golf";

const LEAGUE_META: Record<
  string,
  { shortLabel: string; titleNames?: string[] }
> = {
  MOTOGP: { shortLabel: "MotoGP" },
  WEC: { shortLabel: "WEC" },
  TOUR_DE_FRANCE: { shortLabel: "Tour de France" },
  GIRO_D_ITALIA: { shortLabel: "Giro d'Italia" },
  VUELTA_A_ESPANA: { shortLabel: "Vuelta a España" },
  UCI_WORLD_TOUR: { shortLabel: "UCI World Tour" },
  DIAMOND_LEAGUE: { shortLabel: "Diamond League" },
  WORLD_ATHLETICS_CHAMPIONSHIPS: { shortLabel: "World Athletics Championships" },
  IPL: { shortLabel: "IPL" },
  CRICKET_WORLD_CUP: { shortLabel: "Cricket World Cup" },
  FIFA_WOMENS_WORLD_CUP: { shortLabel: "FIFA Women's World Cup" },
  EPL: { shortLabel: "Premier League" },
  BUNDESLIGA: {
    shortLabel: "Bundesliga"
  },
  LA_LIGA: { shortLabel: "La Liga" },
  SERIE_A: { shortLabel: "Serie A" },
  LIGUE_1: { shortLabel: "Ligue 1" },
  CHAMPIONSHIP: { shortLabel: "EFL Championship" },
  EREDIVISIE: { shortLabel: "Eredivisie" },
  PRIMEIRA_LIGA: { shortLabel: "Primeira Liga" },
  BRASILEIRAO: { shortLabel: "Brasileirão" },
  UFC: { shortLabel: "UFC" },
  PFL: { shortLabel: "PFL" },
  RIZIN: { shortLabel: "RIZIN" },
  ONE: { shortLabel: "One" },
  BOXING_MAJOR: { shortLabel: "Boxing" },
  IWF_WORLDS: { shortLabel: "IWF Worlds", titleNames: ["IWF World Championships"] },
  IWF_JUNIOR_WORLDS: { shortLabel: "Junior Worlds", titleNames: ["IWF World Junior Championships"] },
  IWF_YOUTH_WORLDS: { shortLabel: "Youth Worlds", titleNames: ["IWF World Youth Championships"] },
  MASTERS_WORLDS: { shortLabel: "Masters Worlds", titleNames: ["World Masters Weightlifting Championships"] },
  WEIGHTLIFTING_AFRICA: { shortLabel: "African Championships", titleNames: ["African Weightlifting Championships"] },
  WEIGHTLIFTING_ASIA: { shortLabel: "Asian Championships", titleNames: ["Asian Weightlifting Championships"] },
  WEIGHTLIFTING_EUROPE: { shortLabel: "European Championships", titleNames: ["European Weightlifting Championships"] },
  WEIGHTLIFTING_OCEANIA: { shortLabel: "Oceania Championships" },
  WEIGHTLIFTING_PAN_AMERICA: { shortLabel: "Pan-American Championships", titleNames: ["Pan-American Weightlifting Championships"] },
  WEIGHTLIFTING_COMMONWEALTH_GAMES: { shortLabel: "Commonwealth Games", titleNames: ["Commonwealth Games weightlifting"] },
  WEIGHTLIFTING_ASIAN_GAMES: { shortLabel: "Asian Games", titleNames: ["Asian Games weightlifting"] },
  WEIGHTLIFTING_PAN_AM_GAMES: { shortLabel: "Pan Am Games", titleNames: ["Pan American Games weightlifting"] },
  NFL: { shortLabel: "NFL" },
  NBA: { shortLabel: "NBA" },
  WNBA: { shortLabel: "WNBA" },
  NCAA_MENS_BASKETBALL: { shortLabel: "Men's college basketball" },
  NCAA_WOMENS_BASKETBALL: { shortLabel: "Women's college basketball" },
  COLLEGE_FOOTBALL: { shortLabel: "College football" },
  UEFA_EUROPA_LEAGUE: { shortLabel: "Europa League" },
  UEFA_CONFERENCE_LEAGUE: { shortLabel: "Conference League" },
  UEFA_NATIONS_LEAGUE: { shortLabel: "Nations League" },
  MLS: { shortLabel: "MLS" },
  MLB: { shortLabel: "MLB" },
  NHL: { shortLabel: "NHL" },
  F1: { shortLabel: "F1" },
  NASCAR_CUP: { shortLabel: "NASCAR", titleNames: ["NASCAR Cup Series"] },
  INDYCAR: { shortLabel: "INDYCAR" },
  FIFA_WORLD_CUP: { shortLabel: "FIFA", titleNames: ["FIFA World Cup"] },
  UEFA_CHAMPIONS_LEAGUE: {
    shortLabel: "Champions League"
  },
  IFSC_WORLD_CUP: { shortLabel: "World Climbing", titleNames: ["World Cup", "World Climbing World Cup"] },
  IFSC_PARA_WORLD_CUP: {
    shortLabel: "PARA", titleNames: ["Para World Cup", "World Climbing Para Series"]
  },
  IFSC_YOUTH_WORLD_CHAMPIONSHIPS: {
    shortLabel: "YOUTH", titleNames: ["Youth World Championships"]
  },
  IFSC_WORLDS: { shortLabel: "World Championships", titleNames: ["World Championships"] },
  IFSC_YOUTH_WORLDS: { shortLabel: "Youth World Championships", titleNames: ["Youth World Championships"] },
  IFSC_PARA_WORLDS: { shortLabel: "Para World Championships", titleNames: ["Para World Championships"] },
  CLIMBING_EUROPE: { shortLabel: "European Championships" },
  CLIMBING_ASIA: { shortLabel: "Asian Championships" },
  CLIMBING_AFRICA: { shortLabel: "African Championships" },
  CLIMBING_OCEANIA: { shortLabel: "Oceania Championships" },
  CLIMBING_PAN_AMERICA: { shortLabel: "Pan-American Championships", titleNames: ["Pan American Championships"] },
  CLIMBING_OLYMPIC_QUALIFIERS: { shortLabel: "Olympic qualifiers", titleNames: ["World Climbing"] },
  CLIMBING_CONTINENTAL_CUP: { shortLabel: "Continental Cups", titleNames: ["World Climbing"] },
  CLIMBING_YOUTH_CONTINENTAL_CUP: { shortLabel: "Youth Continental Cups", titleNames: ["World Climbing"] },
  CLIMBING_CHALLENGER: { shortLabel: "Challenger", titleNames: ["World Climbing Challenger"] },
  CLIMBING_NATIONS_GRAND_FINALE: { shortLabel: "Nations Grand Finale", titleNames: ["World Climbing Nations Grand Finale"] },
  CLIMBING_ASIAN_GAMES: { shortLabel: "Asian Games" },
  CLIMBING_ASIAN_BEACH_GAMES: { shortLabel: "Asian Beach Games" },
  CLIMBING_EUROPEAN_GAMES: { shortLabel: "European Games" },
  CLIMBING_PAN_AM_GAMES: { shortLabel: "Pan Am Games", titleNames: ["Pan American Games"] },
  CLIMBING_SOUTH_AM_GAMES: { shortLabel: "South American Games" },
  PGA_TOUR: { shortLabel: "PGA Tour" },
  LPGA_TOUR: { shortLabel: "LPGA Tour" },
  DP_WORLD_TOUR: { shortLabel: "DP World Tour" },
  LIV_GOLF: { shortLabel: "LIV Golf" },
  ATP: { shortLabel: "ATP" },
  WTA: { shortLabel: "WTA" },
  RUGBY_WORLD_CUP: { shortLabel: "Rugby World Cup" },
  WOMENS_RUGBY_WORLD_CUP: { shortLabel: "Women's Rugby World Cup" },
  SIX_NATIONS: { shortLabel: "Six Nations" },
  RUGBY_CHAMPIONSHIP: { shortLabel: "The Rugby Championship" },
  NATIONS_CHAMPIONSHIP: { shortLabel: "Nations Championship" },
  RUGBY_CHAMPIONS_CUP: { shortLabel: "Champions Cup" },
  RUGBY_CHALLENGE_CUP: { shortLabel: "Challenge Cup" },
  PREMIERSHIP_RUGBY: { shortLabel: "Gallagher Prem" },
  UNITED_RUGBY_CHAMPIONSHIP: { shortLabel: "United Rugby Championship" },
  TOP_14: { shortLabel: "Top 14" },
  SUPER_RUGBY_PACIFIC: { shortLabel: "Super Rugby Pacific" },
  CURRIE_CUP: { shortLabel: "Currie Cup" },
  NPC: { shortLabel: "National Provincial Championship" },
  URBA_TOP_14: { shortLabel: "URBA Top 14" },
  MAJOR_LEAGUE_RUGBY: { shortLabel: "Major League Rugby" },
  BRITISH_IRISH_LIONS: { shortLabel: "British and Irish Lions" },
  RUGBY_TESTS: { shortLabel: "International tests" },
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
};

export const NO_FLAG_LEAGUES = new Set(["NBA", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL", "COLLEGE_FOOTBALL", "NFL", "NHL", "MLB", "NASCAR_CUP", "INDYCAR"]);

export function pillCountry(items: EventCard[]) {
  const league = items[0].league;
  return NO_FLAG_LEAGUES.has(league)
    ? undefined : SOCCER_COUNTRIES[league] || commonHostCountry(items);
}

const SPORT_GROUPS = [
  { name: "Soccer", leagues: [...Object.keys(SOCCER_COUNTRIES), "FIFA_WORLD_CUP", "FIFA_WOMENS_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE", "UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS"] },
  { name: "Motorsports", leagues: ["F1", "NASCAR_CUP", "INDYCAR", "MOTOGP", "WEC"] },
  { name: "Football", leagues: ["NFL", "COLLEGE_FOOTBALL"] },
  { name: "Basketball", leagues: ["NBA", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL"] },
  { name: "Baseball", leagues: ["MLB"] },
  { name: "Hockey", leagues: ["NHL"] },
  { name: "Combat sports", leagues: ["UFC", "PFL", "RIZIN", "ONE", "BOXING_MAJOR"] },
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
    "SUPER_RUGBY_PACIFIC", "CHAMPIONSHIP", "EREDIVISIE", "PRIMEIRA_LIGA", "BRASILEIRAO", "UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS"],
  ["RUGBY_CHALLENGE_CUP", "CURRIE_CUP", "NPC", "URBA_TOP_14", "MAJOR_LEAGUE_RUGBY", "BRITISH_IRISH_LIONS", "RUGBY_TESTS"],
  ["PFL", "RIZIN", "ONE"],
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
