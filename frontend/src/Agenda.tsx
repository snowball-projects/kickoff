import { countryIdentity } from "./countries";
import { useEffect, useRef } from "react";
import { agendaDates, agendaGroups, agendaScopeLabel, type AgendaPeriod } from "./agenda-state";
import { firstOfMonth, eventTimeLabel, formatLongDate, formatShortDate } from "./date-utils";
import { EventFlags, SportIcon } from "./EventIdentity";
import { leagueVisual } from "./calendar-helpers";
import { dayAfter } from "./month-feed-state";
import EventPreview, { useEventPreview } from "./EventPreview";
import type { CalendarResponse } from "./types";

export default function Agenda({ today, period, onPeriod, months, errors, timezone, resetKey, onOpenDay, onRetry,
  upcomingEnd, onShowMore, canShowMore, moreLoading, moreErrors, noMore, expandedYears }: {
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
  const preview = useEventPreview();
  const scroller = useRef<HTMLDivElement>(null);
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
  useEffect(() => {
    preview.close();
    scroller.current?.scrollTo({ top: 0, behavior: "instant" });
  }, [period, today, resetKey]);

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
      <div className="agenda-scroll" id="agenda-scroll" ref={scroller} onScroll={preview.close}>
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
            {group.items.map((event) => {
              const scope = agendaScopeLabel(event, group.date);
              const status = event.status === "scheduled" ? "" : event.status.replaceAll("_", " ");
              const location = event.venue || [event.city, countryIdentity(event.country)?.name || event.country].filter(Boolean).join(" · ");
              return (
                <button className="agenda-row" key={event.event_id} id={`agenda-${group.date}-${event.event_id}`}
                  onClick={() => { preview.close(); onOpenDay(group.date, event.event_id); }}
                  onPointerEnter={(pointer) => {
                    if (pointer.pointerType !== "touch") preview.show({ event, date: group.date, target: pointer.currentTarget });
                  }} onPointerLeave={preview.leave}
                  onFocus={(focus) => {
                    if (focus.currentTarget.matches(":focus-visible")) preview.show({ event, date: group.date, target: focus.currentTarget });
                  }} onBlur={preview.close}
                  aria-describedby={preview.preview?.event.event_id === event.event_id && preview.preview.date === group.date ? "event-preview" : undefined}>
                  <span className="agenda-clock">{eventTimeLabel(event, timezone)}</span>
                  <span className="agenda-summary">
                    <span className={`league-label ${leagueVisual(event.league).className}`}><SportIcon sport={event.sport} />{leagueVisual(event.league).shortLabel}</span>
                    <span className="agenda-title"><EventFlags event={event} />{event.title}</span>
                    {location && <span className="agenda-location">{location}</span>}
                    {(scope || status) && <span className="agenda-status">{[scope, status].filter(Boolean).join(" · ")}</span>}
                  </span>
                  <span className="agenda-chevron" aria-hidden="true">›</span>
                </button>
              );
            })}
          </section>
        ))}
      </div>
      {period === "upcoming" && <div className="agenda-more">
        {canShowMore && !moreErrors.length && <button onClick={onShowMore} disabled={moreLoading} aria-controls="agenda-scroll">
          {moreLoading ? "Loading…" : "Show more"}
        </button>}
        {noMore && !messages.length && <p role="status">No later published events match your interests.</p>}
      </div>}
      {preview.preview && <EventPreview preview={preview.preview} timezone={timezone} onEnter={preview.keep} onLeave={preview.leave} />}
    </section>
  );
}
