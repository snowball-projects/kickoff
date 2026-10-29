import type { ButtonHTMLAttributes } from "react";
import { commonHostCountry } from "./countries";
import { leagueVisual, SOCCER_COUNTRIES } from "./calendar-helpers";
import { SportIcon } from "./EventIdentity";
import type { EventCard } from "./types";

export default function EventPill({ items, children, className = "", ...props }: {
  items: EventCard[];
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const event = items[0];
  const country = commonHostCountry(items) || SOCCER_COUNTRIES[event.league];
  return <button {...props} className={`event-pill ${leagueVisual(event.league, event.sport).className} ${className}`}>
    {country ? <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>
      : <SportIcon league={event.league} sport={event.sport} />}
    <span className="pill-text">{children || leagueVisual(event.league, event.sport).shortLabel}</span>
  </button>;
}
