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
export type LeagueInterest = { value: string; sport?: string };
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

export function golfMajor(event: Pick<EventDetail, "league" | "competition_phase">) {
  return GOLF_TOURS.some((tour) => tour === event.league) && event.competition_phase === "championship";
}
// Combined sessions match any selected value. An unrecorded facet cannot
// exclude a record, unless the whole facet is explicitly deselected.
function matchesSessionFacet(tags: string[], available: readonly string[], selected: readonly string[] = available) {
  return selected.length > 0 && (!available.some((value) => tags.includes(value))
    || selected.some((value) => tags.includes(value)));
}
export function matchesInterestOptions(event: EventDetail, filters: FilterState) {
  const tour = event.league;
  if (filters.followed_leagues && !filters.followed_leagues.includes(tour)) return false;
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
