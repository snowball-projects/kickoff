import { matchesInterestOptions } from "./interest-preferences";
import { golfRound, isGolf } from "./golf";
import { eventCalendarDate, eventTimestamp, safeTimezone } from "./date-utils";
import type {
  CalendarResponse,
  CalendarView,
  EventCard,
  EventDetail,
  FacetValue,
  FilterState,
  FiltersResponse,
  ManifestResponse,
} from "./types";

type SportBundle = { events: EventDetail[] };
type PublishedIndex = { available_seasons: number[]; seasons: Record<string, ManifestResponse> };
let manifestPromise: Promise<PublishedIndex> | undefined;
const sportCache = new Map<string, Promise<SportBundle>>();
const unpublishedSeasons = new Set<number>();

class ScheduleDataError extends Error {}
class UnpublishedScheduleError extends ScheduleDataError {}

function dataUrl(file: string) {
  const base = import.meta.env?.BASE_URL || "/";
  return `${base.endsWith("/") ? base : `${base}/`}data/${file}`;
}

async function readFile<T>(file: string): Promise<T> {
  const response = await fetch(dataUrl(file));
  if (!response.ok) throw new ScheduleDataError("Schedule data could not be loaded. Please retry.");
  return response.json() as Promise<T>;
}

function loadIndex() {
  if (!manifestPromise) {
    const request = readFile<PublishedIndex>("manifest.json").catch(() => {
      if (manifestPromise === request) manifestPromise = undefined;
      throw new ScheduleDataError("Schedule data could not be loaded. Please retry.");
    });
    manifestPromise = request;
  }
  return manifestPromise;
}

async function loadManifest(season: number) {
  const index = await loadIndex();
  const year = index.seasons[String(season)];
  if (!year) {
    unpublishedSeasons.add(season);
    throw new UnpublishedScheduleError(`No published schedule for ${season}.`);
  }
  unpublishedSeasons.delete(season);
  return year;
}

async function loadEvents(season: number, filters: FilterState) {
  const manifest = await loadManifest(season);
  const sports = new Set(manifest.leagues
    .filter((league) => (!filters.followed_leagues || filters.followed_leagues.includes(league.value))
      && (!filters.league || normalized(league.value) === normalized(filters.league))
      && (!filters.sport || normalized(league.sport) === normalized(filters.sport)))
    .map((league) => league.sport));
  const bundles = await Promise.all(manifest.sports.filter((sport) => sports.has(sport.value)).map((sport) => {
    let request = sportCache.get(sport.file);
    if (!request) {
      request = readFile<SportBundle>(sport.file).catch(() => {
        if (sportCache.get(sport.file) === request) sportCache.delete(sport.file);
        throw new ScheduleDataError(`Schedule data for ${season} could not be loaded. Please retry.`);
      });
      sportCache.set(sport.file, request);
    }
    return request;
  }));
  return bundles.flatMap((bundle) => bundle.events);
}

function throwIfAborted(signal?: AbortSignal) {
  if (signal?.aborted) {
    throw new DOMException("The request was aborted.", "AbortError");
  }
}

function eventCard(event: EventDetail): EventCard {
  return {
    ...event,
    home_participant_name: event.home_participant?.name || null,
    away_participant_name: event.away_participant?.name || null,
  };
}

function normalized(value: string | null | undefined) {
  return (value || "").trim().toLocaleLowerCase();
}

function matchesFilters(event: EventDetail, filters: FilterState) {
  if (!matchesInterestOptions(event, filters)) return false;
  if (filters.sport && normalized(event.sport) !== normalized(filters.sport))
    return false;
  if (filters.league && normalized(event.league) !== normalized(filters.league))
    return false;
  if (
    filters.competition_phase &&
    normalized(event.competition_phase) !==
      normalized(filters.competition_phase)
  )
    return false;
  if (
    filters.country &&
    normalized(event.country) !== normalized(filters.country)
  )
    return false;
  if (filters.city && normalized(event.city) !== normalized(filters.city))
    return false;
  const tags = new Set(event.tags.map(normalized));
  return filters.tags.every((tag) => tags.has(normalized(tag)));
}

