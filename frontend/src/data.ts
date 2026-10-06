import { matchesInterestOptions, uniqueGolfEvents } from "./interest-preferences";
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
  ProviderSummary,
  SearchResponse,
  SourceNotice,
} from "./types";

type DashboardBundle = {
  schema_version: "1";
  updated_at?: string;
  sources?: SourceNotice[];
  coverage?: string;
  components?: { path: string; sha256: string }[];
  data_license_notice?: string;
  season: number;
  available_seasons: number[];
  providers: ProviderSummary[];
  events: EventDetail[];
};

const bundleCache = new Map<number, Promise<DashboardBundle>>();
const BUNDLE_CACHE_LIMIT = 3;
// Avoid repeatedly probing an unpublished neighboring year as months recycle.
// An explicit retry clears these misses; normal primary-year loads still retry.
const unpublishedSeasons = new Set<number>();

class ScheduleDataError extends Error {}
class UnpublishedScheduleError extends ScheduleDataError {}

function bundleUrl(season: number) {
  const base = import.meta.env?.BASE_URL || "/";
  return `${base.endsWith("/") ? base : `${base}/`}data/${season}.json`;
}

function loadBundle(season: number) {
  let promise = bundleCache.get(season);
  if (promise) {
    // Both pending and resolved bundles share the same small LRU cache.
    bundleCache.delete(season);
    bundleCache.set(season, promise);
  } else {
    promise = fetch(bundleUrl(season))
      .then(async (response) => {
        if (!response.ok) {
          if (response.status === 404) {
            unpublishedSeasons.add(season);
            throw new UnpublishedScheduleError(`No published schedule for ${season}.`);
          }
          throw new ScheduleDataError(
            `Schedule data for ${season} is unavailable. Please retry.`,
          );
        }
        const payload = (await response.json()) as DashboardBundle;
        if (payload.schema_version !== "1") {
          throw new ScheduleDataError(
            `Schedule data for ${season} is unavailable: unsupported bundle version.`,
          );
        }
        if (payload.season !== season) {
          throw new ScheduleDataError(
            `Schedule data for ${season} is unavailable: the bundle belongs to ${payload.season}.`,
          );
        }
        unpublishedSeasons.delete(season);
        return payload;
      })
      .catch((error: unknown) => {
        // An evicted request can settle after another request for this year.
        if (bundleCache.get(season) === promise) bundleCache.delete(season);
        throw error instanceof ScheduleDataError
          ? error
          : new ScheduleDataError(
              `Schedule data for ${season} is unavailable. Please retry.`,
            );
      });
    bundleCache.set(season, promise);
    if (bundleCache.size > BUNDLE_CACHE_LIMIT) {
      bundleCache.delete(bundleCache.keys().next().value!);
    }
  }
  return promise;
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
  if (
    filters.motorsport_view === "race_only" &&
    event.sport === "motorsport" &&
    event.event_type !== "race"
  )
    return false;
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
  signal?: AbortSignal,
  includeAdjacent = true,
) {
  throwIfAborted(signal);
  let primary: DashboardBundle | null = null;
  let primaryError: UnpublishedScheduleError | null = null;
  try {
    if (includeAdjacent && unpublishedSeasons.has(season)) {
      throw new UnpublishedScheduleError(`No published schedule for ${season}.`);
    }
    primary = await loadBundle(season);
  } catch (error) {
    if (!includeAdjacent || !(error instanceof UnpublishedScheduleError)) throw error;
    primaryError = error;
  }
  throwIfAborted(signal);
  if (!includeAdjacent) return { events: primary!.events, primaryError };
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
      return await loadBundle(year);
    } catch (error) {
      if (error instanceof UnpublishedScheduleError) return null;
      // A transient or malformed neighboring bundle must not silently hide
      // known boundary events. Keep the normal visible error/retry flow.
      throw error;
    }
  }));
  throwIfAborted(signal);
  return { primaryError, events: [...new Map([...adjacent, primary].flatMap((bundle) =>
    bundle?.events.map((event) => [event.event_id, event] as const) || [],
  )).values()] };
}

export async function getManifest(
  season: number,
  signal?: AbortSignal,
): Promise<ManifestResponse> {
  throwIfAborted(signal);
  const bundle = await loadBundle(season);
  throwIfAborted(signal);
  return {
    season,
    all_events: bundle.events.length,
    updated_at: bundle.updated_at,
    sources: bundle.sources,
    coverage: bundle.coverage,
    components: bundle.components,
    data_license_notice: bundle.data_license_notice,
    available_seasons: bundle.available_seasons,
    providers: bundle.providers,
  };
}

