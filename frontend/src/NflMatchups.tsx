import { participantRoles } from "./participants";
import { useState } from "react";
import TeamLogo from "./TeamLogo";
import type { EventCard } from "./types";

export function nflMatchupName(event: EventCard) {
  const { away, home } = participantRoles(event);
  return away && home ? `${away.name} at ${home.name}` : event.title;
}

export function hasNflTeams(event: EventCard) {
  const { away, home } = participantRoles(event);
  return Boolean(away && home);
}

function Matchup({ event, failed, onFailure }: {
  event: EventCard; failed: ReadonlySet<string>; onFailure: (url: string) => void;
}) {
  const { away, home } = participantRoles(event);
  if (!away || !home) return <span className="nfl-matchup-name">{event.title}</span>;
  return <>{[away, home].map((team, index) => <span className="nfl-calendar-team" key={index}>
    {team.logo_url && !failed.has(team.logo_url) && <TeamLogo participant={team} onError={() => onFailure(team.logo_url!)} />}
    <span className="nfl-team-name">{team.logo_url ? team.short_name || team.name : team.name}</span>
  </span>)}</>;
}

export default function NflMatchups({ items }: { items: EventCard[] }) {
  const [failed, setFailed] = useState<ReadonlySet<string>>(() => new Set());
  const onFailure = (url: string) => setFailed((current) => current.has(url) ? current : new Set([...current, url]));
  return <span className="nfl-day-matchups" aria-hidden="true">
    {items.map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} failed={failed} onFailure={onFailure} /></span>)}
  </span>;
}
