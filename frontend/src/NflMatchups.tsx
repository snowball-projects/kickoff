import { useLayoutEffect, useRef, useState } from "react";
import NflLogo, { hasNflLogo } from "./NflLogo";
import type { EventCard } from "./types";

function teams(event: EventCard) {
  return [event.away_participant?.name || event.away_participant_name,
    event.home_participant?.name || event.home_participant_name];
}

export function nflMatchupName(event: EventCard) {
  const [away, home] = teams(event);
  return away && home ? `${away} at ${home}` : event.title;
}

export function hasNflTeams(event: EventCard) { return teams(event).every(Boolean); }

function Matchup({ event, names = false }: { event: EventCard; names?: boolean }) {
  const [away, home] = teams(event);
  if (!away || !home) return <span className="nfl-matchup-name">{event.title}</span>;
  return <>{[away, home].map((name, index) => <span className="nfl-calendar-team" key={index}>
    {index === 1 && names && <span className="nfl-at">at</span>}
    <NflLogo name={name} league="NFL" />
    {(names || !hasNflLogo(name)) && <span className="nfl-team-name">{hasNflLogo(name)
      ? (index === 0 ? event.away_participant?.short_name : event.home_participant?.short_name) || name : name}</span>}
  </span>)}</>;
}

export default function NflMatchups({ items, view }: { items: EventCard[]; view: "month" | "day" }) {
  const root = useRef<HTMLSpanElement>(null);
  const measurements = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(0);
  useLayoutEffect(() => {
    if (view !== "month") return;
    const element = root.current!;
    const measure = () => {
      const samples = measurements.current!;
      const widths = [...samples.querySelectorAll<HTMLElement>(".nfl-matchup")].map((pair) => pair.getBoundingClientRect().width);
      const counts = [...samples.querySelectorAll<HTMLElement>(".nfl-more")];
      const available = element.clientWidth;
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
  }, [items, view]);
  return view === "day" ? <span className="nfl-day-matchups" aria-hidden="true">
    {items.map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} names /></span>)}
  </span> : <>
    <span className="nfl-phone-label" aria-hidden="true">NFL</span>
    <span className="nfl-month-matchups" ref={root} aria-hidden="true">
      {items.slice(0, shown).map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} /></span>)}
      {shown < items.length && <span className="nfl-more">+{items.length - shown}</span>}
      <span className="nfl-measurements" ref={measurements}>
        {items.map((event) => <span className="nfl-matchup" key={event.event_id}><Matchup event={event} /></span>)}
        {items.map((_, index) => <span className="nfl-more" key={index}>+{index + 1}</span>)}
      </span>
    </span>
  </>;
}
