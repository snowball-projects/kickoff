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

function localDateText(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month, 0).getDate();
}

export function todayIso() {
  return localDateText(new Date());
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
  }).format(new Date(`${anchor}T12:00:00`));
}

export function monthTitle(anchor: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
  }).format(new Date(`${anchor}T12:00:00`));
}

export function yearLabel(anchor: string) {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
  }).format(new Date(`${anchor}T12:00:00`));
}

export function formatDayNumber(dateText: string) {
  return new Date(`${dateText}T12:00:00`).getDate();
}

export function formatLongDate(dateText: string) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${dateText}T12:00:00`));
}

export function formatShortDate(dateText: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(`${dateText}T12:00:00`));
}

export function formatCalendarCaption(dateText: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${dateText}T12:00:00`));
}

export function eventTimestamp(event: EventCard) {
  const source = event.start_time_utc || event.start_time_local;
  if (source) {
    const value = Date.parse(source);
    if (!Number.isNaN(value)) {
      return value;
    }
  }
  if (event.calendar_date) {
    return Date.parse(`${event.calendar_date}T12:00:00`);
  }
  return Number.MAX_SAFE_INTEGER;
}

function timeFormatter(timezone: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZone: timezone,
  });
}

export function eventTimeLabel(event: EventCard, timezone: string) {
  if (event.start_time_utc) {
    return timeFormatter(timezone).format(new Date(event.start_time_utc));
  }
  if (event.start_time_local) {
    const parsed = Date.parse(event.start_time_local);
    if (!Number.isNaN(parsed)) {
      return timeFormatter(timezone).format(new Date(parsed));
    }
  }
  return "Time TBD";
}

export function eventTimeBucket(event: EventCard, timezone: string) {
  if (event.start_time_utc) {
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: timezone,
    }).format(new Date(event.start_time_utc));
  }
  if (event.start_time_local) {
    const parsed = Date.parse(event.start_time_local);
    if (!Number.isNaN(parsed)) {
      return new Intl.DateTimeFormat("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: timezone,
      }).format(new Date(parsed));
    }
  }
  return "tbd";
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
  const monthStart = new Date(year, month - 1, 1, 12);
  const firstWeekday = monthStart.getDay();
  const totalDays = daysInMonth(year, month);
  const groupByDate = new Map(groups.map((group) => [group.date, group]));
  const cells: MonthGridCell[] = [];

  for (let index = firstWeekday; index > 0; index -= 1) {
    if (!showAdjacentDays) {
      cells.push({ date: null, inMonth: false });
      continue;
    }
    const date = new Date(year, month - 1, 1 - index, 12);
    cells.push({
      date: localDateText(date),
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
    const date = new Date(year, month - 1, totalDays + trailingDay, 12);
    cells.push({
      date: localDateText(date),
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
