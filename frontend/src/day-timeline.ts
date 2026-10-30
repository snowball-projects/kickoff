import { eventInstant, safeTimezone, todayIso } from "./date-utils";
import { compareEvents, pillGroups } from "./calendar-helpers";
import type { EventCard } from "./types";

export const HOUR_HEIGHT = 80;
export const PILL_HEIGHT = 28;
export const DAY_HEIGHT = HOUR_HEIGHT * 24;

// Wall-clock positions, including repeated DST clocks. No end time is inferred.
export function clockMinute(instant: number, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: safeTimezone(timezone),
  }).formatToParts(instant);
  return Number(parts.find((part) => part.type === "hour")!.value) * 60
    + Number(parts.find((part) => part.type === "minute")!.value);
}
export function isAllDay(event: EventCard) {
  const start = event.start_calendar_date || event.calendar_date;
  return eventInstant(event) === null
    || !!(start && event.end_calendar_date && event.end_calendar_date > start);
}
type Slot = { items: EventCard[]; top: number; lane: number; columns: number; overflow: boolean };
export function dayTimeline(items: EventCard[], timezone: string) {
  const timed = items.filter((event) => !isAllDay(event)).map((event) => ({
    event, top: clockMinute(eventInstant(event)!, timezone) * HOUR_HEIGHT / 60,
  })).sort((a, b) => a.top - b.top || compareEvents(a.event, b.event));
  const clusters: typeof timed[] = [];
  let end = -1;
  for (const entry of timed) {
    if (entry.top >= end) clusters.push([]);
    clusters.at(-1)!.push(entry);
    end = entry.top + PILL_HEIGHT;
  }
  const slots: Slot[] = [];
  for (const cluster of clusters) {
    const ends: number[] = [];
    const packed = cluster.map((entry) => {
      let lane = ends.findIndex((end) => end <= entry.top);
      if (lane < 0) lane = ends.length;
      ends[lane] = entry.top + PILL_HEIGHT;
      return { ...entry, lane };
    });
    const columns = Math.min(3, ends.length);
    if (ends.length <= 3) {
      slots.push(...packed.map(({ event, top, lane }) => ({ items: [event], top, lane, columns, overflow: false })));
      continue;
    }
    // Reserve the third lane for overflow. Nearby starts retain their real clocks.
    const visibleEnds = [0, 0];
    let overflow: Slot | undefined;
    for (const { event, top } of cluster) {
      const lane = visibleEnds.findIndex((end) => end <= top);
      if (lane >= 0) {
        visibleEnds[lane] = top + PILL_HEIGHT;
        slots.push({ items: [event], top, lane, columns, overflow: false });
      } else if (overflow && top < overflow.top + PILL_HEIGHT) overflow.items.push(event);
      else {
        overflow = { items: [event], top, lane: 2, columns, overflow: true };
        slots.push(overflow);
      }
    }
  }
  return { allDay: pillGroups(items.filter(isAllDay)), slots };
}
export function initialMinute(date: string, timezone: string, firstMinute?: number, now = Date.now()) {
  return date === todayIso(timezone, new Date(now)) ? clockMinute(now, timezone) : firstMinute ?? 0;
}
export function hourLabel(hour: number) {
  return `${hour % 12 || 12}${hour % 24 < 12 ? "am" : "pm"}`;
}