function sortedEvents(events: EventDetail[]) {
  return [...events].sort(
    (left, right) =>
      eventTimestamp(left) - eventTimestamp(right) ||
      left.event_id.localeCompare(right.event_id),
  );
}

function facet(values: Array<string | null | undefined>): FacetValue[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (value) counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()]
    .sort(
      ([leftValue, leftCount], [rightValue, rightCount]) =>
        rightCount - leftCount || leftValue.localeCompare(rightValue),
    )
    .map(([value, count]) => ({ value, count }));
}

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function isoDate(date: Date) {
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
}

function parseDate(value: string) {
  return new Date(`${value}T12:00:00Z`);
}

function dateRange(view: CalendarView, anchor: string) {
  const date = parseDate(anchor);
  if (view === "day") return [anchor, anchor] as const;
  if (view === "week") {
    const mondayOffset = (date.getUTCDay() + 6) % 7;
    const start = new Date(date);
    start.setUTCDate(start.getUTCDate() - mondayOffset);
    const end = new Date(start);
    end.setUTCDate(end.getUTCDate() + 6);
    return [isoDate(start), isoDate(end)] as const;
  }
  const start = new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1, 12),
  );
  const end = new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0, 12),
  );
  return [isoDate(start), isoDate(end)] as const;
}

