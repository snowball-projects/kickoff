export type AppView = "month" | "year";
export type CalendarView = "month" | "week" | "day";
export type SortOrder = "start_asc" | "start_desc";
export type FeedScrollTarget = {
  kind: "month" | "week" | "day";
  value: string;
  behavior?: ScrollBehavior;
};

export type ApiParticipant = {
  name: string;
  participant_id: string | null;
  short_name: string | null;
  role: string | null;
  entity_type: string;
};

export type EventCard = {
  event_id: string;
  source: string;
  sport: string;
  league: string;
  season: string;
  event_type: string;
  title: string;
  subtitle: string | null;
  start_time_utc: string | null;
  start_time_local: string | null;
  timezone: string | null;
  status: string;
  venue: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  round_or_stage: string | null;
  calendar_date: string | null;
  end_calendar_date?: string | null;
  source_url?: string | null;
  competition_phase: string;
  tags: string[];
  participants: ApiParticipant[];
  home_participant_name: string | null;
  away_participant_name: string | null;
};

export type EventDetail = EventCard & {
  week_label: string | null;
  home_participant: ApiParticipant | null;
  away_participant: ApiParticipant | null;
  is_regular_season: boolean;
  is_postseason: boolean;
  is_exhibition: boolean;
  is_support_event: boolean;
};

export type ProviderSummary = {
  provider: string;
  label: string | null;
  sport: string | null;
  season_mode: string | null;
  season: number;
  event_count: number;
  warnings: string[];
  default_event_scope: string | null;
  default_include_special_events: boolean | null;
  default_include_support_events: boolean | null;
  default_motorsport_view: string | null;
  semantics: Record<string, unknown>;
};

export type SourceNotice = {
  name: string;
  url: string;
  license: string;
  license_url: string;
  revision: string;
};

export type ManifestResponse = {
  updated_at?: string;
  sources?: SourceNotice[];
  coverage?: string;
  season: number;
  all_events: number;
  available_seasons: number[];
  providers: ProviderSummary[];
};

export type FacetValue = {
  value: string;
  count: number;
};

export type FiltersResponse = {
  season: number;
  total_events: number;
  available_seasons: number[];
  sports: FacetValue[];
  leagues: FacetValue[];
  event_types: FacetValue[];
  competition_phases: FacetValue[];
  countries: FacetValue[];
  cities: FacetValue[];
  venues: FacetValue[];
  tags: FacetValue[];
  participants: FacetValue[];
};

export type EventListResponse = {
  season: number;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  sort: SortOrder;
  timezone: string | null;
  items: EventCard[];
};

export type SearchResponse = EventListResponse & {
  query: string;
};

export type CalendarDayGroup = {
  date: string;
  event_count: number;
  items: EventCard[];
};

export type CalendarResponse = {
  view: CalendarView;
  season: number;
  anchor_date: string;
  start_date: string;
  end_date: string;
  timezone: string;
  total_events: number;
  groups: CalendarDayGroup[];
};

export type FilterState = {
  followed_leagues?: string[];
  motorsport_view?: "race_only" | "full_weekend";
  sport: string;
  league: string;
  competition_phase: string;
  country: string;
  city: string;
  tags: string[];
};
