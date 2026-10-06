import type { CalendarDayGroup, EventCard, FilterState } from "./types";

export const WEEKDAY_LABELS = [
  "Sun",
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
] as const;
export const WEEKDAY_NARROW = ["S", "M", "T", "W", "T", "F", "S"] as const;
export type MonthGridCell = {
  date: string | null;
  inMonth: boolean;
  group?: CalendarDayGroup;
};

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function daysInMonth(year: number, month: number) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

const validTimezones = new Map<string, string>();
const dateFormatters = new Map<string, Intl.DateTimeFormat>();

export function safeTimezone(timezone: string) {
  const known = validTimezones.get(timezone);
  if (known) return known;
  let valid = "UTC";
  try {
    if (timezone) valid = new Intl.DateTimeFormat("en-US", { timeZone: timezone }).resolvedOptions().timeZone;
  } catch {
    // A restricted or older browser may not expose a usable IANA timezone.
  }
  if (validTimezones.size >= 16) validTimezones.clear();
  validTimezones.set(timezone, valid);
  return valid;
}

// Device settings only: no location permission, IP lookup or network request.
export function browserTimezone() {
  try {
    return safeTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  } catch {
    return "UTC";
  }
}

function zonedDateText(date: Date, timezone: string) {
  const zone = safeTimezone(timezone);
  let formatter = dateFormatters.get(zone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-US", {
      year: "numeric", month: "2-digit", day: "2-digit", timeZone: zone,
    });
    if (dateFormatters.size >= 16) dateFormatters.clear();
    dateFormatters.set(zone, formatter);
  }
  const parts = Object.fromEntries(formatter.formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function todayIso(timezone = browserTimezone(), now = new Date()) {
  return zonedDateText(now, timezone);
}

export function timezoneLabel(timezone: string) {
  const zone = safeTimezone(timezone);
  if (zone === "UTC") return "UTC";
  return `Local time · ${zone.split("/").at(-1)!.replaceAll("_", " ")}`;
}

export function firstOfMonth(dateText: string) {
  return `${dateText.slice(0, 7)}-01`;
}

export function parseYear(dateText: string) {
  return Number(dateText.slice(0, 4));
}

export function parseMonth(dateText: string) {
  return Number(dateText.slice(5, 7));
}

export function addMonths(anchor: string, delta: number) {
  const year = parseYear(anchor);
  const month = parseMonth(anchor);
  const total = year * 12 + (month - 1) + delta;
  const nextYear = Math.floor(total / 12);
  const nextMonth = (total % 12) + 1;
  return `${nextYear}-${String(nextMonth).padStart(2, "0")}-01`;
}

export function monthAnchorsInRange(startAnchor: string, endAnchor: string) {
  const anchors: string[] = [];
  let current = firstOfMonth(startAnchor);
  const target = firstOfMonth(endAnchor);
  while (current <= target) {
    anchors.push(current);
    current = addMonths(current, 1);
  }
  return anchors;
}

export function yearMonthAnchors(year: number) {
  return Array.from(
    { length: 12 },
    (_, index) => `${year}-${String(index + 1).padStart(2, "0")}-01`,
  );
}

export function monthLabel(anchor: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${anchor}T12:00:00Z`));
}

export function monthTitle(anchor: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${anchor}T12:00:00Z`));
}

export function yearLabel(anchor: string) {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${anchor}T12:00:00Z`));
}

export function formatDayNumber(dateText: string) {
  return Number(dateText.slice(8, 10));
}

export function formatLongDate(dateText: string) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${dateText}T12:00:00Z`));
}

export function formatShortDate(dateText: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${dateText}T12:00:00Z`));
}

export function formatCalendarCaption(dateText: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${dateText}T12:00:00Z`));
}

type EventDateFields = Pick<EventCard, "start_time_utc" | "start_time_local" | "calendar_date">;

