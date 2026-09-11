import { useLayoutEffect, useRef } from "react";
import { firstOfMonth, formatLongDate, monthLabel, monthWeeksSunStart } from "./date-utils";
import { dayAfter, dayInMonth, FIRST_MONTH, LAST_MONTH, monthWindow, scrollBehavior, shouldRecenter, visibleMonthAt } from "./month-feed-state";
import type { CalendarResponse, EventCard } from "./types";
import EventPreview, { useEventPreview } from "./EventPreview";

export type MonthNavigation = { anchor: string; id: number; focusDate?: string };
type Props = {
  anchors: string[];
  months: Record<string, CalendarResponse>;
  errors: Record<number, string>;
  today: string;
  day: string | null;
  timezone: string;
  navigation: MonthNavigation;
  onVisibleMonth: (anchor: string) => void;
  onRecenter: (anchor: string) => void;
  onNavigate: (anchor: string, focusDate?: string) => void;
  onNavigationEnd: () => void;
  onOpenDay: (date: string) => void;
  onRetry: () => void;
  renderEvent: (event: EventCard) => React.ReactNode;
};

export default function MonthFeed(props: Props) {
  const preview = useEventPreview();
  const focusPreviewAllowed = useRef(false);
  const scroller = useRef<HTMLDivElement>(null);
  const latest = useRef(props);
  latest.current = props;
  const lastNavigation = useRef(-1);
  const previousAnchors = useRef<string[]>([]);
  const position = useRef<{ anchor: string; offset: number } | null>(null);
  const moving = useRef(false);
  const navigationDeadline = useRef(0);
  const frame = useRef(0);
  const idle = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const jumpFrame = useRef(0);

  function sections() {
    return [...scroller.current!.querySelectorAll<HTMLElement>("[data-month]")];
  }
  function destination(root: HTMLDivElement, navigation: MonthNavigation) {
    const target = sections().find((element) => element.dataset.month === navigation.anchor);
    if (!target) return null;
    const focusedDay = navigation.focusDate ? root.querySelector<HTMLElement>(`#day-${navigation.focusDate}`) : null;
    const top = focusedDay
      ? Math.max(target.offsetTop, focusedDay.offsetTop + focusedDay.offsetHeight - root.clientHeight + 4)
      : target.offsetTop;
    return { focusedDay, top: Math.max(0, Math.min(top, root.scrollHeight - root.clientHeight)) };
  }
  function measure() {
    const root = scroller.current;
    if (!root || !root.clientHeight) return;
    const items = sections();
    const anchor = visibleMonthAt(items.map((el) => ({ anchor: el.dataset.month!, top: el.offsetTop })), root.scrollTop, root.clientHeight);
    if (!anchor) return;
    const element = items.find((el) => el.dataset.month === anchor)!;
    position.current = { anchor, offset: element.offsetTop - root.scrollTop };
    latest.current.onVisibleMonth(anchor);
  }
  function settle() {
    clearTimeout(idle.current);
    if (moving.current && scroller.current) {
      cancelAnimationFrame(jumpFrame.current);
      const target = destination(scroller.current, latest.current.navigation);
      // Timer silence is not arrival: compositor scroll delivery can be sparse.
      // Keep resize tied to the destination while a native jump is in flight.
      if (target && Math.abs(scroller.current.scrollTop - target.top) > 2 && performance.now() < navigationDeadline.current) {
        measure();
        idle.current = setTimeout(settle, 160);
        return;
      }
      // Bound stalled/canceled browser motion without an indefinitely live timer.
      if (target) {
        scroller.current.scrollTo({ top: target.top, behavior: "instant" });
      }
    }
    moving.current = false;
    measure();
    latest.current.onNavigationEnd();
    if (focusPreviewAllowed.current) {
      const target = document.activeElement as HTMLElement | null;
      const date = target?.id?.replace(/^day-/, "");
      const event = date && latest.current.months[firstOfMonth(date)]?.groups.find((group) => group.date === date)?.items[0];
      if (target && scroller.current?.contains(target) && event)
        preview.show({ event, date: date!, target: target.querySelector<HTMLElement>(".event-pill") || target });
    }
    const anchor = position.current?.anchor;
    if (!anchor || !shouldRecenter(latest.current.anchors, anchor)) return;
    // Keep focused days that overlap the new window. If native scrolling has
    // left focus far behind, return it to the scroller before recycling that day.
    const focusedMonth = document.activeElement?.closest<HTMLElement>("[data-month]")?.dataset.month;
    if (focusedMonth && !monthWindow(anchor).includes(focusedMonth)) scroller.current?.focus({ preventScroll: true });
    latest.current.onRecenter(anchor);
  }
  function onScroll() {
    preview.close();
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(measure);
    clearTimeout(idle.current);
    idle.current = setTimeout(settle, 160);
  }
  function interruptNavigation() {
    cancelAnimationFrame(jumpFrame.current);
    moving.current = false;
    latest.current.onNavigationEnd();
  }

  useLayoutEffect(() => {
    const root = scroller.current!;
    const navigation = props.navigation;
    if (lastNavigation.current !== navigation.id) {
      const target = destination(root, navigation);
      if (!target) return;
      cancelAnimationFrame(jumpFrame.current);
      clearTimeout(idle.current);
      const initial = lastNavigation.current === -1;
      const wasPresent = previousAnchors.current.includes(navigation.anchor);
      lastNavigation.current = navigation.id;
      moving.current = true;
      navigationDeadline.current = performance.now() + 2000;
      const { focusedDay, top } = target;
      // Focus belongs to the requested keyboard navigation even if its queued
      // visual jump is canceled by resize or an idle-completion callback.
      focusedDay?.focus({ preventScroll: true });
      const behavior = initial ? "auto" : scrollBehavior(matchMedia("(prefers-reduced-motion: reduce)").matches);
      // A distant jump replaces the bounded window, then glides into the target.
      // Nearby navigation traverses the existing months with native scrolling.
      if (!wasPresent && behavior === "smooth") {
        const direction = position.current && position.current.anchor > navigation.anchor ? 1 : -1;
        root.scrollTo({ top: top + direction * root.clientHeight * 0.7, behavior: "instant" });
      }
      const jump = () => {
        root.scrollTo({ top, behavior });
        measure();
        // A staging scroll may already have scheduled an idle callback. Keep
        // only one, so an orphan cannot finish navigation during the animation.
        clearTimeout(idle.current);
        idle.current = setTimeout(settle, 180);
      };
      if (behavior === "auto") jump();
      else jumpFrame.current = requestAnimationFrame(jump);
    } else if (position.current && previousAnchors.current.join() !== props.anchors.join()) {
      const target = sections().find((el) => el.dataset.month === position.current!.anchor);
      if (target) root.scrollTo({ top: target.offsetTop - position.current.offset, behavior: "instant" });
    }
    previousAnchors.current = props.anchors;
  }, [props.anchors.join(), props.navigation.id]);

  useLayoutEffect(() => {
    const root = scroller.current!;
    let size = { width: root.clientWidth, height: root.clientHeight };
    const resize = new ResizeObserver(() => {
      if (root.clientWidth === size.width && root.clientHeight === size.height) return;
      size = { width: root.clientWidth, height: root.clientHeight };
      if (moving.current) {
        // Rotation or resizing changes month heights during a smooth jump.
        // Cancel its old pixel destination and land on the requested date.
        cancelAnimationFrame(jumpFrame.current);
        const target = destination(root, latest.current.navigation);
        if (target) root.scrollTo({ top: target.top, behavior: "instant" });
        clearTimeout(idle.current);
        // Let a queued compositor update arrive before confirming completion.
        idle.current = setTimeout(settle, 160);
      } else if (position.current) {
        const target = sections().find((el) => el.dataset.month === position.current!.anchor);
        if (target) root.scrollTo({ top: target.offsetTop - position.current.offset, behavior: "instant" });
      }
    });
    resize.observe(root);
    return () => {
      resize.disconnect();
      cancelAnimationFrame(frame.current);
      cancelAnimationFrame(jumpFrame.current);
      clearTimeout(idle.current);
      lastNavigation.current = -1;
      previousAnchors.current = [];
    };
  }, []);

  function navigateDay(event: React.KeyboardEvent<HTMLButtonElement>, date: string) {
    let next: string | undefined;
    if (event.key === "ArrowLeft") next = dayAfter(date, -1);
    if (event.key === "ArrowRight") next = dayAfter(date, 1);
    if (event.key === "ArrowUp") next = dayAfter(date, -7);
    if (event.key === "ArrowDown") next = dayAfter(date, 7);
    if (event.key === "PageUp") next = dayInMonth(date, event.shiftKey ? -12 : -1);
    if (event.key === "PageDown") next = dayInMonth(date, event.shiftKey ? 12 : 1);
    if (!next || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    const anchor = firstOfMonth(next);
    if (anchor < FIRST_MONTH || anchor > LAST_MONTH) return;
    const target = scroller.current?.querySelector<HTMLElement>(`#day-${next}`);
    if (target) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "nearest", behavior: "instant" });
    } else props.onNavigate(anchor, next);
  }

  return (
    <div ref={scroller} className="month-feed" role="region" aria-label="Scrollable calendar" aria-describedby="scroll-help" tabIndex={0} onScroll={onScroll}
      onWheel={() => { focusPreviewAllowed.current = false; interruptNavigation(); }}
      onTouchStart={() => { focusPreviewAllowed.current = false; interruptNavigation(); }}
      onPointerDown={() => { focusPreviewAllowed.current = false; preview.close(); interruptNavigation(); }}
      onKeyDownCapture={(event) => { if (event.key === "Escape") focusPreviewAllowed.current = false; interruptNavigation(); }}>
      <p id="scroll-help" className="sr-only">Scroll up or down for other months. Use arrow keys between days, Page Up or Page Down for months, or Shift with Page Up or Page Down for years. Hover an event for a preview. Focus a day to preview its first event; press Enter or tap the day for all events and sources. Escape dismisses a preview.</p>
      {props.anchors.map((anchor) => {
        const data = props.months[anchor];
        const error = props.errors[Number(anchor.slice(0, 4))];
        const weeks = monthWeeksSunStart(anchor, data?.groups || [], { showAdjacentDays: false });
        const status = error || (!data ? "Loading schedule…" : data.total_events === 0 ? "No published events match this month and your interests." : "");
        return (
          <section className="feed-month" data-month={anchor} key={anchor} aria-label={monthLabel(anchor)}>
            <h2>{monthLabel(anchor)}</h2>
            <div className="month-status">
              <span>{status}</span>
              {error && <button onClick={props.onRetry} aria-label={`Retry schedule for ${monthLabel(anchor)}`}>Retry</button>}
            </div>
            <div className="month-grid" style={{ gridTemplateRows: `repeat(${weeks.length}, var(--week-height))` }}>
              {weeks.flat().map((cell, i) => cell.date ? (
                <button id={`day-${cell.date}`} key={cell.date}
                  className={`day-cell ${cell.date === props.today ? "is-today" : ""} ${cell.date === props.day ? "selected" : ""}`}
                  onClick={() => { preview.close(); props.onOpenDay(cell.date!); }} onKeyDown={(event) => navigateDay(event, cell.date!)}
                  onFocus={(event) => {
                    const first = cell.group?.items[0];
                    if (first && event.currentTarget.matches(":focus-visible")) {
                      focusPreviewAllowed.current = true;
                      preview.show({ event: first, date: cell.date!, target: event.currentTarget.querySelector<HTMLElement>(".event-pill") || event.currentTarget });
                    }
                  }}
                  onBlur={() => { focusPreviewAllowed.current = false; preview.close(); }}
                  aria-describedby={preview.preview?.date === cell.date ? "event-preview" : undefined}
                  aria-label={`${formatLongDate(cell.date)}, ${error ? "schedule unavailable" : !data ? "schedule loading" : `${cell.group?.event_count || 0} published events`}`}
                  aria-current={cell.date === props.today ? "date" : undefined}>
                  <span className="day-number">{Number(cell.date.slice(-2))}</span>
                  <span className="day-events">
                    {(cell.group?.items || []).slice(0, 3).map((event) => (
                      <span className="event-preview-trigger" key={event.event_id}
                        onPointerEnter={(pointer) => {
                          if (pointer.pointerType !== "touch") preview.show({ event, date: cell.date!, target: pointer.currentTarget });
                        }} onPointerLeave={preview.leave}>
                        {props.renderEvent(event)}
                      </span>
                    ))}
                    {(cell.group?.event_count || 0) > 3 && <span className="more-events">+{cell.group!.event_count - 3} more</span>}
                  </span>
                </button>
              ) : <div key={`blank-${i}`} className="day-cell blank" />)}
            </div>
          </section>
        );
      })}
      {preview.preview && <EventPreview preview={preview.preview} timezone={props.timezone}
        onEnter={preview.keep} onLeave={preview.leave} />}
    </div>
  );
}
