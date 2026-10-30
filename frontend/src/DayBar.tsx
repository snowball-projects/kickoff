import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { formatLongDate, WEEKDAY_NARROW } from "./date-utils";
import { dayAfter } from "./month-feed-state";

export default function DayBar({ date, today, start, end, onSelect }: {
  date: string; today: string; start: string; end: string; onSelect: (date: string) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: number; x: number; left: number } | null>(null);
  const dragged = useRef(false);
  const days = useMemo(() => {
    const result = [];
    for (let day = start; day <= end; day = dayAfter(day, 1)) result.push({
      date: day, label: formatLongDate(day), weekday: WEEKDAY_NARROW[new Date(`${day}T12:00:00Z`).getUTCDay()], number: Number(day.slice(-2)),
    });
    return result;
  }, [start, end]);
  useLayoutEffect(() => {
    const element = root.current!;
    const reveal = () => element.querySelector<HTMLElement>(`[data-date="${date}"]`)
      ?.scrollIntoView({ block: "nearest", inline: "center", behavior: "instant" });
    reveal();
    const observer = new ResizeObserver(reveal);
    observer.observe(element);
    return () => observer.disconnect();
  }, [date, start, end]);
  useEffect(() => {
    const element = root.current!;
    function wheel(event: WheelEvent) {
      // Horizontal trackpad gestures stay native; a mouse wheel moves days too.
      if (event.ctrlKey || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
      event.preventDefault();
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientWidth : 1;
      element.scrollLeft += event.deltaY * unit;
    }
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, []);
  return <div ref={root} className="week-strip" role="group" aria-label="Days" style={{ viewTransitionName: "selected-week" }}
    onPointerDown={(event) => {
      dragged.current = false;
      if (event.pointerType !== "mouse" || event.button !== 0) return;
      drag.current = { id: event.pointerId, x: event.clientX, left: event.currentTarget.scrollLeft };
      // Capture on the original button so an ordinary click still reaches it.
      ((event.target as Element).closest("button") || event.currentTarget).setPointerCapture(event.pointerId);
    }}
    onPointerMove={(event) => {
      const origin = drag.current;
      if (!origin || origin.id !== event.pointerId) return;
      const delta = event.clientX - origin.x;
      if (Math.abs(delta) > 4) dragged.current = true;
      if (dragged.current) { event.preventDefault(); event.currentTarget.scrollLeft = origin.left - delta; }
    }}
    onPointerUp={() => { drag.current = null; }}
    onPointerCancel={() => { drag.current = null; }}
    onLostPointerCapture={() => { drag.current = null; }}
    onClickCapture={(event) => {
      if (dragged.current && event.detail > 0) { event.preventDefault(); event.stopPropagation(); dragged.current = false; }
    }}
    onKeyDown={(event) => {
      const delta = ({ ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 } as Record<string, number>)[event.key];
      if (delta) { event.preventDefault(); onSelect(dayAfter(date, delta)); }
    }}>
    {days.map((day) => <button key={day.date} data-date={day.date} tabIndex={day.date === date ? 0 : -1}
      aria-label={day.label} aria-pressed={day.date === date} aria-current={day.date === today ? "date" : undefined} onClick={() => onSelect(day.date)}>
      <span>{day.weekday}</span>
      <b className={`${day.date === date ? "selected" : ""} ${day.date === today ? "today" : ""}`}>{day.number}</b>
    </button>)}
  </div>;
}