function datesBetween(start: string, end: string) {
  const dates: string[] = [];
  const current = parseDate(start);
  const last = parseDate(end);
  while (current <= last) {
    dates.push(isoDate(current));
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return dates;
}

function eventDateSpan(event: EventDetail, timezone: string) {
  const start = eventCalendarDate(event, timezone);
  // An inclusive date-only end is not a timestamp. Preserve verified spans,
  // while a single-date timed record moves wholly to its display-zone date.
  const end = start && event.end_calendar_date &&
    event.end_calendar_date > (event.calendar_date || start)
    ? event.end_calendar_date : start;
  return { start, end };
}

async function eventsForRange(
  season: number,
  startDate: string,
  endDate: string,
  filters: FilterState,
  signal?: AbortSignal,
  includeAdjacent = true,
) {
  throwIfAborted(signal);
  let primary: EventDetail[] | null = null;
  let primaryError: UnpublishedScheduleError | null = null;
  try {
    if (includeAdjacent && unpublishedSeasons.has(season)) {
      throw new UnpublishedScheduleError(`No published schedule for ${season}.`);
    }
    primary = await loadEvents(season, filters);
  } catch (error) {
    if (!includeAdjacent || !(error instanceof UnpublishedScheduleError)) throw error;
    primaryError = error;
  }
  throwIfAborted(signal);
  if (!includeAdjacent) return { events: primary!, primaryError };
  // Snapshots use source calendar years. UTC and visitor-local dates can cross
  // into a neighboring year; two days cover the full -12 to +14 hour range.
  const first = parseDate(startDate);
  first.setUTCDate(first.getUTCDate() - 2);
  const last = parseDate(endDate);
  last.setUTCDate(last.getUTCDate() + 2);
  const neighbors: number[] = [];
  for (let year = first.getUTCFullYear(); year <= last.getUTCFullYear(); year += 1) {
    if (year !== season && !unpublishedSeasons.has(year)) neighbors.push(year);
  }
  const adjacent = await Promise.all(neighbors.map(async (year) => {
    try {
      return await loadEvents(year, filters);
    } catch (error) {
      if (error instanceof UnpublishedScheduleError) return null;
      // A transient or malformed neighboring bundle must not silently hide
      // known boundary events. Keep the normal visible error/retry flow.
      throw error;
    }
  }));
  throwIfAborted(signal);
  return { primaryError, events: [...new Map([...adjacent, primary].flatMap((bundle) =>
    bundle?.map((event) => [event.event_id, event] as const) || [],
  )).values()] };
}

export async function getManifest(
  season: number,
  signal?: AbortSignal,
): Promise<ManifestResponse> {
  throwIfAborted(signal);
  const manifest = await loadManifest(season);
  throwIfAborted(signal);
  return manifest;
}

export async function getFilters(
  season: number,
  filters: FilterState,
  _timezone: string,
  signal?: AbortSignal,
): Promise<FiltersResponse> {
  throwIfAborted(signal);
  const manifest = await loadManifest(season);
  throwIfAborted(signal);
  if (filters.followed_leagues === undefined && Object.values(filters).every((value) => !value || (Array.isArray(value) && !value.length))) {
    return { season, total_events: manifest.all_events, available_seasons: manifest.available_seasons,
      sports: manifest.sports.map(({ value, count }) => ({ value, count })), leagues: manifest.leagues };
  }
  const events = (await loadEvents(season, filters)).filter((event) => matchesFilters(event, filters));
  throwIfAborted(signal);
  const leagueSports = new Map(events.map((event) => [event.league, event.sport]));
  return {
    season,
    total_events: events.length,
    available_seasons: manifest.available_seasons,
    sports: facet(events.map((event) => event.sport)),
    leagues: facet(events.map((event) => event.league)).map((item) => ({ ...item, sport: leagueSports.get(item.value)! })),

  };
}

export async function getCalendar(
  view: CalendarView,
  season: number,
  anchorDate: string,
  filters: FilterState,
  timezone: string,
  signal?: AbortSignal,
  includeAdjacent = true,
): Promise<CalendarResponse> {
  throwIfAborted(signal);
  const [startDate, endDate] = dateRange(view, anchorDate);
  const { events, primaryError } = await eventsForRange(season, startDate, endDate, filters, signal, includeAdjacent);
  const displayTimezone = safeTimezone(timezone);
  const grouped = new Map(
    datesBetween(startDate, endDate).map((date) => [date, [] as EventCard[]]),
  );
  for (const event of sortedEvents(
    events.filter((item) => matchesFilters(item, filters)),
  )) {
    const { start: date, end } = eventDateSpan(event, displayTimezone);
    if (!date) continue;
    // Date-only multi-day tournaments occupy every inclusive date. A timed
    // one-day event uses its display-zone date, not the provider's venue date.
    for (const day of grouped.keys())
      if (day >= date && day <= (end || date)) {
        const card = { ...eventCard(event), start_calendar_date: date, calendar_date: day, end_calendar_date: end };
        grouped.get(day)?.push(isGolf(event) ? golfRound(card, day, date) : card);
      }
  }
  const groups = [...grouped.entries()].map(([date, items]) => ({
    date,
    event_count: items.length,
    items,
  }));
  const totalEvents = groups.reduce((total, group) => total + group.event_count, 0);
  if (primaryError && !totalEvents) throw primaryError;
  return {
    view,
    season,
    anchor_date: anchorDate,
    start_date: startDate,
    end_date: endDate,
    timezone: displayTimezone,
    total_events: totalEvents,
    groups,
  };
}

export async function getCalendarRange(
  season: number,
  monthAnchors: string[],
  filters: FilterState,
  timezone: string,
  signal?: AbortSignal,
  includeAdjacent = true,
) {
  const entries = await Promise.all(
    monthAnchors.map(
      async (anchor) =>
        [
          anchor,
          await getCalendar("month", season, anchor, filters, timezone, signal, includeAdjacent),
        ] as const,
    ),
  );
  return Object.fromEntries(entries) as Record<string, CalendarResponse>;
}

export type CalendarDataState = {
  months: Record<string, CalendarResponse>;
  errors: Record<number, string>;
  loadingYears: number[];
  boundaryLoadingYears: number[];
  manifests: Record<number, ManifestResponse>;
  facets: FiltersResponse | null;
};

type YearLoad = {
  pending?: AbortController;
  boundaryPending?: AbortController;
  error?: string;
  boundaryError?: string;
  manifest?: ManifestResponse;
  facets?: FiltersResponse;
};

const FACET_FILTERS: FilterState = {
  sport: "",
  league: "",
  competition_phase: "",
  country: "",
  city: "",
  tags: [],
};

function combineFacet<T extends FacetValue>(items: T[]): T[] {
  const combined = new Map<string, T>();
  for (const item of items)
    combined.set(item.value, { ...item, count: (combined.get(item.value)?.count || 0) + item.count });
  return [...combined.values()].sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
}

function combinedFacets(responses: FiltersResponse[]): FiltersResponse {
  const result = { ...responses[0] };
  result.available_seasons = [
    ...new Set(responses.flatMap((r) => r.available_seasons)),
  ].sort();
  result.total_events = responses.reduce((sum, r) => sum + r.total_events, 0);
  result.leagues = combineFacet(responses.flatMap((response) => response.leagues));
  result.sports = combineFacet(responses.flatMap((response) => response.sports));
  return result;
}

// The store owns only the requested window. It is separate from React so race
// conditions, retries and window eviction can be checked with offline fixtures.
export class CalendarDataStore {
  private anchors = new Set<string>();
  private years = new Map<number, YearLoad>();
  private months: Record<string, CalendarResponse> = {};
  private signature = "";
  private timezone = "";
  private retry = 0;
  private filters = FACET_FILTERS;
  private listeners = new Set<() => void>();
  private state: CalendarDataState = {
    months: {},
    errors: {},
    loadingYears: [],
    boundaryLoadingYears: [],
    manifests: {},
    facets: null,
  };

  getSnapshot = () => this.state;

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  matches(signature: string, timezone: string) {
    return this.signature === signature && this.timezone === timezone;
  }

  update(anchors: string[], signature: string, timezone: string, retry: number) {
    const changed = !this.matches(signature, timezone);
    const retryChanged = this.retry !== retry;
    if (retryChanged) { unpublishedSeasons.clear(); manifestPromise = undefined; sportCache.clear(); }
    this.signature = signature;
    this.timezone = timezone;
    this.retry = retry;
    this.filters = JSON.parse(signature) as FilterState;
    this.anchors = new Set(anchors);
    const years = new Set(anchors.map((anchor) => Number(anchor.slice(0, 4))));
    this.months = changed || retryChanged
      ? {}
      : Object.fromEntries(
          Object.entries(this.months).filter(([anchor]) => this.anchors.has(anchor)),
        );
    for (const [year, record] of this.years) {
      if (!years.has(year) || changed || retryChanged) {
        record.pending?.abort();
        record.pending = undefined;
        record.boundaryPending?.abort();
        record.boundaryPending = undefined;
      }
      if (!years.has(year)) this.years.delete(year);
      // Changing interests cannot make an unpublished year available.
      else if (retryChanged) {
        record.error = undefined;
        record.boundaryError = undefined;
        record.manifest = undefined;
        record.facets = undefined;
      } else if (changed) {
        if (!unpublishedSeasons.has(year)) record.error = undefined;
        record.boundaryError = undefined;
      }
    }
    for (const year of years) {
      if (!this.years.has(year)) this.years.set(year, {});
    }
    this.loadMissing();
    for (const [year, record] of this.years) {
      if (record.error && unpublishedSeasons.has(year)) this.loadBoundaryMonths(year, record);
    }
    this.publish();
  }

  cancel() {
    for (const record of this.years.values()) {
      record.pending?.abort();
      record.pending = undefined;
      record.boundaryPending?.abort();
      record.boundaryPending = undefined;
    }
  }

  private loadMissing() {
    for (const [year, record] of this.years) {
      if (record.pending || record.error) continue;
      const missing = [...this.anchors].filter(
        (anchor) => Number(anchor.slice(0, 4)) === year && !this.months[anchor],
      );
      if (!missing.length) continue;
      const request = new AbortController();
      record.pending = request;
      const { signal } = request;
      Promise.all([
        record.manifest || getManifest(year, signal),
        record.facets || getFilters(year, FACET_FILTERS, this.timezone, signal),
      ])
        .then(([manifest, facets]) => {
          if (this.years.get(year) !== record || record.pending !== request) return;
          record.manifest = manifest;
          record.facets = facets;
          this.publish();
          return getCalendarRange(year, missing, this.filters, this.timezone, signal, false);
        })
        .then((months) => {
          if (!months) return;
          if (this.years.get(year) !== record || record.pending !== request) return;
          record.pending = undefined;
          for (const [anchor, month] of Object.entries(months)) {
            if (this.anchors.has(anchor)) this.months[anchor] = month;
          }
          this.loadBoundaryMonths(year, record);
          // A sliding window may have added more months while this year loaded.
          this.loadMissing();
          this.publish();
        })
        .catch((error: unknown) => {
          if (this.years.get(year) !== record || record.pending !== request) return;
          record.pending = undefined;
          record.error = error instanceof Error
            ? error.message
            : `Schedule data for ${year} is unavailable. Please retry.`;
          if (error instanceof UnpublishedScheduleError) this.loadBoundaryMonths(year, record);
          this.publish();
        });
    }
  }

  private loadBoundaryMonths(year: number, record: YearLoad) {
    const anchors = [...this.anchors].filter((anchor) =>
      Number(anchor.slice(0, 4)) === year && ["01", "12"].includes(anchor.slice(5, 7)),
    );
    if (!anchors.length) return;
    record.boundaryPending?.abort();
    const request = new AbortController();
    record.boundaryPending = request;
    // Render the year's own data first. A neighboring request must never hold
    // up an otherwise available year; merge its boundary events when it settles.
    let remaining = anchors.length;
    const failures = new Set<string>();
    const settle = (anchor: string, month?: CalendarResponse, error?: unknown) => {
      if (this.years.get(year) !== record || record.boundaryPending !== request) return;
      if (month && this.anchors.has(anchor)) this.months[anchor] = month;
      if (error && !(error instanceof UnpublishedScheduleError)) {
        failures.add(error instanceof Error ? error.message : "Please retry.");
      }
      record.boundaryError = failures.size
        ? `Some year-boundary events could not be loaded. ${[...failures].join(" ")}`
        : undefined;
      remaining -= 1;
      if (!remaining) record.boundaryPending = undefined;
      this.publish();
    };
    for (const anchor of anchors) {
      getCalendar("month", year, anchor, this.filters, this.timezone, request.signal)
        .then((month) => settle(anchor, month), (error: unknown) => settle(anchor, undefined, error));
    }
  }

  private publish() {
    const responses = [...this.years.values()].flatMap((record) =>
      record.facets ? [record.facets] : [],
    );
    this.state = {
      months: { ...this.months },
      errors: Object.fromEntries(
        [...this.years].flatMap(([year, record]) => {
          const boundaryVisible = [...this.anchors].some((anchor) =>
            Number(anchor.slice(0, 4)) === year && ["01", "12"].includes(anchor.slice(5, 7)),
          );
          const notice = [record.error, boundaryVisible ? record.boundaryError : undefined]
            .filter(Boolean).join(" ");
          return notice ? [[year, notice]] : [];
        }),
      ),
      manifests: Object.fromEntries(
        [...this.years].flatMap(([year, record]) =>
          record.manifest ? [[year, record.manifest]] : [],
        ),
      ),
      loadingYears: [...this.years]
        .filter(([, record]) => record.pending)
        .map(([year]) => year),
      boundaryLoadingYears: [...this.years]
        .filter(([, record]) => record.boundaryPending)
        .map(([year]) => year),
      // Keep the last useful interests even when the entire window is missing.
      facets: responses.length ? combinedFacets(responses) : this.state.facets,
    };
    for (const listener of this.listeners) listener();
  }
}
