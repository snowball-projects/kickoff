import { participantRoles } from "./participants";
import { useLayoutEffect, useRef, useState } from "react";
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

function Matchup({ event, names = false, measurement = false, failed, onFailure }: {
  event: EventCard; names?: boolean; measurement?: boolean; failed: ReadonlySet<string>; onFailure: (url: string) => void;
}) {
  const { away, home } = participantRoles(event);
  if (!away || !home) return <span className="nfl-matchup-name">{event.title}</span>;
  return <>{[away, home].map((team, index) => <span className="nfl-calendar-team" key={index}>
    {team.logo_url && !failed.has(team.logo_url) && <TeamLogo participant={team} load={!measurement} onError={() => onFailure(team.logo_url!)} />}
    <span className={`nfl-team-name${names ? "" : " nfl-logo-fallback"}`}>{team.logo_url ? team.short_name || team.name : team.name}</span>
  </span>)}</>;
}

export default function NflMatchups({ items, view }: { items: EventCard[]; view: "month" | "day" }) {
  const root = useRef<HTMLSpanElement>(null);
  const measurements = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(0);
  const [failed, setFailed] = useState<ReadonlySet<string>>(() => new Set());
  const onFailure = (url: string) => setFailed((current) => current.has(url) ? current : new Set([...current, url]));
  useLayoutEffect(() => {
    if (view !== "month") return;
    const element = root.current!;
    const measure = () => {
      const samples = measurements.current!;
      const widths = [...samples.querySelectorAll<HTMLElement>(".nfl-matchup")].map((pair) => pair.getBoundingClientRect().width);
      const counts = [...samples.querySelectorAll<HTMLElement>(".nfl-more")];
      const available = element.getBoundingClientRect().width;
      const gap = parseFloat(getComputedStyle(element).columnGap) || 0;
      let width = 0, fit = 0;
      for (let count = 1; count <= items.length; count++) {
        width += widths[count - 1] + (count > 1 ? gap : 0);
        const remaining = items.length - count;
        const total = width + (remaining ? gap + counts[remaining - 1].getBoundingClientRect().width : 0);
        if (total <= available) fit = count;
      }
      setShown(fit);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    // Font changes affect the fallback names and the omitted-matchup count.
    observer.observe(measurements.current!);
    measure();
    return () => observer.disconnect();
  }, [items, view, failed]);
  return view === "day" ? <span className="nfl-day-matchups" aria-hidden="true">
    {items.map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} names failed={failed} onFailure={onFailure} /></span>)}
  </span> : <>
    <span className="nfl-phone-label" aria-hidden="true">NFL</span>
    <span className="nfl-month-matchups" ref={root} aria-hidden="true">
      {items.slice(0, shown).map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} failed={failed} onFailure={onFailure} /></span>)}
      {shown < items.length && <span className="nfl-more">+{items.length - shown}</span>}
      <span className="nfl-measurements" ref={measurements}>
        {items.map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} measurement failed={failed} onFailure={onFailure} /></span>)}
        {items.map((_, index) => <span className="nfl-more" key={index}>+{index + 1}</span>)}
      </span>
    </span>
  </>;
}
