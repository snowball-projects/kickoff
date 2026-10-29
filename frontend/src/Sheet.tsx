import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { countryIdentity } from "./countries";
import { compareEvents, leagueGroups, leagueVisual } from "./calendar-helpers";
import { eventTimeLabel, formatLongDate } from "./date-utils";
import { EventFlags, SportIcon } from "./EventIdentity";
import type { EventCard } from "./types";

export default function Sheet({ title, onClose, children }: {
  title: string; onClose: () => void; children: React.ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const backdrop = useRef(false);
  const drag = useRef<number | null>(null);
  const dismissing = useRef(false);
  const [closing, setClosing] = useState(false);
  function dismiss() {
    if (dismissing.current) return;
    dismissing.current = true;
    setClosing(true);
  }
  useEffect(() => {
    const element = dialog.current!;
    const opener = document.activeElement;
    element.showModal();
    return () => {
      element.close();
      const target = opener instanceof HTMLElement && opener.isConnected && opener.getClientRects().length
        ? opener : document.querySelector<HTMLElement>(".today-button");
      target?.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    if (!closing) return;
    const timer = setTimeout(onClose, matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 180);
    return () => clearTimeout(timer);
  }, [closing, onClose]);
  function outside(event: React.PointerEvent<HTMLDialogElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return event.target === event.currentTarget && (event.clientX < rect.left || event.clientX > rect.right
      || event.clientY < rect.top || event.clientY > rect.bottom);
  }
  return <dialog ref={dialog} className={`sheet ${closing ? "closing" : ""}`} aria-label={title}
    onKeyDown={(event) => {
      if (event.key !== "Tab") return;
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>("button, a[href], input, select, textarea, summary, [tabindex]:not([tabindex='-1'])")]
        .filter((element) => !element.matches(":disabled") && element.getClientRects().length);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}
    onCancel={(event) => { event.preventDefault(); dismiss(); }}
    onPointerDown={(event) => { backdrop.current = outside(event); }}
    onPointerUp={(event) => { if (backdrop.current && outside(event)) dismiss(); backdrop.current = false; }}
    onPointerCancel={() => { backdrop.current = false; drag.current = null; }}>
    <header className="sheet-header"
      onPointerDown={(event) => { if (event.pointerType === "touch" && !(event.target as HTMLElement).closest("button")) { drag.current = event.clientY;
        if (event.isTrusted) event.currentTarget.setPointerCapture(event.pointerId); } }}
      onPointerUp={(event) => { if (drag.current !== null && event.clientY - drag.current > 64) dismiss(); drag.current = null; }}>
      <span className="grabber" aria-hidden="true" />
      <button className="icon-button sheet-close" aria-label="Close" onClick={dismiss}>×</button>
      <h2>{title}</h2>
    </header>
    <div className="sheet-body">{children}</div>
  </dialog>;
}
function EventDetails({ event, date, timezone }: { event: EventCard; date: string; timezone: string }) {
  const location = [event.venue, event.city, countryIdentity(event.country)?.name || event.country].filter(Boolean).join(" · ");
  const start = event.start_calendar_date || date;
  const end = event.end_calendar_date;
  return <article className="event-details" aria-label="Event details">
    <span className={`league-label ${leagueVisual(event.league, event.sport).className}`}>
      <SportIcon league={event.league} sport={event.sport} />{leagueVisual(event.league, event.sport).shortLabel}
    </span>
    <h3 tabIndex={-1}><EventFlags event={event} />{event.title}</h3>
    {event.subtitle && <p>{event.subtitle}</p>}
    <p className="detail-time">{eventTimeLabel(event, timezone)}</p>
    <p>{formatLongDate(start)}{end && end > start && <> through {formatLongDate(end)}</>}</p>
    {event.tags.includes("final date only") && <p>Final date only</p>}
    {location && <p>{location}</p>}
    {event.status !== "scheduled" && <p>{event.status.replaceAll("_", " ")}</p>}
    <div className="source-links">
      {event.source_url && <a href={event.source_url} target="_blank" rel="noreferrer">Schedule source ↗</a>}
      {event.start_time_source_url && <a href={event.start_time_source_url} target="_blank" rel="noreferrer">
        Time source: {event.start_time_source === "espn" ? "ESPN" : event.start_time_source} ↗
      </a>}
    </div>
  </article>;
}
export function EventSheet({ items, date, timezone, onClose }: {
  items: EventCard[]; date: string; timezone: string; onClose: () => void;
}) {
  const [selected, setSelected] = useState<EventCard | null>(items.length === 1 ? items[0] : null);
  const body = useRef<HTMLDivElement>(null);
  const lastRow = useRef<string | null>(null);
  useLayoutEffect(() => {
    if (selected) body.current?.querySelector<HTMLElement>("h3")?.focus({ preventScroll: true });
    else if (lastRow.current) { const row = document.getElementById(`sheet-${lastRow.current}`);
      row?.focus({ preventScroll: true }); row?.scrollIntoView({ block: "nearest" }); }
  }, [selected]);
  const groups = leagueGroups(items);
  const title = groups.length === 1 ? leagueVisual(items[0].league, items[0].sport).shortLabel : "Events";
  return <Sheet title={title} onClose={onClose}>
    <div ref={body}>
      {selected ? <>
        {items.length > 1 && <button className="sheet-back" aria-label="Back to events" onClick={() => setSelected(null)}>‹ {title}</button>}
        <EventDetails event={selected} date={date} timezone={timezone} />
      </> : groups.map((group) => <section className="sheet-event-group" key={group.league}>
        {groups.length > 1 && <h3>{leagueVisual(group.league, group.items[0].sport).shortLabel}</h3>}
        {[...group.items].sort(compareEvents).map((event) => <button className="sheet-event-row" key={event.event_id} id={`sheet-${event.event_id}`}
          onClick={() => { lastRow.current = event.event_id; setSelected(event); }}>
          <span>{eventTimeLabel(event, timezone)}</span><b><EventFlags event={event} />{event.title}</b><span aria-hidden="true">›</span>
        </button>)}
      </section>)}
    </div>
  </Sheet>;
}
