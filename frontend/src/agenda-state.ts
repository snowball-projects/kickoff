import { addMonths, firstOfMonth, monthAnchorsInRange, eventInstant, formatShortDate, yearMonthAnchors } from "./date-utils";
import { dayAfter } from "./month-feed-state";
import type { CalendarResponse, EventCard } from "./types";

export type AgendaPeriod = "yesterday" | "today" | "upcoming";
export type ScheduleView = "calendar" | "agenda";
export const VIEW_KEY = "kickoff.view.v1";

export function readScheduleView(storage: Pick<Storage, "getItem">): ScheduleView {
  try { return storage.getItem(VIEW_KEY) === "agenda" ? "agenda" : "calendar"; }
  catch { return "calendar"; }
}

// Calendar arithmetic on local date labels, not 24-hour durations (DST).
export function agendaDates(today: string, period: AgendaPeriod, until = dayAfter(today, 7)) {
  if (period !== "upcoming") return [dayAfter(today, period === "yesterday" ? -1 : 0)];
  const dates: string[] = [];
  for (let date = dayAfter(today, 1); date <= until; date = dayAfter(date, 1)) dates.push(date);
  return dates;
}

export function agendaAnchors(today: string) {
  return monthAnchorsInRange(dayAfter(today, -1), dayAfter(today, 7));
}

// Bundle metadata bounds discovery; never probe successive unpublished years.
export function laterAgendaAnchors(today: string, publishedYears: number[]) {
  const years = [...new Set(publishedYears)].filter((year) => Number.isInteger(year) && year >= 1900 && year <= 2100);
  // The source's last December can move into local January or contain a span.
  return [...new Set(years.flatMap((year) => [
    ...yearMonthAnchors(year), ...(year < 2100 ? [addMonths(`${year}-12-01`, 1)] : []),
  ]))].filter((anchor) => anchor >= firstOfMonth(dayAfter(today, -1))).sort();
}

// Extend by occupied dates, so sparse interests do not require clicking through empty weeks.
export function nextAgendaEnd(months: Record<string, CalendarResponse>, until: string) {
  return [...new Set(Object.values(months).flatMap((month) => month.groups)
    .filter((group) => group.date > until && group.items.length).map((group) => group.date))]
    .sort().slice(0, 7).at(-1) || null;
}

export function agendaGroups(months: Record<string, CalendarResponse>, dates: string[]) {
  return dates.map((date) => ({
    date,
    // Reuse the calendar's zoned groups, including inclusive date-only spans.
    items: [...(months[firstOfMonth(date)]?.groups.find((group) => group.date === date)?.items || [])]
      .sort((a, b) => (eventInstant(a) ?? Infinity) - (eventInstant(b) ?? Infinity) || a.event_id.localeCompare(b.event_id)),
  }));
}

export function agendaScopeLabel(event: EventCard, date: string) {
  if (event.tags.includes("final date only")) return "Final date only";
  return event.end_calendar_date && event.end_calendar_date > date
    ? `Through ${formatShortDate(event.end_calendar_date)}` : "";
}
