import { eventInstant, safeTimezone, todayIso } from "./date-utils";
import { monthCompetitions } from "./month-competitions";
import type { EventCard } from "./types";

export const HOUR_HEIGHT = 80;
export const PILL_HEIGHT = 44;
export const DAY_HEIGHT = HOUR_HEIGHT * 24;

// A wall-clock grid always has 24 fixed hours, including DST transition days.
// Repeated local clocks share a slot; no duration or end time is inferred.
export function clockMinute(instant: number, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: safeTimezone(timezone),
  }).formatToParts(instant);
  return Number(parts.find((part) => part.type === "hour")!.value) * 60
    + Number(parts.find((part) => part.type === "minute")!.value);
}

export function isAllDay(event: EventCard) {
  const start = event.start_calendar_date || event.calendar_date;
  return eventInstant(event) === null || event.tags.includes("final date only")
    || !!(start && event.end_calendar_date && event.end_calendar_date > start);
}

export function dayTimeline(items: EventCard[], timezone: string) {
  const allDay = monthCompetitions(items.filter(isAllDay));
  const timed = monthCompetitions(items.filter((event) => !isAllDay(event))).map((group) => {
    const slots = new Map<number, EventCard[]>();
    for (const event of group.items) {
      const minute = clockMinute(eventInstant(event)!, timezone);
      if (!slots.has(minute)) slots.set(minute, []);
      slots.get(minute)!.push(event);
    }
    const times = [...slots].sort(([a], [b]) => a - b).map(([minute, events]) => ({ minute, events }));
    return { ...group, times, minute: times[0].minute, lastMinute: times.at(-1)!.minute };
  }).sort((a, b) => a.minute - b.minute || a.key.localeCompare(b.key));
  return { allDay, timed };
}

export type TimedGroup = ReturnType<typeof dayTimeline>["timed"][number];

// Allocate horizontal lanes to overlapping visible pills/groups. Expansion only
// changes lanes and the translucent bounds, never the hour grid or minute offsets.
function packLanes<T>(values: { value: T; top: number; end: number }[]) {
  const entries = values.map((entry) => ({ ...entry, lane: 0, columns: 1 }));
  let cluster: typeof entries = [];
  let clusterEnd = -1;
  const finish = () => {
    const columns = Math.max(1, ...cluster.map((entry) => entry.lane + 1));
    cluster.forEach((entry) => { entry.columns = columns; });
  };
  for (const entry of entries) {
    if (entry.top >= clusterEnd) { finish(); cluster = []; clusterEnd = -1; }
    const occupied = new Set(cluster.filter((previous) => previous.end > entry.top).map((previous) => previous.lane));
    while (occupied.has(entry.lane)) entry.lane++;
    cluster.push(entry);
    clusterEnd = Math.max(clusterEnd, entry.end);
  }
  finish();
  return entries;
}

export function timelineLanes(groups: TimedGroup[], expanded: Set<string>) {
  return packLanes(groups.map((group) => ({ value: group, top: group.minute * HOUR_HEIGHT / 60,
    end: (expanded.has(group.key) ? group.lastMinute : group.minute) * HOUR_HEIGHT / 60 + PILL_HEIGHT,
  }))).map(({ value, ...position }) => ({ group: value, ...position }));
}

export function slotLanes(group: TimedGroup) {
  return packLanes(group.times.map((slot) => ({ value: slot,
    top: (slot.minute - group.minute) * HOUR_HEIGHT / 60,
    end: (slot.minute - group.minute) * HOUR_HEIGHT / 60 + PILL_HEIGHT,
  }))).map(({ value, ...position }) => ({ ...value, ...position }));
}

export function visibleSlot(events: EventCard[]) {
  return events.length <= 3 ? { shown: events, more: [] as EventCard[] }
    : { shown: events.slice(0, 2), more: events.slice(2) };
}

export function initialMinute(date: string, timezone: string, firstMinute?: number, now = Date.now()) {
  return date === todayIso(timezone, new Date(now)) ? clockMinute(now, timezone) : firstMinute ?? 0;
}

export function hourLabel(hour: number) {
  return `${hour % 12 || 12}${hour % 24 < 12 ? "am" : "pm"}`;
}
