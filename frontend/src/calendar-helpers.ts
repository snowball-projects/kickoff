const LEAGUE_META: Record<
  string,
  { shortLabel: string; className: string; order: number }
> = {
  EPL: { shortLabel: "Premier League", className: "league-epl", order: 20 },
  BUNDESLIGA: {
    shortLabel: "Bundesliga",
    className: "league-bundesliga",
    order: 21,
  },
  LA_LIGA: { shortLabel: "La Liga", className: "league-laliga", order: 22 },
  SERIE_A: { shortLabel: "Serie A", className: "league-seriea", order: 23 },
  LIGUE_1: { shortLabel: "Ligue 1", className: "league-ligue1", order: 24 },
  CHAMPIONSHIP: { shortLabel: "EFL Championship · England", className: "league-epl", order: 25 },
  EREDIVISIE: { shortLabel: "Eredivisie", className: "league-generic", order: 26 },
  PRIMEIRA_LIGA: { shortLabel: "Primeira Liga", className: "league-generic", order: 27 },
  BRASILEIRAO: { shortLabel: "Brazil Série A", className: "league-generic", order: 28 },
  UFC: { shortLabel: "UFC", className: "league-generic", order: 30 },
  PFL: { shortLabel: "PFL", className: "league-generic", order: 31 },
  RIZIN: { shortLabel: "RIZIN", className: "league-generic", order: 32 },
  ONE: { shortLabel: "ONE · combat sports", className: "league-generic", order: 33 },
  BOXING_MAJOR: { shortLabel: "Boxing · selected unifications", className: "league-generic", order: 34 },
  IWF_WORLDS: { shortLabel: "IWF Worlds", className: "league-generic", order: 35 },
  GOLF_MAJORS_MEN: { shortLabel: "Golf · men's majors", className: "league-pga", order: 36 },
  GOLF_MAJORS_WOMEN: { shortLabel: "Golf · women's majors", className: "league-pga", order: 37 },
  NFL: { shortLabel: "NFL · selected games", className: "league-nfl", order: 0 },
  NBA: { shortLabel: "NBA", className: "league-nba", order: 1 },
  MLB: { shortLabel: "MLB", className: "league-mlb", order: 2 },
  NHL: { shortLabel: "NHL", className: "league-nhl", order: 3 },
  F1: { shortLabel: "F1", className: "league-f1", order: 4 },
  NASCAR_CUP: { shortLabel: "NASCAR", className: "league-nascar", order: 5 },
  INDYCAR: { shortLabel: "INDYCAR", className: "league-indycar", order: 6 },
  FIFA_WORLD_CUP: { shortLabel: "FIFA", className: "league-fifa", order: 7 },
  UEFA_CHAMPIONS_LEAGUE: {
    shortLabel: "UCL",
    className: "league-ucl",
    order: 8,
  },
  IFSC_WORLD_CUP: { shortLabel: "World Climbing", className: "league-ifsc", order: 9 },
  IFSC_PARA_WORLD_CUP: {
    shortLabel: "PARA",
    className: "league-ifsc-para",
    order: 10,
  },
  IFSC_YOUTH_WORLD_CHAMPIONSHIPS: {
    shortLabel: "YOUTH",
    className: "league-ifsc-youth",
    order: 11,
  },
  PGA_TOUR: { shortLabel: "PGA Tour · selected dates", className: "league-pga", order: 38 },
  LPGA_TOUR: { shortLabel: "LPGA Tour · final dates", className: "league-pga", order: 39 },
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

const SPORT_GROUPS = [
  { name: "Soccer", leagues: [...Object.keys(SOCCER_COUNTRIES), "FIFA_WORLD_CUP", "UEFA_CHAMPIONS_LEAGUE"] },
  { name: "Motorsports", leagues: ["F1", "NASCAR_CUP", "INDYCAR"] },
  { name: "American football", leagues: ["NFL"] },
  { name: "Combat sports", leagues: ["UFC", "PFL", "RIZIN", "ONE", "BOXING_MAJOR"] },
  { name: "Golf", leagues: ["GOLF_MAJORS_MEN", "GOLF_MAJORS_WOMEN", "PGA_TOUR", "LPGA_TOUR"] },
];

export function interestGroups(leagues: { value: string }[]) {
  const available = new Set(leagues.map((league) => league.value));
  const groups = SPORT_GROUPS.map((group) => ({
    name: group.name,
    leagues: group.leagues.filter((league) => available.delete(league)),
  }));
  // Preserve selection access for newly published competitions as well.
  groups.push({ name: "Miscellaneous", leagues: [...available] });
  return groups.filter((group) => group.leagues.length);
}

export function toggleInterestGroup(selected: string[], leagues: string[]) {
  const allSelected = leagues.every((league) => selected.includes(league));
  return allSelected
    ? selected.filter((league) => !leagues.includes(league))
    : [...new Set([...selected, ...leagues])];
}
export function leagueVisual(league: string) {
  return (
    LEAGUE_META[league] || {
      shortLabel: league.replaceAll("_", " "),
      className: "league-generic",
      order: 99,
    }
  );
}
