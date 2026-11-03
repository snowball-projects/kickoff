import { useLayoutEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import { leagueVisual, pillCountry } from "./calendar-helpers";
import { SportIcon } from "./EventIdentity";
import MonthMatchups from "./MonthMatchups";
import { desktopMonthGames, monthMatchupName, orderedTeams } from "./month-matchups";
import { isGolf } from "./golf";
import NflMatchups, { hasNflTeams, nflMatchupName } from "./NflMatchups";
import type { EventCard } from "./types";

export default function EventPill({ items, children, calendarView, displayDate, displayTimezone, className = "", ...props }: {
  items: EventCard[];
  calendarView?: "month" | "day";
  displayDate?: string;
  displayTimezone?: string;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const event = items[0];
  const country = pillCountry(items);
  const text = useRef<HTMLSpanElement>(null);
  const [truncated, setTruncated] = useState(false);
  const visual = leagueVisual(event.league, event.sport);
  const label = children || (isGolf(event) && (calendarView === "month" || items.length === 1)
    ? items.map((item) => item.title).join("; ") : visual.shortLabel);
  const monthGames = calendarView === "month" ? desktopMonthGames(items, displayDate!, displayTimezone!) : [];
  const single = calendarView === "month" && items.length === 1 && orderedTeams(event).length === 2 ? event : undefined;
  const desktopLabel = monthGames.length ? visual.code || visual.shortLabel : label;
  const code = calendarView === "month" ? visual.code : undefined;
  const nfl = event.league === "NFL" && items.some(hasNflTeams) && calendarView === "day";
  useLayoutEffect(() => {
    const element = text.current;
    if (!element) return;
    const measure = () => setTruncated(element.scrollWidth > element.clientWidth);
    const observer = new ResizeObserver(measure);
    observer.observe(element); measure();
    return () => observer.disconnect();
  }, [desktopLabel, code, nfl]);
  const monthNames = single ? [single] : monthGames;
  const matchupNames = nfl ? items.map(nflMatchupName).join("; ") : monthNames.map(monthMatchupName).join("; ");
  const accessibleName = matchupNames && !props["aria-label"]?.includes(matchupNames)
    ? [props["aria-label"], matchupNames].filter(Boolean).join(", ") : props["aria-label"];
  return <button {...props} aria-label={accessibleName} className={`event-pill ${visual.className} ${single ? "month-single" : ""} ${className}`}>
    <SportIcon league={event.league} sport={event.sport} />
    {nfl ? <NflMatchups items={items} /> : <span ref={text} className={`pill-text${truncated ? " truncated" : ""}`}>{code ? <><span className="pill-label">{desktopLabel}</span><span className="pill-code" aria-hidden="true">{code}</span></> : desktopLabel}</span>}
    {calendarView === "month" && <MonthMatchups items={monthGames} single={single} />}
    {country && <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>}
  </button>;
}
