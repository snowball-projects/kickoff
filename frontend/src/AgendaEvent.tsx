import { participantRoles } from "./participants";
import { useState } from "react";
import { agendaEventText } from "./agenda-title";
import { eventTimeLabel } from "./date-utils";
import { isGolf, leaderboardId } from "./golf";
import GolfLeaderboard from "./GolfLeaderboard";
import TeamLogo from "./TeamLogo";
import { EventFlags } from "./EventIdentity";
import type { ApiParticipant, EventCard } from "./types";

function Team({ team }: { team: ApiParticipant }) {
  return <span className="agenda-team"><TeamLogo participant={team} />
    <span className="team-name" title={team.name}>{team.short_name || team.name}</span>
    {team.record && <span className="team-record">{team.record}</span>}
  </span>;
}

export default function AgendaEvent({ event, date, today, timezone, active, upcoming, onOpen }: {
  event: EventCard; date: string; today: string; timezone: string; active: boolean; upcoming: boolean; onOpen: () => void;
}) {
  const [golfStatus, setGolfStatus] = useState<string | null>(null);
  const time = eventTimeLabel(event, timezone);
  const { home, away } = participantRoles(event);
  const teams = (home || away) && ["football", "basketball", "hockey", "baseball", "soccer", "rugby"].includes(event.sport);
  const scores = event.status === "finished" && home?.final_score != null && away?.final_score != null;
  const partial = Boolean(home) !== Boolean(away);
  const round = partial ? event.round_or_stage || event.week_label : event.week_label || event.round_or_stage;
  const golf = isGolf(event), id = !upcoming && leaderboardId(event);
  const { title, session } = agendaEventText(event, round);
  return <article className="agenda-row" id={`agenda-${date}-${event.event_id}`}>
    <button className={`agenda-open ${teams ? "agenda-match" : "agenda-centered"}`} onClick={onOpen} aria-label={!title && !teams ? event.title : undefined}>
      {teams ? <>
        {away ? <Team team={away} /> : <span />}
        <span className="agenda-match-center">
          {round && <span className="agenda-round">{round}</span>}
          {scores && away && home ? <><span className="agenda-result">{away.final_score}–{home.final_score}</span><span className="agenda-round">Final</span></>
            : event.status !== "finished" && time && <span className="agenda-time">{time}</span>}
        </span>
        {home ? <Team team={home} /> : <span />}
      </> : <>
        <span className="agenda-title">{title}<EventFlags event={event} /></span>
        {golf ? <span className="agenda-round">{[round, !upcoming && golfStatus].filter(Boolean).join(" · ")}</span>
          : <>{session && <span className="agenda-round">{session}</span>}{time && <span className="agenda-time">{time}</span>}</>}
      </>}
    </button>
    {id && <GolfLeaderboard id={id} date={date} today={today} timezone={timezone} active={active}
      onStatus={setGolfStatus} caption="Top 5 · ESPN" />}
  </article>;
}
