import type { ButtonHTMLAttributes } from "react";
import { leagueVisual, pillCountry } from "./calendar-helpers";
import { SportIcon } from "./EventIdentity";
import { isGolf } from "./golf";
import type { EventCard } from "./types";

export default function EventPill({ items, children, className = "", ...props }: {
  items: EventCard[];
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const event = items[0];
  const country = pillCountry(items);
  return <button {...props} className={`event-pill ${leagueVisual(event.league, event.sport).className} ${className}`}>
    <SportIcon league={event.league} sport={event.sport} />
    <span className="pill-text">{children || (items.length === 1 && isGolf(event) ? event.title : leagueVisual(event.league, event.sport).shortLabel)}</span>
    {country && <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>}
  </button>;
}
