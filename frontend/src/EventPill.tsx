import { useLayoutEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import { leagueVisual, pillCountry } from "./calendar-helpers";
import { SportIcon } from "./EventIdentity";
import { isGolf } from "./golf";
import type { EventCard } from "./types";

export default function EventPill({ items, children, className = "", ...props }: {
  items: EventCard[];
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const event = items[0];
  const country = pillCountry(items);
  const text = useRef<HTMLSpanElement>(null);
  const [truncated, setTruncated] = useState(false);
  const label = children || (items.length === 1 && isGolf(event) ? event.title : leagueVisual(event.league, event.sport).shortLabel);
  useLayoutEffect(() => {
    const element = text.current!;
    const measure = () => setTruncated(element.scrollWidth > element.clientWidth);
    const observer = new ResizeObserver(measure);
    observer.observe(element); measure();
    return () => observer.disconnect();
  }, [label]);
  return <button {...props} className={`event-pill ${leagueVisual(event.league, event.sport).className} ${className}`}>
    <SportIcon league={event.league} sport={event.sport} />
    <span ref={text} className={`pill-text${truncated ? " truncated" : ""}`}>{label}</span>
    {country && <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>}
  </button>;
}
