import { commonHostCountry } from "./countries";
import { eventInstant } from "./date-utils";
import type { EventCard } from "./types";
import type { LeagueInterest } from "./interest-preferences";
import { isGolf } from "./golf";

const LEAGUE_META: Record<
  string,
  { shortLabel: string; titleNames?: string[] }
> = {
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
  CLIMBING_PAN_AMERICA: { shortLabel: "Pan-American Championships", titleNames: ["Pan American Championships"] },
  CLIMBING_PAN_AM_GAMES: { shortLabel: "Pan Am Games", titleNames: ["Pan American Games"] },
  CLIMBING_CHALLENGER: { shortLabel: "Challenger", titleNames: ["World Climbing Challenger"] },
  CLIMBING_NATIONS_GRAND_FINALE: { shortLabel: "Nations Grand Finale", titleNames: ["World Climbing Nations Grand Finale"] },
  CLIMBING_CONTINENTAL_CUP: { shortLabel: "Continental Cups", titleNames: ["World Climbing"] },
  CLIMBING_YOUTH_CONTINENTAL_CUP: { shortLabel: "Youth Continental Cups", titleNames: ["World Climbing"] },
  CLIMBING_OLYMPIC_QUALIFIERS: { shortLabel: "Olympic qualifiers", titleNames: ["World Climbing"] },
  PGA_TOUR: { shortLabel: "PGA Tour" },
  LPGA_TOUR: { shortLabel: "LPGA Tour" },
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

export const NO_FLAG_LEAGUES = new Set(["NBA", "NFL", "NHL", "MLB", "NASCAR_CUP", "INDYCAR"]);

export function pillCountry(items: EventCard[]) {
  const league = items[0].league;
  return NO_FLAG_LEAGUES.has(league)
    ? undefined : SOCCER_COUNTRIES[league] || commonHostCountry(items);
}

const CLIMBING_COMPETITIONS: Record<string, string> = {
  IFSC_WORLD_CUP: "World Cups",
  IFSC_WORLDS: "World Championships",
  IFSC_YOUTH_WORLDS: "Youth World Championships",
  IFSC_YOUTH_WORLD_CHAMPIONSHIPS: "Youth World Championships",
  IFSC_PARA_WORLD_CUP: "Para World Cups",
  IFSC_PARA_WORLDS: "Para World Championships",
  CLIMBING_EUROPE: "European Championships",
  CLIMBING_ASIA: "Asian Championships",
  CLIMBING_AFRICA: "African Championships",
  CLIMBING_OCEANIA: "Oceania Championships",
  CLIMBING_PAN_AMERICA: "Pan-American Championships",
  CLIMBING_OLYMPIC_QUALIFIERS: "Olympic qualifiers",
  CLIMBING_CONTINENTAL_CUP: "Continental Cups",
  CLIMBING_YOUTH_CONTINENTAL_CUP: "Youth Continental Cups",
  CLIMBING_CHALLENGER: "Challenger",
  CLIMBING_NATIONS_GRAND_FINALE: "Nations Grand Finale",
  CLIMBING_ASIAN_GAMES: "Asian Games",
  CLIMBING_ASIAN_BEACH_GAMES: "Asian Beach Games",
  CLIMBING_EUROPEAN_GAMES: "European Games",
  CLIMBING_PAN_AM_GAMES: "Pan Am Games",
  CLIMBING_SOUTH_AM_GAMES: "South American Games",
};

const SPORT_GROUPS = [
  { name: "Soccer", leagues: [...Object.keys(SOCCER_COUNTRIES), "FIFA_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE"] },
  { name: "Motorsports", leagues: ["F1", "NASCAR_CUP", "INDYCAR"] },
  { name: "Football", leagues: ["NFL"] },
  { name: "Basketball", leagues: ["NBA"] },
  { name: "Baseball", leagues: ["MLB"] },
  { name: "Hockey", leagues: ["NHL"] },
  { name: "Combat sports", leagues: ["UFC", "PFL", "RIZIN", "ONE", "BOXING_MAJOR"] },
  { name: "Golf", leagues: ["PGA_TOUR", "LPGA_TOUR"] },
  { name: "Climbing", leagues: Object.keys(CLIMBING_COMPETITIONS) },
  { name: "Weightlifting", leagues: ["IWF_WORLDS", "IWF_JUNIOR_WORLDS", "IWF_YOUTH_WORLDS", "MASTERS_WORLDS",
    "WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_OCEANIA",
    "WEIGHTLIFTING_PAN_AMERICA", "WEIGHTLIFTING_COMMONWEALTH_GAMES", "WEIGHTLIFTING_ASIAN_GAMES", "WEIGHTLIFTING_PAN_AM_GAMES"] },
];

export function interestChoices(group: { name: string; leagues: string[] }) {
  return group.leagues.map((league) => ({ name: CLIMBING_COMPETITIONS[league] || leagueVisual(league).shortLabel, leagues: [league] }));
}

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
  Golf: "golf", Climbing: "climbing", Weightlifting: "weightlifting",
} as const;
export type CategoryKey = typeof CATEGORY_KEYS[keyof typeof CATEGORY_KEYS];

