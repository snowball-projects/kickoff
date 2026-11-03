import { categoryForLeague } from "./calendar-helpers";
import { eventInstant, todayIso } from "./date-utils";
import { participantRoles } from "./participants";
import type { EventCard } from "./types";

const TEAM_SPORTS = new Set(["soccer", "american-football", "basketball", "baseball", "hockey", "rugby", "cricket"]);
const AWAY_FIRST = new Set(["american-football", "basketball", "baseball", "hockey"]);

export function isTeamGame(event: EventCard) {
  return TEAM_SPORTS.has(categoryForLeague(event.league, event.sport) || "");
}

export function orderedTeams(event: EventCard) {
  if (!isTeamGame(event)) return [];
  const { away, home } = participantRoles(event);
  if (away && home) return AWAY_FIRST.has(categoryForLeague(event.league, event.sport)!) ? [away, home] : [home, away];
  return event.participants.filter((participant) => ["team", "club", "national_team"].includes(participant.entity_type));
}

export function monthMatchupName(event: EventCard) {
  const { away, home } = participantRoles(event);
  if (!away || !home) return [event.title, ...orderedTeams(event).map((team) => team.name)
    .filter((name) => !event.title.includes(name))].join("; ");
  return AWAY_FIRST.has(categoryForLeague(event.league, event.sport)!)
    ? `${away.name} at ${home.name}` : `${home.name} vs ${away.name}`;
}

export function desktopMonthGames(items: EventCard[], displayDate: string, timezone: string) {
  if (!items.length || !isTeamGame(items[0])) return [];
  // The cell date has already been converted to the viewer's display timezone.
  if (items[0].league === "NFL" && new Date(`${displayDate}T12:00:00Z`).getUTCDay() === 0) {
    const times = items.map(eventInstant);
    // An unknown kickoff, source-only date, or tied last start cannot identify the last game.
    if (times.some((time) => time === null || todayIso(timezone, new Date(time)) !== displayDate)) return [];
    const last = Math.max(...times as number[]);
    const games = items.filter((_, index) => times[index] === last);
    return games.length === 1 ? games : [];
  }
  return items.length <= 3 && items.some((event) => orderedTeams(event).some((team) => team.logo_url)) ? items : [];
}
