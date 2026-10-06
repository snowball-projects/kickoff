import type { EventDetail, FilterState } from "./types";

export const INTERESTS_KEY = "kickoff.interests.v2";
export const LEGACY_INTERESTS_KEY = "kickoff.interests.v1";
export const GOLF_TOURS = ["PGA_TOUR", "LPGA_TOUR"] as const;
export type GolfView = "majors_only" | "full_tour";
export type InterestPreferences = {
  leagues: string[] | null;
  golf_views: Record<typeof GOLF_TOURS[number], GolfView>;
  motorsport_view: "race_only" | "full_weekend";
};
export function defaultPreferences(): InterestPreferences {
  return { leagues: null, golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" },
    motorsport_view: "race_only" };
}
export function interestLeague(league: string) {
  return league === "GOLF_MAJORS_MEN" ? "PGA_TOUR"
    : league === "GOLF_MAJORS_WOMEN" ? "LPGA_TOUR" : league;
}
export function interestLeagues(leagues: { value: string }[]) {
  return [...new Set(leagues.map(({ value }) => interestLeague(value)))].map((value) => ({ value }));
}
function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
export function migrateInterests(leagues: string[]): InterestPreferences {
  const preferences = defaultPreferences();
  preferences.leagues = [...new Set(leagues.map(interestLeague))];
  for (const [major, tour] of [["GOLF_MAJORS_MEN", "PGA_TOUR"], ["GOLF_MAJORS_WOMEN", "LPGA_TOUR"]] as const) {
    if (leagues.includes(major) && !leagues.includes(tour)) preferences.golf_views[tour] = "majors_only";
  }
  return preferences;
}
export function readPreferences(storage: Pick<Storage, "getItem">): InterestPreferences {
  const read = (key: string) => {
    try { return JSON.parse(storage.getItem(key) || "null"); } catch { return null; }
  };
  try {
    const value = read(INTERESTS_KEY);
    if (value && stringArray(value.leagues)) {
      const preferences = migrateInterests(value.leagues);
      for (const tour of GOLF_TOURS) {
        if (["majors_only", "full_tour"].includes(value.golf_views?.[tour]))
          preferences.golf_views[tour] = value.golf_views[tour];
      }
      if (value.motorsport_view === "full_weekend") preferences.motorsport_view = "full_weekend";
      // Retired boxing filters are deliberately ignored, including empty selections.
      return preferences;
    }
    const legacy = read(LEGACY_INTERESTS_KEY);
    if (stringArray(legacy)) return migrateInterests(legacy);
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
export function matchesInterestOptions(event: EventDetail, filters: FilterState) {
  const tour = interestLeague(event.league);
  if (filters.followed_leagues && !filters.followed_leagues.includes(tour)
    && !filters.followed_leagues.includes(event.league)) return false;
  if ((tour === "PGA_TOUR" || tour === "LPGA_TOUR") && filters.golf_views?.[tour] === "majors_only"
    && !golfMajor(event)) return false;
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