export async function getFilters(
  season: number,
  filters: FilterState,
  _timezone: string,
  signal?: AbortSignal,
): Promise<FiltersResponse> {
  throwIfAborted(signal);
  const bundle = await loadBundle(season);
  throwIfAborted(signal);
  const events = uniqueGolfEvents(bundle.events.filter((event) =>
    matchesFilters(event, filters),
  ));
  return {
    season,
    total_events: events.length,
    available_seasons: bundle.available_seasons,
    sports: facet(events.map((event) => event.sport)),
    leagues: facet(events.map((event) => event.league)),
    event_types: facet(events.map((event) => event.event_type)),
    competition_phases: facet(events.map((event) => event.competition_phase)),
    countries: facet(events.map((event) => event.country)),
    cities: facet(events.map((event) => event.city)),
    venues: facet(events.map((event) => event.venue)),
    tags: facet(events.flatMap((event) => event.tags)),
    participants: facet(
      events.flatMap((event) =>
        event.participants.map((participant) => participant.name),
      ),
    ),
  };
}

export async function getEventDetail(
  season: number,
  eventId: string,
  signal?: AbortSignal,
) {
  throwIfAborted(signal);
  const bundle = await loadBundle(season);
  throwIfAborted(signal);
  const event = bundle.events.find((item) => item.event_id === eventId);
  if (!event) throw new Error(`Event not found: ${eventId}`);
  return event;
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
  const { events, primaryError } = await eventsForRange(season, startDate, endDate, signal, includeAdjacent);
  const displayTimezone = safeTimezone(timezone);
  const grouped = new Map(
    datesBetween(startDate, endDate).map((date) => [date, [] as EventCard[]]),
  );
  for (const event of sortedEvents(
    uniqueGolfEvents(events.filter((item) => matchesFilters(item, filters))),
  )) {
    const { start: date, end } = eventDateSpan(event, displayTimezone);
    if (!date) continue;
    // Date-only multi-day tournaments occupy every inclusive date. A timed
    // one-day event uses its display-zone date, not the provider's venue date.
    for (const day of grouped.keys())
      if (day >= date && day <= (end || date))
        grouped.get(day)?.push({ ...eventCard(event), start_calendar_date: date, calendar_date: day, end_calendar_date: end });
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

function combinedFacets(responses: FiltersResponse[]): FiltersResponse {
  const result = { ...responses[0] };
  result.available_seasons = [
    ...new Set(responses.flatMap((r) => r.available_seasons)),
  ].sort();
  result.total_events = responses.reduce((sum, r) => sum + r.total_events, 0);
  for (const key of [
    "sports",
    "leagues",
    "event_types",
    "competition_phases",
    "countries",
    "cities",
    "venues",
    "tags",
    "participants",
  ] as const) {
    const counts = new Map<string, number>();
    for (const response of responses) {
      for (const item of response[key]) {
        counts.set(item.value, (counts.get(item.value) || 0) + item.count);
      }
    }
    result[key] = [...counts]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
  }
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
    if (retryChanged) unpublishedSeasons.clear();
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
        getCalendarRange(year, missing, this.filters, this.timezone, signal, false),
      ])
        .then(([manifest, facets, months]) => {
          if (this.years.get(year) !== record || record.pending !== request) return;
          record.pending = undefined;
          record.manifest = manifest;
          record.facets = facets;
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
      // Keep the last useful interests even when the entire window is missing.
      facets: responses.length ? combinedFacets(responses) : this.state.facets,
    };
    for (const listener of this.listeners) listener();
  }
}

export async function searchEvents(
  season: number,
  query: string,
  filters: FilterState,
  timezone: string,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  throwIfAborted(signal);
  const startDate = `${season}-01-01`;
  const endDate = `${season}-12-31`;
  const { events, primaryError } = await eventsForRange(season, startDate, endDate, signal);
  const displayTimezone = safeTimezone(timezone);
  const needle = normalized(query);
  const matches = sortedEvents(
    uniqueGolfEvents(events.filter((event) => {
      if (!matchesFilters(event, filters)) return false;
      const { start, end } = eventDateSpan(event, displayTimezone);
      if (!start || !end || start > endDate || end < startDate) return false;
      const haystack = [
        event.title,
        event.subtitle,
        event.venue,
        event.city,
        event.region,
        event.country,
        ...event.participants.map((participant) => participant.name),
      ]
        .filter(Boolean)
        .join(" | ")
        .toLocaleLowerCase();
      return haystack.includes(needle);
    })),
  );
  const items = matches
    .slice(0, 30)
    .map((event) => {
      const { start, end } = eventDateSpan(event, displayTimezone);
      return {
        ...eventCard(event),
        start_calendar_date: start || undefined,
        calendar_date: start,
        end_calendar_date: end,
      };
    });
  if (primaryError && !matches.length) throw primaryError;
  return {
    season,
    query,
    total: matches.length,
    limit: 30,
    offset: 0,
    has_more: matches.length > items.length,
    sort: "start_asc",
    timezone: displayTimezone,
    items,
  };
}
