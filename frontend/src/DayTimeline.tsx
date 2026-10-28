import { useLayoutEffect, useRef, useState } from "react";
import { leagueVisual } from "./calendar-helpers";
import { eventTimeLabel } from "./date-utils";
import { DAY_HEIGHT, HOUR_HEIGHT, PILL_HEIGHT, dayTimeline, hourLabel, initialMinute, timelineLanes, visibleSlot } from "./day-timeline";
import { EventFlags, SportIcon } from "./EventIdentity";
import EventPreview, { useEventPreview } from "./EventPreview";
import type { EventCard } from "./types";

export default function DayTimeline({ date, timezone, items, loading, error, selectedId, onSelect, renderDetails }: {
  date: string; timezone: string; items: EventCard[]; loading: boolean; error?: string;
  selectedId?: string; onSelect: (id?: string) => void; renderDetails: (event: EventCard) => React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(new Set<string>());
  const [overflow, setOverflow] = useState<string[]>([]);
  const scroller = useRef<HTMLDivElement>(null);
  const details = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const initialized = useRef(false);
  const preview = useEventPreview();
  const { timed, allDay } = dayTimeline(items, timezone);
  const overflowItems = overflow.flatMap((id) => items.filter((event) => event.event_id === id));
  const selected = items.find((event) => event.event_id === selectedId);
  useLayoutEffect(() => {
    if (loading || initialized.current) return;
    initialized.current = true;
    scroller.current!.scrollTop = Math.max(0, initialMinute(date, timezone, timed[0]?.minute) * HOUR_HEIGHT / 60 - 40);
  }, [loading, date, timezone, timed]);
  useLayoutEffect(() => {
    if (selected || overflow.length) details.current?.focus({ preventScroll: true });
  }, [selected?.event_id, overflow]);
  function toggle(key: string) {
    preview.close();
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }
  function closeDetails() {
    onSelect(undefined);
    if (selected && overflowItems.length) return;
    setOverflow([]);
    opener.current?.focus({ preventScroll: true });
  }
  function pill(event: EventCard) {
    return <button key={event.event_id} data-event-id={event.event_id}
      className={`timeline-pill ${leagueVisual(event.league, event.sport).className}`}
      onClick={(click) => {
        preview.close();
        if (!click.currentTarget.closest(".timeline-details")) {
          setOverflow([]);
          opener.current = click.currentTarget;
        }
        onSelect(event.event_id);
      }}
      onPointerEnter={(pointer) => {
        if (pointer.pointerType !== "touch") preview.show({ event, date, target: pointer.currentTarget });
      }} onPointerLeave={preview.leave}
      onFocus={(focus) => {
        if (focus.currentTarget.matches(":focus-visible")) preview.show({ event, date, target: focus.currentTarget });
      }} onBlur={preview.close}
      aria-describedby={preview.preview?.event.event_id === event.event_id ? "event-preview" : undefined}>
      <span className="timeline-title"><SportIcon league={event.league} sport={event.sport} /><EventFlags event={event} />{event.title}</span>
      <span className="timeline-clock">{eventTimeLabel(event, timezone)}{event.status !== "scheduled" && ` · ${event.status.replaceAll("_", " ")}`}</span>
    </button>;
  }
  function groupButton(key: string, name: string, events: EventCard[], open: boolean, controls: string, compact = false) {
    return <button className={`timeline-pill timeline-group-toggle ${compact ? "timeline-collapse" : ""} ${leagueVisual(events[0].league, events[0].sport).className}`}
      aria-expanded={open} aria-controls={controls} aria-label={compact ? `Collapse ${name}` : undefined} onClick={() => toggle(key)}
      onPointerEnter={(pointer) => {
        if (pointer.pointerType !== "touch" && !open) preview.show({ event: events[0], date, target: pointer.currentTarget });
      }} onPointerLeave={preview.leave}
      onFocus={(focus) => {
        if (!open && focus.currentTarget.matches(":focus-visible")) preview.show({ event: events[0], date, target: focus.currentTarget });
      }} onBlur={preview.close}
      aria-describedby={!open && preview.preview?.event.event_id === events[0].event_id ? "event-preview" : undefined}>
      {compact && <span aria-hidden="true">−</span>}
      <span className="timeline-title"><SportIcon league={events[0].league} sport={events[0].sport} />{name}</span>
      <span className="timeline-clock">{events.length} {events.every((event) => ["game", "match"].includes(event.event_type)) ? "games" : "events"} · {eventTimeLabel(events[0], timezone)}{[...new Set(events.filter((event) => event.status !== "scheduled").map((event) => event.status.replaceAll("_", " ")))].map((status) => ` · ${status}`)} · {open ? "−" : "+"}</span>
    </button>;
  }
  return <>
    {!!allDay.length && <section className="timeline-all-day" aria-label="All-day events">
      <span className="all-day-label">All-day</span>
      <div className="all-day-pills">
        {allDay.map((group, index) => <div key={group.key}>
          {group.items.length === 1 ? pill(group.items[0]) : <>
            {groupButton(`all-day:${group.key}`, group.name, group.items, expanded.has(`all-day:${group.key}`), `all-day-group-${index}`)}
            <div id={`all-day-group-${index}`} hidden={!expanded.has(`all-day:${group.key}`)} className="all-day-children">{group.items.map(pill)}</div>
          </>}
        </div>)}
      </div>
    </section>}
    <div className="day-scroll" ref={scroller} tabIndex={0} role="region" aria-label="Day timeline" onScroll={preview.close}
      onKeyDown={(event) => {
        if (event.key === "Escape" && preview.preview) { event.stopPropagation(); preview.close(); }
      }}>
      <div className="timeline-grid" style={{ height: DAY_HEIGHT + PILL_HEIGHT + 16 }}>
        {Array.from({ length: 25 }, (_, hour) => <div className="timeline-hour" key={hour} style={{ top: hour * HOUR_HEIGHT }}>
          <span>{hourLabel(hour)}</span><i />
        </div>)}
        <div className="timeline-events">
          {timelineLanes(timed, expanded).map(({ group, top, end, lane, columns, slots }, index) => {
            const open = expanded.has(group.key) && group.items.length > 1;
            const id = `timeline-group-${index}`;
            return <div key={group.key} data-competition={group.name} className={`timeline-group ${open ? "is-expanded" : ""} ${leagueVisual(group.items[0].league, group.items[0].sport).className}`}
              style={{ top, height: end - top, left: `${lane * 100 / columns}%`, width: `${100 / columns}%` }}>
              {group.items.length === 1 ? pill(group.items[0])
                : groupButton(group.key, group.name, group.items, open, id, open)}
              {group.items.length > 1 && <div id={id} hidden={!open} className="timeline-subpills">
                {slots.map(({ minute, events, top: slotTop, lane: slotLane, columns: slotColumns }) => {
                  const { shown, more } = visibleSlot(events);
                  return <div className="timeline-slot" key={minute} style={{ top: slotTop, left: `${slotLane * 100 / slotColumns}%`, width: `${100 / slotColumns}%` }}>
                    {shown.map(pill)}
                    {!!more.length && <button className="timeline-pill timeline-more" onClick={(click) => {
                      preview.close(); onSelect(undefined); opener.current = click.currentTarget; setOverflow(more.map((event) => event.event_id));
                    }}>+{more.length} more<span className="sr-only"> · {group.name} · {eventTimeLabel(events[0], timezone)}</span></button>}
                  </div>;
                })}
              </div>}
            </div>;
          })}
        </div>
      </div>
    </div>
    {(loading || error || !items.length) && <p className="timeline-notice" role="status">{error || (loading ? "Loading…" : "No published events match this day.")}</p>}
    {(selected || !!overflowItems.length) && <section className="timeline-details" aria-label={selected ? "Event details" : "More events"}>
      <button className="icon-button" aria-label="Close details" onClick={closeDetails}>×</button>
      <div ref={details} tabIndex={-1} className="timeline-details-scroll">
        {selected ? renderDetails(selected) : <ul>{overflowItems.map((event) => <li key={event.event_id}>{pill(event)}</li>)}</ul>}
      </div>
    </section>}
    {preview.preview && <EventPreview preview={preview.preview} timezone={timezone} onEnter={preview.keep} onLeave={preview.leave} />}
  </>;
}
