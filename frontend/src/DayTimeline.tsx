import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { eventTimeLabel } from "./date-utils";
import { DAY_HEIGHT, HOUR_HEIGHT, currentMinute, dayOverflow, dayTimeline, hourLabel, initialMinute } from "./day-timeline";
import DayPill from "./DayPill";
import { dayPillTeams } from "./day-pill";
import type { EventCard } from "./types";

export default function DayTimeline({ date, timezone, now, items, loading, error, onEvents, onRetry }: {
  date: string; timezone: string; now: number; items: EventCard[]; loading: boolean; error?: string;
  onEvents: (events: EventCard[], date: string) => void; onRetry: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  const { slots, allDay } = useMemo(() => dayTimeline(items, timezone), [items, timezone]);
  const [unreadable, setUnreadable] = useState<ReadonlySet<string>>(() => new Set());
  const pendingFocus = useRef<{ eventId: string; overflow: boolean; top?: number } | null>(null);
  const onOverflowChange = useCallback((eventId: string, needed: boolean) => {
    setUnreadable((current) => {
      if (current.has(eventId) === needed) return current;
      const next = new Set(current);
      if (needed) next.add(eventId); else next.delete(eventId);
      const active = document.activeElement as HTMLElement | null;
      if (needed && active?.dataset.eventId === eventId) pendingFocus.current = { eventId, overflow: true };
      else if (active?.classList.contains("timeline-more")) {
        const previous = dayOverflow(slots, current).find((slot) => slot.overflow && String(slot.top) === active.dataset.overflowTop);
        const remains = dayOverflow(slots, next).find((slot) => slot.overflow && String(slot.top) === active.dataset.overflowTop);
        if (remains) pendingFocus.current = { eventId, overflow: true, top: remains.top };
        else if (previous?.items.some((event) => event.event_id === eventId)) pendingFocus.current = { eventId, overflow: false };
      }
      return next;
    });
  }, [slots]);
  const overflowSlots = dayOverflow(slots, unreadable).filter((slot) => slot.overflow);
  const sourceId = (eventId: string) => `day-event-${date}-${eventId}`;
  const overflowId = (top: number) => `day-more-${date}-${top}`;
  const suppressedIds = new Set(slots.filter((slot) => !slot.overflow && unreadable.has(slot.items[0].event_id)).map((slot) => slot.items[0].event_id));
  useLayoutEffect(() => {
    const focus = pendingFocus.current;
    if (!focus) return;
    pendingFocus.current = null;
    if (focus.overflow) {
      const slot = overflowSlots.find((slot) => focus.top !== undefined ? slot.top === focus.top : slot.items.some((event) => event.event_id === focus.eventId));
      const button = [...scroller.current!.querySelectorAll<HTMLButtonElement>(".timeline-more")]
        .find((element) => element.dataset.overflowTop === String(slot?.top));
      button?.focus({ preventScroll: true });
    } else {
      const button = [...scroller.current!.querySelectorAll<HTMLButtonElement>("[data-event-id]")]
        .find((element) => element.dataset.eventId === focus.eventId);
      button?.focus({ preventScroll: true });
    }
  }, [overflowSlots]);
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
      <div>{allDay.flatMap((group) => group.items).map((event) => <DayPill key={event.event_id} event={event}
        data-event-id={event.event_id} aria-label={event.title} onClick={() => onEvents([event], date)} />)}</div>
    </div>
    <div ref={scroller} className="timeline-scroll" tabIndex={0} aria-label="Hourly timeline">
      <div className="timeline-grid" style={{ height: DAY_HEIGHT }}>
        {Array.from({ length: 25 }, (_, hour) => <div key={hour} className="timeline-hour" style={{ top: hour * HOUR_HEIGHT }}>
          <span>{hourLabel(hour)}</span>
        </div>)}
        <div className="timeline-events">
          {slots.flatMap((slot) => {
            const event = slot.items[0];
            const style = { top: slot.top, left: `${slot.lane * 100 / slot.columns}%`, width: `calc(${100 / slot.columns}% - 4px)` };
            const more = overflowSlots.find((entry) => entry.top === slot.top && entry.lane === slot.lane);
            const names = more?.items.filter((item) => suppressedIds.has(item.event_id)).map((item) => {
              const matchup = dayPillTeams(item);
              if (matchup) return matchup.teams.map((team) => team.name).join(` ${matchup.separator} `);
              const knownNames = item.participants.map((team) => team.name).filter((name) => !item.title.toLowerCase().includes(name.toLowerCase()));
              return [item.title, ...knownNames].join("; ");
            }) || [];
            const restored = more?.items.find((item) => suppressedIds.has(item.event_id)) || event;
            return [
              !slot.overflow && <DayPill key={`event:${event.event_id}`} event={event} compact={slot.columns === 3} style={style} data-event-id={event.event_id}
                id={sourceId(event.event_id)}
                data-focus-return={overflowId(overflowSlots.find((entry) => entry.items.some((item) => item.event_id === event.event_id))?.top ?? slot.top)}
                suppressed={unreadable.has(event.event_id)} onOverflowChange={onOverflowChange}
                aria-label={[event.title, eventTimeLabel(event, timezone)].filter(Boolean).join(", ")} onClick={() => onEvents([event], date)} />,
              more && <button key={`more:${more.top}`} id={overflowId(more.top)} data-focus-return={sourceId(restored.event_id)}
                className="timeline-more" style={style} data-overflow-top={more.top}
                aria-label={[[`${more.items.length} more events`, eventTimeLabel(more.items[0], timezone)].filter(Boolean).join(" at "), ...names].join(", ")}
                onClick={() => onEvents(more.items, date)}>+{more.items.length}</button>,
            ];
          })}
        </div>
        {minute !== null && <div className="timeline-now" style={{ top: minute * HOUR_HEIGHT / 60 }}>
          <time dateTime={new Date(now).toISOString()} aria-label={`Current time, ${time}${minute < 720 ? "am" : "pm"}`}>{time}</time>
        </div>}
      </div>
    </div>
  </section>;
}
