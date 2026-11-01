export type AppView = "month" | "year";
export type CalendarView = "month" | "week" | "day";
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
  country_code?: string;
  country_source_url?: string;
  country_checked_date?: string;
  country_source_kind?: string;
  record?: string;
  team_source_url?: string;
  final_score?: number;
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
  start_time_scope?: "event" | "shared_session";
  start_time_source?: string | null;
  start_time_source_url?: string | null;
  start_time_utc: string | null;
  start_time_local: string | null;
  timezone: string | null;
  status: string;
  venue: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  country_source_url?: string;
  country_checked_date?: string;
  round_or_stage: string | null;
  calendar_date: string | null;
  start_calendar_date?: string;
  end_calendar_date?: string | null;
  source_url?: string | null;
  competition_phase: string;
  tags: string[];
  participants: ApiParticipant[];
  home_participant: ApiParticipant | null;
  away_participant: ApiParticipant | null;
  week_label: string | null;
  facts_checked_date?: string;
  facts_source_url?: string;
  home_participant_name: string | null;
  away_participant_name: string | null;
};

export type EventDetail = EventCard & {
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
  semantics: Record<string, unknown>;
};

export type SourceNotice = {
  kind: string;
  name: string;
  url: string;
  license: string;
  license_url: string;
  revision?: string;
};

export type SportFile = { value: string; count: number; file: string };

export type ManifestResponse = {
  sports: SportFile[];
  leagues: LeagueFacetValue[];
  updated_at?: string;
  sources?: SourceNotice[];
  coverage?: string;
  data_license_notice?: string;
  season: number;
  all_events: number;
  available_seasons: number[];
  providers: ProviderSummary[];
};

export type FacetValue = {
  value: string;
  count: number;
};

export type LeagueFacetValue = FacetValue & { sport: string };

export type FiltersResponse = {
  season: number;
  total_events: number;
  available_seasons: number[];
  sports: FacetValue[];
  leagues: LeagueFacetValue[];

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
  climbing?: { levels?: string[]; genders: string[]; disciplines: string[] };
  weightlifting?: { levels?: string[]; genders: string[] };
  motorsport_events?: string[];
  sport: string;
  league: string;
  competition_phase: string;
  country: string;
  city: string;
  tags: string[];
};