export function eventInstant(event: EventDateFields) {
  for (const source of [event.start_time_utc, event.start_time_local]) {
    // A source wall clock without an offset is not an instant. Never interpret
    // it in the visitor's timezone or invent a clock for a date-only record.
    if (!source || !/T.*(?:Z|[+-]\d{2}:?\d{2})$/i.test(source)) continue;
    const value = Date.parse(source);
    if (!Number.isNaN(value)) return value;
  }
  return null;
}

export function eventCalendarDate(event: EventDateFields, timezone: string) {
  const instant = eventInstant(event);
  return instant === null ? event.calendar_date : zonedDateText(new Date(instant), timezone);
}

export function eventTimestamp(event: EventDateFields) {
  return eventInstant(event) ?? (event.calendar_date
    ? Date.parse(`${event.calendar_date}T12:00:00Z`)
    : Number.MAX_SAFE_INTEGER);
}

function timeFormatter(timezone: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZone: safeTimezone(timezone),
  });
}

export function eventTimeLabel(event: EventCard, timezone: string) {
  const instant = eventInstant(event);
  return instant === null ? "Time TBD" : timeFormatter(timezone).format(new Date(instant));
}

export function eventTimeBucket(event: EventCard, timezone: string) {
  const instant = eventInstant(event);
  return instant === null ? "tbd" : new Intl.DateTimeFormat("en-US", {
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: safeTimezone(timezone),
  }).format(new Date(instant));
}

type MonthGridOptions = {
  showAdjacentDays?: boolean;
};

export function monthGridSunStart(
  anchor: string,
  groups: CalendarDayGroup[],
  options: MonthGridOptions = {},
) {
  const showAdjacentDays = options.showAdjacentDays ?? true;
  const year = parseYear(anchor);
  const month = parseMonth(anchor);
  const monthStart = new Date(Date.UTC(year, month - 1, 1, 12));
  const firstWeekday = monthStart.getUTCDay();
  const totalDays = daysInMonth(year, month);
  const groupByDate = new Map(groups.map((group) => [group.date, group]));
  const cells: MonthGridCell[] = [];

  for (let index = firstWeekday; index > 0; index -= 1) {
    if (!showAdjacentDays) {
      cells.push({ date: null, inMonth: false });
      continue;
    }
    const date = new Date(Date.UTC(year, month - 1, 1 - index, 12));
    cells.push({
      date: date.toISOString().slice(0, 10),
      inMonth: false,
    });
  }

  for (let day = 1; day <= totalDays; day += 1) {
    const date = `${year}-${pad(month)}-${pad(day)}`;
    cells.push({ date, inMonth: true, group: groupByDate.get(date) });
  }

  let trailingDay = 1;
  while (cells.length % 7 !== 0) {
    if (!showAdjacentDays) {
      cells.push({ date: null, inMonth: false });
      continue;
    }
    const date = new Date(Date.UTC(year, month - 1, totalDays + trailingDay, 12));
    cells.push({
      date: date.toISOString().slice(0, 10),
      inMonth: false,
    });
    trailingDay += 1;
  }

  return cells;
}

export function monthWeeksSunStart(
  anchor: string,
  groups: CalendarDayGroup[],
  options: MonthGridOptions = {},
) {
  const cells = monthGridSunStart(anchor, groups, options);
  const weeks: MonthGridCell[][] = [];
  for (let index = 0; index < cells.length; index += 7) {
    weeks.push(cells.slice(index, index + 7));
  }
  return weeks;
}

export function weekAnchorForCells(
  cells: MonthGridCell[],
  fallbackAnchor: string,
) {
  const inMonth = cells.find((cell) => cell.inMonth && cell.date)?.date;
  if (inMonth) {
    return inMonth;
  }
  return cells.find((cell) => cell.date)?.date || fallbackAnchor;
}

export function countAppliedFilters(filters: FilterState) {
  return (
    Number(Boolean(filters.sport)) +
    Number(Boolean(filters.league)) +
    Number(Boolean(filters.competition_phase)) +
    Number(Boolean(filters.country)) +
    Number(Boolean(filters.city)) +
    filters.tags.length
  );
}
