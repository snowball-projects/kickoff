import { interestLeagues, type LeagueInterest } from "./interest-preferences";

const LEAGUE_META: Record<
  string,
  { shortLabel: string; order: number }
> = {
  EPL: { shortLabel: "Premier League", order: 20 },
  BUNDESLIGA: {
    shortLabel: "Bundesliga",
    order: 21,
  },
  LA_LIGA: { shortLabel: "La Liga", order: 22 },
  SERIE_A: { shortLabel: "Serie A", order: 23 },
  LIGUE_1: { shortLabel: "Ligue 1", order: 24 },
  CHAMPIONSHIP: { shortLabel: "EFL Championship · England", order: 25 },
  EREDIVISIE: { shortLabel: "Eredivisie", order: 26 },
  PRIMEIRA_LIGA: { shortLabel: "Primeira Liga", order: 27 },
  BRASILEIRAO: { shortLabel: "Brazil Série A", order: 28 },
  UFC: { shortLabel: "UFC", order: 30 },
  PFL: { shortLabel: "PFL", order: 31 },
  RIZIN: { shortLabel: "RIZIN", order: 32 },
  ONE: { shortLabel: "One", order: 33 },
  BOXING_MAJOR: { shortLabel: "Boxing", order: 34 },
  IWF_WORLDS: { shortLabel: "IWF Worlds", order: 35 },
  IWF_JUNIOR_WORLDS: { shortLabel: "Junior Worlds", order: 40 },
  IWF_YOUTH_WORLDS: { shortLabel: "Youth Worlds", order: 41 },
  MASTERS_WORLDS: { shortLabel: "Masters Worlds", order: 42 },
  WEIGHTLIFTING_AFRICA: { shortLabel: "African Championships", order: 43 },
  WEIGHTLIFTING_ASIA: { shortLabel: "Asian Championships", order: 44 },
  WEIGHTLIFTING_EUROPE: { shortLabel: "European Championships", order: 45 },
  WEIGHTLIFTING_OCEANIA: { shortLabel: "Oceania Championships", order: 46 },
  WEIGHTLIFTING_PAN_AMERICA: { shortLabel: "Pan-American Championships", order: 47 },
  WEIGHTLIFTING_COMMONWEALTH_GAMES: { shortLabel: "Commonwealth Games", order: 48 },
  WEIGHTLIFTING_ASIAN_GAMES: { shortLabel: "Asian Games", order: 49 },
  WEIGHTLIFTING_PAN_AM_GAMES: { shortLabel: "Pan Am Games", order: 50 },
  GOLF_MAJORS_MEN: { shortLabel: "Golf · men's majors", order: 36 },
  GOLF_MAJORS_WOMEN: { shortLabel: "Golf · women's majors", order: 37 },
  NFL: { shortLabel: "NFL", order: 0 },
  NBA: { shortLabel: "NBA", order: 1 },
  MLB: { shortLabel: "MLB", order: 2 },
  NHL: { shortLabel: "NHL", order: 3 },
  F1: { shortLabel: "F1", order: 4 },
  NASCAR_CUP: { shortLabel: "NASCAR", order: 5 },
  INDYCAR: { shortLabel: "INDYCAR", order: 6 },
  FIFA_WORLD_CUP: { shortLabel: "FIFA", order: 7 },
  UEFA_CHAMPIONS_LEAGUE: {
    shortLabel: "Champions League",
    order: 8,
  },
  IFSC_WORLD_CUP: { shortLabel: "World Climbing", order: 9 },
  IFSC_PARA_WORLD_CUP: {
    shortLabel: "PARA",
    order: 10,
  },
  IFSC_YOUTH_WORLD_CHAMPIONSHIPS: {
    shortLabel: "YOUTH",
    order: 11,
  },
  PGA_TOUR: { shortLabel: "PGA Tour", order: 38 },
  LPGA_TOUR: { shortLabel: "LPGA Tour", order: 39 },
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
  { name: "American football", leagues: ["NFL"] },
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

const CONTINENTAL_CHAMPIONSHIPS: Record<string, string[]> = {
  Climbing: ["CLIMBING_EUROPE", "CLIMBING_ASIA", "CLIMBING_AFRICA", "CLIMBING_OCEANIA", "CLIMBING_PAN_AMERICA"],
  Weightlifting: ["WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE",
    "WEIGHTLIFTING_OCEANIA", "WEIGHTLIFTING_PAN_AMERICA"],
};

export function interestChoices(group: { name: string; leagues: string[] }) {
  const continental = group.leagues.filter((league) => CONTINENTAL_CHAMPIONSHIPS[group.name]?.includes(league));
  return group.leagues.flatMap((league) => {
    if (continental.includes(league)) return league === continental[0]
      ? [{ name: "Continental championships", leagues: continental }] : [];
    return [{ name: CLIMBING_COMPETITIONS[league] || leagueVisual(league).shortLabel, leagues: [league] }];
  });
}

export function interestGroups(leagues: LeagueInterest[]) {
  const available = new Map(interestLeagues(leagues).map((league) => [league.value, league]));
  const groups = SPORT_GROUPS.map((group) => ({
    name: group.name,
    leagues: group.leagues.filter((league) => available.delete(league)),
  }));
  const other: string[] = [];
  for (const { value, sport } of available.values()) {
    const category = categoryForLeague(value, sport);
    const group = groups.find(({ name }) => CATEGORY_KEYS[name as keyof typeof CATEGORY_KEYS] === category);
    if (group) group.leagues.push(value);
    else other.push(value);
  }
  groups.push({ name: "Miscellaneous", leagues: other });
  return groups.filter((group) => group.leagues.length);
}

export function toggleInterestGroup(selected: string[], leagues: string[]) {
  const allSelected = leagues.every((league) => selected.includes(league));
  return allSelected
    ? selected.filter((league) => !leagues.includes(league))
    : [...new Set([...selected, ...leagues])];
}
export const CATEGORY_KEYS = {
  Soccer: "soccer", Motorsports: "motorsport", "American football": "american-football",
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
  if (["GOLF_MAJORS_MEN", "GOLF_MAJORS_WOMEN"].includes(league)) return "golf";
  return SPORT_CATEGORIES[sport?.toLowerCase() || ""] || null;
}

export function leagueVisual(league: string, sport?: string) {
  const category = categoryForLeague(league, sport);
  return {
    ...(LEAGUE_META[league] || {
      shortLabel: CLIMBING_COMPETITIONS[league] || league.replaceAll("_", " "),
      order: 99,
    }),
    className: category ? `category-${category}` : "category-unknown",
  };
}

