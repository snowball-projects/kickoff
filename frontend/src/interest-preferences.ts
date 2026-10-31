import type { EventDetail, FilterState } from "./types";

export const INTERESTS_KEY = "kickoff.interests.v4";
export const CLIMBING_LEVELS = ["Senior", "Youth", "Para"] as const;
export const WEIGHTLIFTING_LEVELS = ["Youth", "Junior", "Senior", "Masters"] as const;
export const WEIGHTLIFTING_LEAGUE_LEVELS: Record<string, string> = {
  IWF_WORLDS: "Senior", IWF_JUNIOR_WORLDS: "Junior", IWF_YOUTH_WORLDS: "Youth", MASTERS_WORLDS: "Masters",
  WEIGHTLIFTING_AFRICA: "Senior", WEIGHTLIFTING_ASIA: "Senior",
  WEIGHTLIFTING_EUROPE: "Senior", WEIGHTLIFTING_OCEANIA: "Senior", WEIGHTLIFTING_PAN_AMERICA: "Senior",
  WEIGHTLIFTING_COMMONWEALTH_GAMES: "Senior", WEIGHTLIFTING_ASIAN_GAMES: "Senior", WEIGHTLIFTING_PAN_AM_GAMES: "Senior",
};
export const GENDERS = ["Men", "Women"] as const;
export const CLIMBING_DISCIPLINES = ["Boulder", "Lead", "Speed"] as const;
export const MOTORSPORT_EVENTS = ["practice", "qualifying", "sprint", "race"] as const;
export type InterestPreferences = {
  leagues: string[];
  motorsport_events: string[];
  climbing: { levels: string[]; genders: string[]; disciplines: string[] };
  weightlifting: { levels: string[]; genders: string[] };
};
export function defaultPreferences(): InterestPreferences {
  return { leagues: [], motorsport_events: [], climbing: { levels: [], genders: [], disciplines: [] }, weightlifting: { levels: [], genders: [] } };
}
export function allPreferences(leagues: string[]): InterestPreferences {
  return { leagues, motorsport_events: [...MOTORSPORT_EVENTS],
    climbing: { levels: [...CLIMBING_LEVELS], genders: [...GENDERS], disciplines: [...CLIMBING_DISCIPLINES] }, weightlifting: { levels: [...WEIGHTLIFTING_LEVELS], genders: [...GENDERS] } };
}
export type LeagueInterest = { value: string; sport?: string };
function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
export function readPreferences(storage: Pick<Storage, "getItem">): InterestPreferences {
  try {
    const value = JSON.parse(storage.getItem(INTERESTS_KEY) || "null");
    if (stringArray(value?.leagues) && stringArray(value?.motorsport_events)
      && stringArray(value?.climbing?.levels) && stringArray(value?.climbing?.genders) && stringArray(value?.climbing?.disciplines)
      && stringArray(value?.weightlifting?.levels) && stringArray(value?.weightlifting?.genders)) {
      return { leagues: value.leagues, motorsport_events: value.motorsport_events,
        climbing: { levels: value.climbing.levels, genders: value.climbing.genders, disciplines: value.climbing.disciplines },
        weightlifting: { levels: value.weightlifting.levels, genders: value.weightlifting.genders } };
    }
  } catch { /* Unavailable storage or invalid current preferences reopen Interests. */ }
  return defaultPreferences();
}

// Climbing levels come from the session, including continental competitions.
// Future weightlifting leagues can supply their level in tags; known leagues
// keep the federation's league-level classification.
export function sessionLevel(event: Pick<EventDetail, "sport" | "league" | "tags">) {
  if (event.sport === "climbing") {
    if (event.tags.includes("Para")) return "Para";
    return event.tags.some((tag) => ["Youth", "U17", "U19", "U21"].includes(tag)) ? "Youth" : "Senior";
  }
  if (event.sport === "weightlifting") {
    const level = WEIGHTLIFTING_LEAGUE_LEVELS[event.league];
    return level || event.tags.find((tag) => WEIGHTLIFTING_LEVELS.some((value) => value === tag)) || "Senior";
  }
  return null;
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
    if (options?.levels && !options.levels.includes(sessionLevel(event)!)) return false;
    if (!matchesSessionFacet(event.tags, GENDERS, options?.genders)) return false;
    if (event.sport === "climbing"
      && !matchesSessionFacet(event.tags, CLIMBING_DISCIPLINES, filters.climbing?.disciplines)) return false;
  }
  return true;
}
