import { useLayoutEffect, useRef } from "react";
import { agendaDates, agendaGroups, agendaLeagues, type AgendaPeriod } from "./agenda-state";
import { firstOfMonth, formatLongDate, formatShortDate } from "./date-utils";
import { SportIcon } from "./EventIdentity";
import { leagueVisual } from "./calendar-helpers";
import { dayAfter } from "./month-feed-state";
import AgendaEvent from "./AgendaEvent";
import type { CalendarResponse } from "./types";

export default function Agenda({ today, period, onPeriod, months, errors, timezone, resetKey, onOpenDay, onRetry,
  active, upcomingEnd, onShowMore, canShowMore, moreLoading, moreErrors, noMore, expandedYears }: {
  active: boolean;
  today: string;
  period: AgendaPeriod;
  onPeriod: (period: AgendaPeriod) => void;
  months: Record<string, CalendarResponse>;
  errors: Record<number, string>;
  timezone: string;
  resetKey: string;
  onOpenDay: (date: string, eventId?: string) => void;
  onRetry: () => void;
  upcomingEnd: string;
  onShowMore: () => void;
  canShowMore: boolean;
  moreLoading: boolean;
  moreErrors: string[];
  noMore: boolean;
  expandedYears?: number[];
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const position = useRef({ top: 0, id: "", offset: 0 });
  const pendingPosition = useRef<typeof position.current | null>(null);
  const previousScope = useRef(`${period}:${today}`);
  const previousKey = useRef(resetKey);
  function measure() {
    const root = scroller.current;
    if (!root || pendingPosition.current) return;
    const row = [...root.querySelectorAll<HTMLElement>(".agenda-row")]
      .find((item) => item.getBoundingClientRect().bottom > root.getBoundingClientRect().top);
    position.current = { top: root.scrollTop, id: row?.id || "", offset: row ? row.getBoundingClientRect().top - root.getBoundingClientRect().top : 0 };
  }
  const dates = agendaDates(today, period, upcomingEnd);
  const coveredDates = period === "upcoming" && expandedYears
    ? dates.filter((date) => expandedYears.includes(Number(date.slice(0, 4)))) : dates;
  const groups = agendaGroups(months, dates);
  const messages = [...new Set([
    ...coveredDates.map((date) => errors[Number(date.slice(0, 4))]).filter(Boolean),
    ...(period === "upcoming" ? moreErrors : []),
  ])];
  const loading = coveredDates.some((date) => !months[firstOfMonth(date)] && !errors[Number(date.slice(0, 4))]);
  const hasEvents = groups.some((group) => group.items.length);
  useLayoutEffect(() => {
    const root = scroller.current!;
    const scope = `${period}:${today}`;
    if (previousScope.current !== scope) {
      previousScope.current = scope;
      pendingPosition.current = null;
      root.scrollTo({ top: 0, behavior: "instant" });
      position.current = { top: 0, id: "", offset: 0 };
    } else {
      if (previousKey.current !== resetKey) pendingPosition.current = position.current;
      const saved = pendingPosition.current;
      if (saved) {
        const row = document.getElementById(saved.id);
        const top = row ? root.scrollTop + row.getBoundingClientRect().top - root.getBoundingClientRect().top - saved.offset : saved.top;
        root.scrollTo({ top, behavior: "instant" });
        if (!loading) { pendingPosition.current = null; measure(); }
      }
    }
    previousKey.current = resetKey;
  }, [period, today, resetKey, months, loading]);

  return (
    <section className="agenda-stage" aria-label="Agenda">
      <div className="agenda-toolbar">
        <div className="segmented-control agenda-periods" role="group" aria-label="Agenda days">
          {(["yesterday", "today", "upcoming"] as const).map((value) => (
            <button key={value} aria-pressed={period === value} onClick={() => onPeriod(value)}>
              {value === "yesterday" ? "Yesterday" : value === "today" ? "Today" : "Upcoming"}
            </button>
          ))}
        </div>
        <p className="agenda-range" aria-live="polite">
          {period === "upcoming" ? `${formatShortDate(dates[0])} – ${formatShortDate(dates.at(-1)!)}${upcomingEnd === dayAfter(today, 7) ? " · Next 7 days" : ""}` : formatLongDate(dates[0])}
        </p>
      </div>
      <div className="agenda-scroll" id="agenda-scroll" ref={scroller} onScroll={measure}>
        {!!messages.length && <div className="agenda-notice" role="status">
          {messages.map((message) => <p key={message}>{message}</p>)}
          <button onClick={onRetry}>Retry</button>
        </div>}
        {loading && <p className="empty-state" role="status">Loading schedule…</p>}
        {!loading && !hasEvents && !messages.length && <p className="empty-state">
          {period === "upcoming" ? `No published events match your interests${upcomingEnd === dayAfter(today, 7) ? " in the next 7 days" : " in this range"}.`
            : `No published events match your interests ${period}.`}
        </p>}
        {groups.filter((group) => group.items.length).map((group) => (
          <section className="agenda-day" key={group.date} aria-label={formatLongDate(group.date)}>
            {period === "upcoming" && <h2>{formatLongDate(group.date)}</h2>}
            {agendaLeagues(group.items).map((league) => <section className="agenda-league" key={league.league}
              aria-label={leagueVisual(league.league, league.items[0].sport).shortLabel}>
              <h3 className="agenda-league-heading"><SportIcon league={league.league} sport={league.items[0].sport} />
                {leagueVisual(league.league, league.items[0].sport).shortLabel}</h3>
              {league.items.map((event) => <AgendaEvent key={`${group.date}:${event.event_id}:${timezone}`} event={event}
                date={group.date} today={today} timezone={timezone} active={active} upcoming={period === "upcoming"}
                onOpen={() => onOpenDay(group.date, event.event_id)} />)}
            </section>)}
          </section>
        ))}
      </div>
      {period === "upcoming" && <div className="agenda-more">
        {canShowMore && !moreErrors.length && <button onClick={onShowMore} disabled={moreLoading} aria-controls="agenda-scroll">
          {moreLoading ? "Loading…" : "Show more"}
        </button>}
        {noMore && !messages.length && <p role="status">No later published events match your interests.</p>}
      </div>}
    </section>
  );
}
