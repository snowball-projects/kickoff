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
  season: number;
  available_seasons: number[];
  providers: ProviderSummary[];
  events: EventDetail[];
};

const bundleCache = new Map<number, Promise<DashboardBundle>>();

function bundleUrl(season: number) {
  const base = import.meta.env?.BASE_URL || "/";
  return `${base.endsWith("/") ? base : `${base}/`}data/${season}.json`;
}

function loadBundle(season: number) {
  let promise = bundleCache.get(season);
  if (!promise) {
    promise = fetch(bundleUrl(season))
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Schedule data for ${season} is unavailable.`);
        }
        const payload = (await response.json()) as DashboardBundle;
        if (payload.schema_version !== "1") {
          throw new Error(
            `Unsupported schedule bundle version: ${payload.schema_version}`,
          );
        }
        return payload;
      })
      .catch((error: unknown) => {
        bundleCache.delete(season);
        throw error;
      });
    bundleCache.set(season, promise);
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
  if (
    filters.followed_leagues &&
    !filters.followed_leagues.includes(event.league)
  )
    return false;
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

function eventDate(event: EventDetail, timezone: string) {
  if (event.start_time_utc) {
    const date = new Date(event.start_time_utc);
    if (!Number.isNaN(date.valueOf())) {
      try {
        const parts = new Intl.DateTimeFormat("en-US", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          timeZone: timezone,
        }).formatToParts(date);
        const value = Object.fromEntries(
          parts.map((part) => [part.type, part.value]),
        );
        return `${value.year}-${value.month}-${value.day}`;
      } catch {
        // Fall back to the provider's canonical date for an invalid browser timezone.
      }
    }
  }
  return event.calendar_date;
}

function eventTime(event: EventDetail) {
  if (event.start_time_utc) {
    const parsed = Date.parse(event.start_time_utc);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return event.calendar_date
    ? Date.parse(`${event.calendar_date}T12:00:00Z`)
    : Number.MAX_SAFE_INTEGER;
}

function sortedEvents(events: EventDetail[]) {
  return [...events].sort(
    (left, right) =>
      eventTime(left) - eventTime(right) ||
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
  const events = bundle.events.filter((event) =>
    matchesFilters(event, filters),
  );
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
): Promise<CalendarResponse> {
  throwIfAborted(signal);
  const bundle = await loadBundle(season);
  throwIfAborted(signal);
  const [startDate, endDate] = dateRange(view, anchorDate);
  const grouped = new Map(
    datesBetween(startDate, endDate).map((date) => [date, [] as EventCard[]]),
  );
  for (const event of sortedEvents(
    bundle.events.filter((item) => matchesFilters(item, filters)),
  )) {
    const date = eventDate(event, timezone);
    if (!date) continue;
    const end =
      event.end_calendar_date &&
      event.end_calendar_date > (event.calendar_date || date)
        ? event.end_calendar_date
        : date;
    // Date-only multi-day tournaments occupy every inclusive date. A timed
    // one-day event uses its display-zone date, not the provider's venue date.
    for (const day of grouped.keys())
      if (day >= date && day <= end)
        grouped.get(day)?.push({ ...eventCard(event), calendar_date: day });
  }
  const groups = [...grouped.entries()].map(([date, items]) => ({
    date,
    event_count: items.length,
    items,
  }));
  return {
    view,
    season,
    anchor_date: anchorDate,
    start_date: startDate,
    end_date: endDate,
    timezone,
    total_events: groups.reduce((total, group) => total + group.event_count, 0),
    groups,
  };
}

export async function getCalendarRange(
  season: number,
  monthAnchors: string[],
  filters: FilterState,
  timezone: string,
  signal?: AbortSignal,
) {
  const entries = await Promise.all(
    monthAnchors.map(
      async (anchor) =>
        [
          anchor,
          await getCalendar("month", season, anchor, filters, timezone, signal),
        ] as const,
    ),
  );
  return Object.fromEntries(entries) as Record<string, CalendarResponse>;
}

export async function searchEvents(
  season: number,
  query: string,
  filters: FilterState,
  timezone: string,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  throwIfAborted(signal);
  const bundle = await loadBundle(season);
  throwIfAborted(signal);
  const needle = normalized(query);
  const matches = sortedEvents(
    bundle.events.filter((event) => {
      if (!matchesFilters(event, filters)) return false;
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
    }),
  );
  const items = matches
    .slice(0, 30)
    .map((event) => ({
      ...eventCard(event),
      calendar_date: eventDate(event, timezone),
    }));
  return {
    season,
    query,
    total: matches.length,
    limit: 30,
    offset: 0,
    has_more: matches.length > items.length,
    sort: "start_asc",
    timezone: null,
    items,
  };
}
