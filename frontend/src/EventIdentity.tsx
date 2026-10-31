import { hostCountry, nationalTeamCountries, type Country } from "./countries";
import { categoryForLeague, NO_FLAG_LEAGUES, type CategoryKey } from "./calendar-helpers";
import { SPORT_ICONS } from "./sport-icons";
import type { EventCard } from "./types";

export function SportIcon({ league = "", sport, category }: {
  league?: string; sport?: string; category?: CategoryKey;
}) {
  const key = category || categoryForLeague(league, sport);
  return key ? <svg className="sport-icon" data-sport={key} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d={SPORT_ICONS[key]} />
  </svg> : null;
}

export function CountryFlag({ country, label }: { country: Country; label: string }) {
  return <span className="country-flag" role="img" aria-label={label} title={label}>{country.flag}</span>;
}

export function EventFlags({ event }: { event: EventCard }) {
  if (NO_FLAG_LEAGUES.has(event.league)) return null;
  const host = hostCountry(event);
  const teams = nationalTeamCountries(event.participants);
  if (!host && !teams.length) return null;
  return <span className="event-flags">
    {host && <CountryFlag country={host} label={`Host country: ${host.name}`} />}
    {teams.map(({ participant, country }, index) => <CountryFlag key={`${index}:${participant.name}`}
      country={country} label={`${participant.name}: ${country.name}`} />)}
  </span>;
}
