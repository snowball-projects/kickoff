import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { firstOfMonth, formatLongDate, monthTitle } from "./date-utils";
import { dayAfter, monthRows } from "./month-feed-state";
import { pillGroups, leagueVisual } from "./calendar-helpers";
import { isGolf } from "./golf";
import EventPill from "./EventPill";
import type { CalendarResponse, EventCard } from "./types";

export type MonthNavigation = { date: string; id: number; focus?: boolean; returnFromDay?: boolean };
export default function MonthFeed({ start, end, today, months, navigation, active, splitDate, onVisibleMonth, onOpenDay, onEvents }: {
  start: string; end: string; today: string; months: Record<string, CalendarResponse>;
  navigation: MonthNavigation; active: boolean; splitDate: string | null;
  onVisibleMonth: (month: string) => void; onOpenDay: (date: string) => void;
  onEvents: (items: EventCard[], date: string) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const lastNavigation = useRef(-1);
  const [limit, setLimit] = useState(2);
  const weeks = useMemo(() => monthRows(start, end), [start, end]);
  const split = splitDate ? weeks.findIndex((dates) => dates.includes(splitDate)) : -1;
  function measure() {
    const element = root.current;
    if (!element || !active) return;
    const box = element.getBoundingClientRect();
    const area = new Map<string, number>();
    for (const row of element.querySelectorAll<HTMLElement>(".calendar-week")) {
      const rect = row.getBoundingClientRect();
      const height = Math.max(0, Math.min(box.bottom, rect.bottom) - Math.max(box.top, rect.top));
      if (!height) continue;
      for (const date of row.dataset.dates!.split(",")) {
        if (date < start || date > end) continue;
        const month = firstOfMonth(date);
        area.set(month, (area.get(month) || 0) + height);
      }
    }
    const visible = [...area].sort((a, b) => b[1] - a[1])[0]?.[0];
    if (visible) onVisibleMonth(visible);
    const cell = element.querySelector<HTMLElement>(".day-cell");
    const pills = cell?.querySelector<HTMLElement>(".cell-pills");
    if (cell && pills) {
      const chrome = pills.getBoundingClientRect().top - cell.getBoundingClientRect().top
        + 21 + parseFloat(getComputedStyle(cell).paddingBottom);
      // 22px pills, 2px gaps, and a reserved 21px overflow control.
      setLimit(element.clientWidth < 700 ? 2 : Math.max(2, Math.floor((cell.getBoundingClientRect().height - chrome + 2) / 24)));
    }
  }
  useLayoutEffect(() => {
    if (!active) return;
    const observer = new ResizeObserver(measure);
    observer.observe(root.current!);
    measure();
    return () => observer.disconnect();
  }, [active, weeks]);
  useLayoutEffect(() => {
    if (!active) return;
    if (lastNavigation.current === navigation.id) { measure(); return; }
    lastNavigation.current = navigation.id;
    const cell = document.getElementById(`day-${navigation.date}`);
    if (!cell) return;
    if (navigation.returnFromDay) {
      const button = cell.querySelector<HTMLButtonElement>(".day-number");
      button?.focus({ preventScroll: true }); button?.scrollIntoView({ block: "nearest" });
      measure(); return;
    }
    const scroller = root.current!;
    const first = document.getElementById(`day-${firstOfMonth(navigation.date)}`) || cell;
    scroller.scrollTop += first.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
    const bottom = cell.getBoundingClientRect().bottom - scroller.getBoundingClientRect().bottom;
    if (bottom > 0) scroller.scrollTop += bottom;
    if (navigation.focus) cell.querySelector<HTMLButtonElement>(".day-number")?.focus({ preventScroll: true });
    measure();
  }, [active, navigation.id, weeks]);
  function move(date: string, key: string) {
    const delta = ({ ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 } as Record<string, number>)[key];
    if (!delta) return false;
    const next = dayAfter(date, delta);
    if (next >= start && next <= end) {
      const button = document.querySelector<HTMLButtonElement>(`#day-${next} .day-number`);
      button?.focus({ preventScroll: true });
      button?.scrollIntoView({ block: "nearest" });
    }
    return true;
  }
  function row(dates: (string | null)[], index: number) {
    return <div className="calendar-week" role="row" key={dates.find(Boolean)!} data-dates={dates.filter(Boolean).join(",")}
      style={index === split ? { viewTransitionName: "selected-week" } : undefined}>
      {dates.map((date, column) => {
        if (!date) return <div role="gridcell" className="empty-day" key={column} />;
        const items = months[firstOfMonth(date)]?.groups.find((group) => group.date === date)?.items || [];
        const groups = pillGroups(items);
        return <div className="day-cell" role="gridcell" id={`day-${date}`} key={date}
          onClick={(event) => { if (!(event.target as HTMLElement).closest("button")) onOpenDay(date); }}>
          <span className="month-abbreviation">{date.endsWith("-01") ? monthTitle(date).slice(0, 3) : ""}</span>
          <button className={`day-number ${date === today ? "today" : ""}`} aria-label={formatLongDate(date)}
            aria-current={date === today ? "date" : undefined} onClick={() => onOpenDay(date)}
            onKeyDown={(event) => { if (move(date, event.key)) event.preventDefault(); }}>{Number(date.slice(-2))}</button>
          <div className="cell-pills">
            {groups.slice(0, limit).map((group) => <EventPill key={group.items[0].event_id} items={group.items} calendarView="month"
              aria-label={`${isGolf(group.items[0]) ? group.items[0].title : `${leagueVisual(group.league).shortLabel}, ${group.items.length} events`}, ${formatLongDate(date)}`}
              onClick={() => onEvents(group.items, date)} />)}
          </div>
          {groups.length > limit && <button className="more-events" aria-label={`${groups.length - limit} more event groups, ${formatLongDate(date)}`}
            onClick={() => onOpenDay(date)}>+{groups.length - limit}</button>}
        </div>;
      })}
    </div>;
  }
  return <div className="month-scroll" ref={root} role="region" aria-label="Scrollable calendar" onScroll={measure}>
    <div role="grid" aria-label="Calendar" className="month-grid">
      {split < 0 ? weeks.map(row) : <>
        <div className="month-before">{weeks.slice(0, split).map((dates, index) => row(dates, index))}</div>
        {row(weeks[split], split)}
        <div className="month-after">{weeks.slice(split + 1).map((dates, index) => row(dates, split + 1 + index))}</div>
      </>}
    </div>
  </div>;
}
