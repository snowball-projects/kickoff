import type { EventResult } from "./result-format";

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
  record?: string;
  final_score?: number;
  result_winner?: boolean;
  result_advance?: boolean;
  aggregate_score?: number;
  shootout_score?: number;
  entry_total_kg?: number;
  start_list_category?: string;
  start_list_nation?: string;
  start_list_guest?: boolean;
  start_list_source_url?: string;
  start_list_checked_date?: string;
  logo_url?: string;
};

export type EventCard = {
  result?: EventResult;
  event_id: string;
  source: string;
  sport: string;
  league: string;
  event_type: string;
  title: string;
  subtitle: string | null;
  start_time_scope?: "event" | "shared_session";
  start_time_source?: string | null;
  start_time_source_url?: string | null;
  start_time_utc: string | null;
  start_time_local: string | null;
  status: string;
  venue: string | null;
  city: string | null;
  country: string | null;
  country_source_url?: string;
  round_or_stage: string | null;
  calendar_date: string | null;
  start_calendar_date?: string;
  end_calendar_date?: string | null;
  source_url?: string | null;
  competition_phase: string;
  tags: string[];
  participants: ApiParticipant[];
  week_label: string | null;
};

export type EventDetail = EventCard;

export type SourceNotice = {
  publisher?: string;
  kind: string;
  name: string;
  url: string;
  license: string;
  license_url: string;
  revision?: string;
};

export type SportFile = { value: string; count: number; file: string; leagues: string[] };

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

