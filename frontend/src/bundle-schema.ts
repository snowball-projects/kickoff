// Check external schedule responses before the browser caches a year.
type ObjectValue = Record<string, unknown>;
const object = (value: unknown): value is ObjectValue =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every(text);
const day = (value: unknown): value is string =>
  typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
  Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
const instant = (value: unknown): boolean =>
  typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
  day(value.slice(0, 10)) && Number.isFinite(Date.parse(value));
const participant = (value: unknown): boolean => object(value) && text(value.name) &&
  ["participant_id", "short_name", "role", "entity_type"].every((key) =>
    value[key] == null || typeof value[key] === "string");

export function validateBundle(payload: unknown): void {
  function fail(detail: string): never {
    throw new Error(`Invalid public snapshot: ${detail}`);
  }
  if (!object(payload) || payload.schema_version !== "1") fail("unsupported bundle version");
  if (!Number.isInteger(payload.season) || !Array.isArray(payload.available_seasons) ||
      !payload.available_seasons.every(Number.isInteger) || !payload.available_seasons.includes(payload.season) ||
      !Array.isArray(payload.providers) || !Array.isArray(payload.events)) fail("invalid year or collections");
  if (!(payload.providers as unknown[]).every(object)) fail("invalid providers");
  for (const key of ["updated_at", "coverage", "data_license_notice"]) {
    if (payload[key] != null && typeof payload[key] !== "string") fail(`invalid ${key}`);
  }
  if (payload.sources != null && (!Array.isArray(payload.sources) || !payload.sources.every((source) =>
      object(source) && ["name", "url", "license"].every((key) => text(source[key])) &&
      (source.license_url == null || typeof source.license_url === "string")))) fail("invalid sources");
  if (payload.components != null && (!Array.isArray(payload.components) || !payload.components.every((component) =>
      object(component) && typeof component.path === "string" &&
      /^\d{4}-(?:wikipedia|wikidata)-[a-f0-9]{64}\.json$/.test(component.path) &&
      typeof component.sha256 === "string" && /^[a-f0-9]{64}$/.test(component.sha256)))) fail("invalid components");
  const ids = new Set();
  for (const value of payload.events as unknown[]) {
    if (!object(value)) fail("invalid event");
    const label = text(value.event_id) ? value.event_id : "<missing-id>";
    const invalid = (field: string) => fail(`${label}: invalid ${field}`);
    for (const key of ["event_id", "source", "sport", "league", "season", "event_type", "title", "status", "competition_phase"]) {
      if (!text(value[key])) invalid(key);
    }
    if (ids.has(value.event_id)) fail("Duplicate event");
    ids.add(value.event_id);
    if (!day(value.calendar_date)) invalid("calendar_date");
    if ((value.end_calendar_date != null) &&
        (!day(value.end_calendar_date) || value.end_calendar_date < (value.calendar_date as string))) invalid("end_calendar_date");
    if (!strings(value.tags)) invalid("tags");
    if (!Array.isArray(value.participants) || !value.participants.every(participant)) invalid("participants");
    for (const key of ["home_participant", "away_participant"]) {
      if (value[key] != null && !participant(value[key])) invalid(key);
    }
    for (const key of ["source", "season", "status", "subtitle", "timezone", "venue", "city", "region", "country", "round_or_stage", "week_label", "source_url", "competition_phase"]) {
      if (value[key] != null && typeof value[key] !== "string") invalid(key);
    }
    if (value.start_time_utc != null && !instant(value.start_time_utc)) invalid("start_time_utc");
    // A local clock without a verified UTC instant remains Time TBD in the UI.
    if (value.start_time_local != null && (typeof value.start_time_local !== "string" ||
        ((value.start_time_utc != null) && !instant(value.start_time_local)))) invalid("start_time_local");
    if (value.start_time_utc != null && !(value.start_time_utc as string).endsWith("Z")) invalid("start_time_utc");
    if (value.start_time_local != null && (value.start_time_utc != null) && (!value.start_time_utc || !text(value.timezone) ||
        Date.parse(value.start_time_local as string) !== Date.parse(value.start_time_utc as string))) invalid("start_time_local");
    if (value.start_time_scope != null && !["event", "shared_session"].includes(value.start_time_scope as string)) invalid("shared session clock scope");
    if (value.start_time_scope === "shared_session" && !value.start_time_utc) invalid("shared session clock scope");
    for (const key of ["is_regular_season", "is_postseason", "is_exhibition", "is_support_event"]) {
      if ((value[key] != null) && typeof value[key] !== "boolean") invalid(key);
    }
  }
}
