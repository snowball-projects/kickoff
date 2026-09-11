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
  CHAMPIONSHIP: { shortLabel: "Championship", className: "league-epl", order: 25 },
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
  NFL: { shortLabel: "NFL", className: "league-nfl", order: 0 },
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
  PGA_TOUR: { shortLabel: "PGA", className: "league-pga", order: 12 },
};
export function leagueVisual(league: string) {
  return (
    LEAGUE_META[league] || {
      shortLabel: league.replaceAll("_", " "),
      className: "league-generic",
      order: 99,
    }
  );
}
