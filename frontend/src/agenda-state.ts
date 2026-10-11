import { firstOfMonth, monthAnchorsInRange, eventInstant, formatShortDate } from "./date-utils";
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
export function agendaDates(today: string, period: AgendaPeriod) {
  const offsets = period === "yesterday" ? [-1] : period === "today" ? [0] : [1, 2, 3, 4, 5, 6, 7];
  return offsets.map((offset) => dayAfter(today, offset));
}

export function agendaAnchors(today: string) {
  return monthAnchorsInRange(dayAfter(today, -1), dayAfter(today, 7));
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
