import type { EventDetail, FilterState } from "./types";

export const INTERESTS_KEY = "kickoff.interests.v3";
export const GENDERS = ["Men", "Women"] as const;
export const CLIMBING_DISCIPLINES = ["Boulder", "Lead", "Speed"] as const;
export const MOTORSPORT_EVENTS = ["practice", "qualifying", "sprint", "race"] as const;
export type InterestPreferences = {
  leagues: string[];
  motorsport_events: string[];
  climbing: { genders: string[]; disciplines: string[] };
  weightlifting: { genders: string[] };
};
export function defaultPreferences(): InterestPreferences {
  return { leagues: [], motorsport_events: [], climbing: { genders: [], disciplines: [] }, weightlifting: { genders: [] } };
}
export function allPreferences(leagues: string[]): InterestPreferences {
  return { leagues, motorsport_events: [...MOTORSPORT_EVENTS],
    climbing: { genders: [...GENDERS], disciplines: [...CLIMBING_DISCIPLINES] }, weightlifting: { genders: [...GENDERS] } };
}
export type LeagueInterest = { value: string; sport?: string };
export function readPreferences(storage: Pick<Storage, "getItem">): InterestPreferences {
  try { return JSON.parse(storage.getItem(INTERESTS_KEY) || "null") || defaultPreferences(); }
  catch { return defaultPreferences(); }
}

// Combined sessions match any selected value. An unrecorded facet cannot
// exclude a record, unless the whole facet is explicitly deselected.
function matchesSessionFacet(tags: string[], available: readonly string[], selected: readonly string[] = available) {
  return selected.length > 0 && (!available.some((value) => tags.includes(value))
    || selected.some((value) => tags.includes(value)));
}
export function matchesInterestOptions(event: EventDetail, filters: FilterState) {
  if (filters.followed_leagues && !filters.followed_leagues.includes(event.league)) return false;
  if (event.sport === "motorsport" && filters.motorsport_events && !filters.motorsport_events.includes(event.event_type)) return false;
  if (event.sport === "climbing" || event.sport === "weightlifting") {
    const options = filters[event.sport];
    if (!matchesSessionFacet(event.tags, GENDERS, options?.genders)) return false;
    if (event.sport === "climbing"
      && !matchesSessionFacet(event.tags, CLIMBING_DISCIPLINES, filters.climbing?.disciplines)) return false;
  }
  return true;
}