const SPORT_CATEGORIES: Record<string, CategoryKey> = {
  soccer: "soccer", motorsport: "motorsport", motorsports: "motorsport",
  football: "american-football", american_football: "american-football", "american-football": "american-football",
  basketball: "basketball", baseball: "baseball", hockey: "hockey", ice_hockey: "hockey",
  combat: "combat", combat_sports: "combat", mma: "combat", boxing: "combat",
  golf: "golf", climbing: "climbing", weightlifting: "weightlifting",
};

// New competitions inherit their event's sport; adding a league never allocates a colour.
// Unknown families stay neutral until deliberately assigned one of the two spares.
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
      shortLabel: CLIMBING_COMPETITIONS[league] || league.replaceAll("_", " ")
    }),
    className: category ? `category-${category}` : "category-unknown",
  };
}


// One order for every view. A final/playoff takes precedence over regular play.
const TIERS = [
  ["FIFA_WORLD_CUP", "PGA_MAJOR", "LPGA_MAJOR", "UEFA_CHAMPIONS_LEAGUE"],
  ["NFL", "NBA", "F1", "EPL"],
  ["MLB", "NHL", "UFC", "BOXING_MAJOR"],
  ["LA_LIGA", "BUNDESLIGA", "SERIE_A", "LIGUE_1"],
  ["NASCAR_CUP", "INDYCAR", "IWF_WORLDS", "IFSC_WORLD_CUP"],
  ["PGA_TOUR", "LPGA_TOUR", "CHAMPIONSHIP", "EREDIVISIE", "PRIMEIRA_LIGA", "BRASILEIRAO"],
  ["PFL", "RIZIN", "ONE"],
  ["IFSC_PARA_WORLD_CUP", "IFSC_PARA_WORLDS", "IFSC_YOUTH_WORLD_CHAMPIONSHIPS", "IFSC_YOUTH_WORLDS",
    "IWF_JUNIOR_WORLDS", "IWF_YOUTH_WORLDS", "MASTERS_WORLDS",
    "WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_OCEANIA",
    "WEIGHTLIFTING_PAN_AMERICA", "WEIGHTLIFTING_COMMONWEALTH_GAMES", "WEIGHTLIFTING_ASIAN_GAMES", "WEIGHTLIFTING_PAN_AM_GAMES"],
];
const RANKS = new Map(TIERS.flatMap((tier, index) => tier.map((league, order) => [league, index * 100 + order] as const)));
function golfMajor(event: EventCard) {
  return ["PGA_TOUR", "LPGA_TOUR"].includes(event.league) && event.competition_phase === "championship";
}
function eventRank(event: EventCard) {
  const league = golfMajor(event)
    ? event.league === "LPGA_TOUR" ? "LPGA_MAJOR" : "PGA_MAJOR" : event.league;
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
