import { participantRoles } from "./participants";
import { useState } from "react";
import { teamOutcome } from "./team-results";
import type { TeamOutcome } from "./team-results";
import { resultSummary } from "./result-format";
import "./results.css";
import { agendaEventText } from "./agenda-title";
import { eventTimeLabel } from "./date-utils";
import { isGolf, leaderboardId } from "./golf";
import GolfLeaderboard from "./GolfLeaderboard";
import TeamLogo from "./TeamLogo";
import { EventFlags } from "./EventIdentity";
import type { ApiParticipant, EventCard } from "./types";

function Team({ team, outcome }: { team: ApiParticipant; outcome?: TeamOutcome }) {
  return <span className={`agenda-team ${outcome?.winner ? "agenda-team-winner" : ""}`}><TeamLogo participant={team} />
    <span className="team-name" title={team.name}>{team.short_name || team.name}</span>
    {outcome?.winner && <span className="agenda-team-outcome">Winner</span>}
    {outcome?.advances && <span className="agenda-team-outcome">Advances</span>}
    {team.record && <span className="team-record">{team.record}</span>}
  </span>;
}

export default function AgendaEvent({ event, date, today, timezone, active, upcoming, onOpen }: {
  event: EventCard; date: string; today: string; timezone: string; active: boolean; upcoming: boolean; onOpen: () => void;
}) {
  const [golfStatus, setGolfStatus] = useState<string | null>(null);
  const time = eventTimeLabel(event, timezone);
  const { home, away } = participantRoles(event);
  const teams = Boolean(home || away) && ["football", "basketball", "hockey", "baseball", "soccer", "rugby"].includes(event.sport);
  const left = away, right = home;
  const summary = resultSummary(event.result);
  const scores = event.status === "finished" && left?.final_score != null && right?.final_score != null;
  const partial = Boolean(home) !== Boolean(away);
  const round = partial ? event.round_or_stage || event.week_label : event.week_label || event.round_or_stage;
  const golf = isGolf(event), id = !upcoming && leaderboardId(event);
  const { title, session } = agendaEventText(event, round);
  return <article className="agenda-row" id={`agenda-${date}-${event.event_id}`}>
    <button className={`agenda-open ${teams ? "agenda-match" : "agenda-centered"}`} onClick={onOpen} aria-label={!title && !teams ? event.title : undefined}>
      {teams ? <>
        {left ? <Team team={left} outcome={event.status === "finished" ? teamOutcome(left, right, event.sport) : undefined} /> : <span />}
        <span className="agenda-match-center">
          {round && <span className="agenda-round">{round}</span>}
          {scores && left && right ? <><span className="agenda-result">{left.final_score}–{right.final_score}</span><span className="agenda-round">Final</span>
            {left.aggregate_score != null && right.aggregate_score != null && <span className="agenda-round">Aggregate {left.aggregate_score}–{right.aggregate_score}</span>}
            {left.shootout_score != null && right.shootout_score != null && <span className="agenda-round">Shootout {left.shootout_score}–{right.shootout_score}</span>}</>
            : event.status !== "finished" && time && <span className="agenda-time">{time}</span>}
        </span>
        {right ? <Team team={right} outcome={event.status === "finished" ? teamOutcome(right, left, event.sport) : undefined} /> : <span />}
      </> : <>
        <span className="agenda-title">{title}<EventFlags event={event} /></span>
        {golf ? <span className="agenda-round">{[round, !upcoming && golfStatus].filter(Boolean).join(" · ")}</span>
          : <>{session && <span className="agenda-round">{session}</span>}{time && <span className="agenda-time">{time}</span>}</>}
      </>}
      {summary && <span className="agenda-result-summary">{summary}</span>}
    </button>
    {id && <GolfLeaderboard id={id} date={date} today={today} timezone={timezone} active={active}
      onStatus={setGolfStatus} caption="Top 5 · ESPN" />}
  </article>;
}
