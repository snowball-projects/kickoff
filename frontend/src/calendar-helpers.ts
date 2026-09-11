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
  IFSC_WORLD_CUP: { shortLabel: "IFSC", className: "league-ifsc", order: 9 },
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
