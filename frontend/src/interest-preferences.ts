import type { EventDetail, FilterState } from "./types";

export const INTERESTS_KEY = "kickoff.interests.v2";
export const GOLF_TOURS = ["PGA_TOUR", "LPGA_TOUR"] as const;
export type GolfView = "majors_only" | "full_tour";
export const GENDERS = ["Men", "Women"] as const;
export const CLIMBING_DISCIPLINES = ["Boulder", "Lead", "Speed"] as const;
export type SessionInterests = {
  climbing: { genders: string[]; disciplines: string[] };
  weightlifting: { genders: string[] };
};
export type InterestPreferences = SessionInterests & {
  leagues: string[] | null;
  golf_views: Record<typeof GOLF_TOURS[number], GolfView>;
  motorsport_view: "race_only" | "full_weekend";
};
export function defaultPreferences(): InterestPreferences {
  return { leagues: null, golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" },
    motorsport_view: "race_only",
    climbing: { genders: [...GENDERS], disciplines: [...CLIMBING_DISCIPLINES] },
    weightlifting: { genders: [...GENDERS] } };
}
export function interestLeague(league: string) {
  return league === "GOLF_MAJORS_MEN" ? "PGA_TOUR"
    : league === "GOLF_MAJORS_WOMEN" ? "LPGA_TOUR" : league;
}
export type LeagueInterest = { value: string; sport?: string };
export function interestLeagues(leagues: LeagueInterest[]) {
  const choices = new Map<string, LeagueInterest>();
  for (const league of leagues) {
    const value = interestLeague(league.value);
    choices.set(value, { ...choices.get(value), value, ...(league.sport ? { sport: league.sport } : {}) });
  }
  return [...choices.values()];
}
function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
export function readPreferences(storage: Pick<Storage, "getItem">): InterestPreferences {
  const read = (key: string) => {
    try { return JSON.parse(storage.getItem(key) || "null"); } catch { return null; }
  };
  try {
    const value = read(INTERESTS_KEY);
    if (value && stringArray(value.leagues)) {
      const preferences = defaultPreferences();
      preferences.leagues = value.leagues;
      for (const tour of GOLF_TOURS) {
        if (["majors_only", "full_tour"].includes(value.golf_views?.[tour]))
          preferences.golf_views[tour] = value.golf_views[tour];
      }
      if (value.motorsport_view === "full_weekend") preferences.motorsport_view = "full_weekend";
      for (const sport of ["climbing", "weightlifting"] as const) {
        if (stringArray(value[sport]?.genders))
          preferences[sport].genders = GENDERS.filter((gender) => value[sport].genders.includes(gender));
      }
      if (stringArray(value.climbing?.disciplines))
        preferences.climbing.disciplines = CLIMBING_DISCIPLINES.filter((discipline) => value.climbing.disciplines.includes(discipline));
      return preferences;
    }
  } catch { /* Storage can be unavailable or malformed. Keep onboarding usable. */ }
  return defaultPreferences();
}

// Exact tournament identities, not a substring match for any event called “Open”.
const MEN_MAJORS: Record<string, string> = {
  "Masters Tournament": "masters", "PGA Championship": "pga",
  "U.S. Open": "us-open", "Open Championship": "open", "The Open": "open",
};
export function golfMajor(event: EventDetail) {
  if (event.league === "GOLF_MAJORS_WOMEN") return event.event_id;
  if (["PGA_TOUR", "GOLF_MAJORS_MEN"].includes(event.league)) return MEN_MAJORS[event.title] || null;
  return null;
}
// Combined sessions match any selected value. An unrecorded facet cannot
// exclude a record, unless the whole facet is explicitly deselected.
function matchesSessionFacet(tags: string[], available: readonly string[], selected: readonly string[] = available) {
  return selected.length > 0 && (!available.some((value) => tags.includes(value))
    || selected.some((value) => tags.includes(value)));
}
export function matchesInterestOptions(event: EventDetail, filters: FilterState) {
  const tour = interestLeague(event.league);
  if (filters.followed_leagues && !filters.followed_leagues.includes(tour)
    && !filters.followed_leagues.includes(event.league)) return false;
  if ((tour === "PGA_TOUR" || tour === "LPGA_TOUR") && filters.golf_views?.[tour] === "majors_only"
    && !golfMajor(event)) return false;
  if (event.sport === "climbing" || event.sport === "weightlifting") {
    const options = filters[event.sport];
    if (!matchesSessionFacet(event.tags, GENDERS, options?.genders)) return false;
    if (event.sport === "climbing"
      && !matchesSessionFacet(event.tags, CLIMBING_DISCIPLINES, filters.climbing?.disciplines)) return false;
  }
  return true;
}

// Keep source records and attribution intact. Suppress a reviewed men's major
// only when the selected ESPN record describes the same tournament and span.
export function uniqueGolfEvents(events: EventDetail[]) {
  const fedMajors = new Set(events.filter((event) => event.league === "PGA_TOUR" && golfMajor(event))
    .map((event) => `${golfMajor(event)}:${event.calendar_date}:${event.end_calendar_date}`));
  return events.filter((event) => event.league !== "GOLF_MAJORS_MEN"
    || !fedMajors.has(`${golfMajor(event)}:${event.calendar_date}:${event.end_calendar_date}`));
}
