import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { eventTimeLabel, formatLongDate } from "./date-utils";
import { leagueVisual } from "./calendar-helpers";
import type { EventCard } from "./types";

export type Preview = { event: EventCard; target: HTMLElement; date: string };

export function useEventPreview() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  function keep() { clearTimeout(timer.current); }
  function close() { keep(); setPreview(null); }
  function leave() { keep(); timer.current = setTimeout(() => setPreview(null), 160); }
  function show(value: Preview) { keep(); setPreview(value); }
  useEffect(() => {
    function escape(event: KeyboardEvent) { if (event.key === "Escape") close(); }
    document.addEventListener("keydown", escape);
    window.addEventListener("resize", close);
    return () => {
      keep();
      document.removeEventListener("keydown", escape);
      window.removeEventListener("resize", close);
    };
  }, []);
  return { preview, show, close, keep, leave };
}

export default function EventPreview({ preview, timezone, onEnter, onLeave }: {
  preview: Preview; timezone: string; onEnter: () => void; onLeave: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 8, top: 8 });
  useLayoutEffect(() => {
    const box = ref.current!.getBoundingClientRect();
    const target = preview.target.getBoundingClientRect();
    const below = target.bottom + 8;
    setPosition({
      left: Math.max(8, Math.min(target.left, window.innerWidth - box.width - 8)),
      top: Math.max(8, below + box.height <= window.innerHeight - 8
        ? below : target.top - box.height - 8),
    });
  }, [preview]);
  const { event } = preview;
  const location = [event.venue, event.city, event.country].filter(Boolean).join(" · ");
  const start = event.start_calendar_date || event.calendar_date || preview.date;
  return createPortal(
    <div ref={ref} id="event-preview" role="tooltip" className="event-preview"
      style={position} onPointerEnter={onEnter} onPointerLeave={onLeave}
      onPointerDown={(event) => event.stopPropagation()} onWheel={(event) => event.stopPropagation()}>
      <p className={`league-label ${leagueVisual(event.league).className}`}>{leagueVisual(event.league).shortLabel}</p>
      <h3>{event.title}</h3>
      <p>{event.tags.includes("final date only") && "Final date only · "}{formatLongDate(start)}{event.end_calendar_date && event.end_calendar_date > start
        ? ` – ${formatLongDate(event.end_calendar_date)}` : ""}</p>
      <p className="preview-time">{eventTimeLabel(event, timezone)}</p>
      {location && <p>{location}</p>}
      {event.subtitle && <p>{event.subtitle}</p>}
      <p className="event-status">{event.status.replaceAll("_", " ")}</p>
      <p className="preview-help">Open the day for all events and sources. Press Enter when the day is focused.</p>
    </div>, document.body,
  );
}
