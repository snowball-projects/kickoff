import type { ApiParticipant, EventCard } from "./types";

const TEAM_SPORTS = new Set(["football", "basketball", "baseball", "hockey", "soccer", "rugby", "cricket"]);
const AWAY_FIRST = new Set(["football", "basketball", "baseball", "hockey"]);

export function orderedTeams(event: Pick<EventCard, "sport" | "participants">): ApiParticipant[] {
  if (!TEAM_SPORTS.has(event.sport)) return [];
  const teams = event.participants.filter(team => ["team", "club", "national_team"].includes(team.entity_type));
  const home = teams.find(team => team.role === "home"), away = teams.find(team => team.role === "away");
  if (teams.length === 2 && home && away) return AWAY_FIRST.has(event.sport) ? [away, home] : [home, away];
  return teams;
}

export type TeamOutcome = { winner: boolean; advances: boolean };

export function teamOutcome(team: ApiParticipant, opponent: ApiParticipant | null | undefined, sport: string): TeamOutcome {
  const higher = team.final_score != null && opponent?.final_score != null && team.final_score > opponent.final_score;
  const unflagged = team.result_winner === undefined && opponent?.result_winner === undefined;
  const aggregateOrShootout = [team, opponent].some(side => side?.aggregate_score != null || side?.shootout_score != null);
  const scoreDecides = TEAM_SPORTS.has(sport) && sport !== "cricket" && unflagged && !aggregateOrShootout;
  return {
    winner: higher && (team.result_winner === true || scoreDecides),
    advances: team.result_advance === true,
  };
}

export function completedTeams(event: Pick<EventCard, "sport" | "participants" | "status">) {
  const teams = orderedTeams(event);
  return event.status === "finished" && teams.length === 2 && teams.every(team => team.final_score != null) ? teams : [];
}
