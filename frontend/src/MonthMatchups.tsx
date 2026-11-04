import { useLayoutEffect, useRef, useState } from "react";
import { orderedTeams } from "./month-matchups";
import TeamLogo from "./TeamLogo";
import type { EventCard } from "./types";

function Matchup({ event, measurement = false, failed, onFailure }: {
  event: EventCard; measurement?: boolean; failed: ReadonlySet<string>; onFailure: (url: string) => void;
}) {
  const teams = orderedTeams(event);
  if (teams.length !== 2) return <span className="month-source-title">{event.title}</span>;
  return <>{teams.map((team, index) => <span className="month-calendar-team" key={index}>
    {team.logo_url && !failed.has(team.logo_url) && <TeamLogo participant={team} load={!measurement} onError={() => onFailure(team.logo_url!)} />}
    <span className="month-team-fallback">{team.short_name || team.name}</span>
  </span>)}</>;
}

export default function MonthMatchups({ items, single, failed, onFailure }: {
  items: EventCard[]; single?: EventCard; failed: ReadonlySet<string>; onFailure: (url: string) => void;
}) {
  const root = useRef<HTMLSpanElement>(null);
  const measurements = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(0);
  useLayoutEffect(() => {
    const element = root.current;
    if (!element || !items.length) return;
    const measure = () => {
      const samples = measurements.current!;
      const widths = [...samples.querySelectorAll<HTMLElement>(".month-pair")].map((pair) => pair.getBoundingClientRect().width);
      const counts = [...samples.querySelectorAll<HTMLElement>(".month-more")];
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
    observer.observe(measurements.current!);
    measure();
    return () => observer.disconnect();
  }, [items, failed]);
  return <>
    {single && <span className="month-phone-single" aria-hidden="true"><span className="month-pair">
      <Matchup event={single} failed={failed} onFailure={onFailure} />
    </span></span>}
    {items.length > 0 && <span className="month-desktop-pairs" ref={root} aria-hidden="true">
      {items.slice(0, shown).map((event) => <span className="month-pair" data-matchup-id={event.event_id} key={event.event_id}>
        <Matchup event={event} failed={failed} onFailure={onFailure} />
      </span>)}
      {shown < items.length && <span className="month-more">+{items.length - shown}</span>}
      <span className="month-measurements" ref={measurements}>
        {items.map((event) => <span className="month-pair" key={event.event_id}>
          <Matchup event={event} measurement failed={failed} onFailure={onFailure} />
        </span>)}
        {items.map((_, index) => <span className="month-more" key={index}>+{index + 1}</span>)}
      </span>
    </span>}
  </>;
}
