import { useLayoutEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import { leagueVisual, pillCountry } from "./calendar-helpers";
import { SportIcon } from "./EventIdentity";
import { isGolf } from "./golf";
import NflMatchups, { hasNflTeams, nflMatchupName } from "./NflMatchups";
import type { EventCard } from "./types";

export default function EventPill({ items, children, calendarView, className = "", ...props }: {
  items: EventCard[];
  calendarView?: "month" | "day";
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const event = items[0];
  const country = pillCountry(items);
  const text = useRef<HTMLSpanElement>(null);
  const [truncated, setTruncated] = useState(false);
  const label = children || (items.length === 1 && isGolf(event) ? event.title : leagueVisual(event.league, event.sport).shortLabel);
  const nfl = event.league === "NFL" && items.some(hasNflTeams) && calendarView;
  useLayoutEffect(() => {
    const element = text.current;
    if (!element) return;
    const measure = () => setTruncated(element.scrollWidth > element.clientWidth);
    const observer = new ResizeObserver(measure);
    observer.observe(element); measure();
    return () => observer.disconnect();
  }, [label, nfl]);
  const matchupNames = nfl ? items.map(nflMatchupName).join("; ") : "";
  const accessibleName = nfl && !props["aria-label"]?.includes(matchupNames)
    ? [props["aria-label"], matchupNames].filter(Boolean).join(", ") : props["aria-label"];
  return <button {...props} aria-label={accessibleName} className={`event-pill ${leagueVisual(event.league, event.sport).className} ${className}`}>
    <SportIcon league={event.league} sport={event.sport} />
    {nfl ? <NflMatchups items={items} view={nfl} /> : <span ref={text} className={`pill-text${truncated ? " truncated" : ""}`}>{label}</span>}
    {country && <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>}
  </button>;
}
