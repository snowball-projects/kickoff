import { useLayoutEffect, useRef } from "react";
import { eventTimeLabel } from "./date-utils";
import { DAY_HEIGHT, HOUR_HEIGHT, currentMinute, dayTimeline, hourLabel, initialMinute } from "./day-timeline";
import EventPill from "./EventPill";
import type { EventCard } from "./types";

export default function DayTimeline({ date, timezone, now, items, loading, error, onEvents, onRetry }: {
  date: string; timezone: string; now: number; items: EventCard[]; loading: boolean; error?: string;
  onEvents: (events: EventCard[], date: string) => void; onRetry: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  const { slots, allDay } = dayTimeline(items, timezone);
  const minute = currentMinute(date, timezone, now);
  const time = minute === null ? "" : `${Math.floor(minute / 60) % 12 || 12}:${String(minute % 60).padStart(2, "0")}`;
  useLayoutEffect(() => {
    if (loading || initialized.current) return;
    initialized.current = true;
    scroller.current!.scrollTop = Math.max(0, initialMinute(date, timezone, slots[0] ? slots[0].top * 60 / HOUR_HEIGHT : undefined, now) * HOUR_HEIGHT / 60 - 40);
  }, [loading, date, timezone, slots, now]);
  return <section className="day-timeline-stage" aria-label="Day events">
    {error && <div className="schedule-notice" role="status">{error} <button onClick={onRetry}>Retry</button></div>}
    {loading && <p className="loading-note" role="status">Loading schedule…</p>}
    <div className="all-day-strip" aria-label="All-day events">
      <span className="all-day-label">all-day</span>
      <div>{allDay.map((group) => <EventPill key={group.items[0].event_id} items={group.items} onClick={() => onEvents(group.items, date)}>
        {group.items.length === 1 ? group.items[0].title : undefined}
      </EventPill>)}</div>
    </div>
    <div ref={scroller} className="timeline-scroll" tabIndex={0} aria-label="Hourly timeline">
      <div className="timeline-grid" style={{ height: DAY_HEIGHT }}>
        {Array.from({ length: 25 }, (_, hour) => <div key={hour} className="timeline-hour" style={{ top: hour * HOUR_HEIGHT }}>
          <span>{hourLabel(hour)}</span>
        </div>)}
        <div className="timeline-events">
          {slots.map((slot) => {
            const event = slot.items[0];
            const style = { top: slot.top, left: `${slot.lane * 100 / slot.columns}%`, width: `calc(${100 / slot.columns}% - 4px)` };
            return slot.overflow ? <button key={`more-${slot.top}`} className="timeline-more" style={style}
              aria-label={[`${slot.items.length} more events`, eventTimeLabel(event, timezone)].filter(Boolean).join(" at ")}
              onClick={() => onEvents(slot.items, date)}>+{slot.items.length}</button>
              : <EventPill key={event.event_id} items={[event]} style={style} data-event-id={event.event_id}
                aria-label={[event.title, eventTimeLabel(event, timezone)].filter(Boolean).join(", ")} onClick={() => onEvents([event], date)}>
                {event.title}
              </EventPill>;
          })}
        </div>
        {minute !== null && <div className="timeline-now" style={{ top: minute * HOUR_HEIGHT / 60 }}>
          <time dateTime={new Date(now).toISOString()} aria-label={`Current time, ${time}${minute < 720 ? "am" : "pm"}`}>{time}</time>
        </div>}
      </div>
    </div>
  </section>;
}
