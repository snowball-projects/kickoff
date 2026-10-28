import { useEffect, useRef, useState } from "react";
import {
  browserTimezone,
  timezoneLabel,
  eventTimeLabel,
  firstOfMonth,
  monthLabel,
  monthTitle,
  monthWeeksSunStart,
  todayIso,
  WEEKDAY_LABELS,
  WEEKDAY_NARROW,
  yearMonthAnchors,
} from "./date-utils";
import type { EventCard, FilterState } from "./types";
import { leagueVisual, SOCCER_COUNTRIES } from "./calendar-helpers";
import InterestGroups from "./InterestGroups";
import { defaultPreferences, GOLF_TOURS, INTERESTS_KEY, interestLeagues, readPreferences, type InterestPreferences } from "./interest-preferences";
import MonthFeed, { type MonthNavigation } from "./MonthFeed";
import { boundMonth, dayAfter, monthAt, monthIndex, monthWindow, scheduleWindow } from "./month-feed-state";
import { useCalendarData } from "./use-calendar-data";
import Agenda from "./Agenda";
import { agendaAnchors, laterAgendaAnchors, nextAgendaEnd, readScheduleView, VIEW_KEY, type AgendaPeriod, type ScheduleView } from "./agenda-state";

type UpcomingWindow = { key: string; end: string; expanded: boolean; pending: boolean; done: boolean };

const EMPTY: FilterState = {
  sport: "",
  league: "",
  competition_phase: "",
  country: "",
  city: "",
  tags: [],
  motorsport_view: "race_only",
};
function savedPreferences() {
  try { return readPreferences(localStorage); } catch { return defaultPreferences(); }
}
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const backdropPress = useRef(false);
  function isBackdrop(event: React.PointerEvent<HTMLDialogElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    return event.target === event.currentTarget &&
      (event.clientX < box.left || event.clientX > box.right ||
       event.clientY < box.top || event.clientY > box.bottom);
  }
  useEffect(() => {
    const dialog = ref.current;
    const opener = document.activeElement;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog ref={ref} aria-label={title} onCancel={onClose}
      onPointerDown={(event) => { backdropPress.current = isBackdrop(event); }}
      onPointerUp={(event) => {
        if (backdropPress.current && isBackdrop(event)) onClose();
        backdropPress.current = false;
      }}
      onPointerCancel={() => { backdropPress.current = false; }}>
      <header>
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close">
          ×
        </button>
      </header>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
function Pill({ event }: { event: EventCard }) {
  return (
    <span
      className={`event-pill ${leagueVisual(event.league).className}`}
    >
      <b>{SOCCER_COUNTRIES[event.league] && <span aria-hidden="true">{SOCCER_COUNTRIES[event.league].flag} </span>}{leagueVisual(event.league).shortLabel}</b>
      <span>{event.tags.includes("final date only") && "Final date · "}{event.title}</span>
    </span>
  );
}
function EventRow({ event, timezone }: { event: EventCard; timezone: string }) {
  const location = [event.venue, event.city, event.country]
    .filter(Boolean)
    .join(" · ");
  return (
    <article className="agenda-event" id={`details-${event.event_id}`}>
      <div className="event-time">{eventTimeLabel(event, timezone)}</div>
      <div>
        <span
          className={`league-label ${leagueVisual(event.league).className}`}
        >
          {leagueVisual(event.league).shortLabel}
        </span>
        <h3>{event.title}</h3>
        {event.tags.includes("final date only") && <p className="date-scope">Final date only</p>}
        {event.subtitle && <p>{event.subtitle}</p>}
        {location && <p>{location}</p>}
        <p className="event-status">
          {event.status.replaceAll("_", " ")}
          {event.end_calendar_date &&
          event.end_calendar_date > (event.calendar_date || "")
            ? ` · through ${event.end_calendar_date}`
            : ""}
        </p>
        {event.source_url && (
          <a href={event.source_url} target="_blank" rel="noreferrer">
            Schedule source ↗
          </a>
        )}
      </div>
    </article>
  );
}
export default function App() {
  const [today, setToday] = useState(todayIso);
  const [month, setMonth] = useState(() => firstOfMonth(today));
  const [feedCenter, setFeedCenter] = useState(() => firstOfMonth(today));
  const [navigation, setNavigation] = useState<MonthNavigation>(() => ({ anchor: firstOfMonth(today), id: 0 }));
  const [view, setView] = useState<"month" | "year">("month");
  const [scheduleView, setScheduleView] = useState<ScheduleView>(() => {
    try { return readScheduleView(localStorage); } catch { return "calendar"; }
  });
  const [period, setPeriod] = useState<AgendaPeriod>("today");
  const [publishedYears, setPublishedYears] = useState<number[]>([]);
  const [savedUpcoming, setUpcoming] = useState<UpcomingWindow | null>(null);
  const [day, setDay] = useState<string | null>(null);
  const [detailEventId, setDetailEventId] = useState<string | undefined>();
  const dayOpener = useRef<HTMLElement | null>(null);
  const [preferences, setPreferences] = useState<InterestPreferences>(savedPreferences);
  const interests = preferences.leagues;
  const [draftPreferences, setDraftPreferences] = useState<InterestPreferences>(savedPreferences);
  const [draft, setDraft] = useState<string[]>(() => savedPreferences().leagues || []);
  const [choose, setChoose] = useState(() => savedPreferences().leagues === null);
  const [info, setInfo] = useState(false);
  const filters = EMPTY;
  const [retry, setRetry] = useState(0);
  const [storageNote, setStorageNote] = useState("");
  const year = Number((scheduleView === "agenda" ? today : month).slice(0, 4));
  const timezone = browserTimezone();
  const activeFilters = {
    ...filters,
    climbing: preferences.climbing,
    weightlifting: preferences.weightlifting,
    golf_views: preferences.golf_views,
    motorsport_view: preferences.motorsport_view,
    followed_leagues: interests ?? undefined,
  };
  const signature = JSON.stringify(activeFilters);
  const upcomingKey = `${today}:${signature}`;
  const upcoming: UpcomingWindow = savedUpcoming?.key === upcomingKey ? savedUpcoming : {
    key: upcomingKey, end: dayAfter(today, 7), expanded: false, pending: false, done: false,
  };
  const bounds = scheduleWindow(today);
  const laterAnchors = laterAgendaAnchors(today, publishedYears);
  const anchors = yearMonthAnchors(Number(month.slice(0, 4)))
    .filter((anchor) => anchor >= firstOfMonth(bounds.start) && anchor <= firstOfMonth(bounds.end));
  const feedAnchors = monthWindow(feedCenter, today);
  // Snapshots are fetched per year. Group later published months on demand to
  // find occupied dates without probing successive empty or unpublished years.
  const requestedAnchors = [...new Set([
    ...(view === "year" ? anchors : feedAnchors),
    ...(scheduleView === "agenda" ? agendaAnchors(today) : []),
    ...(scheduleView === "agenda" && upcoming.expanded ? laterAnchors : []),
    ...(day ? [firstOfMonth(day)] : []),
  ])].sort();
  const { months, errors, loadingYears, boundaryLoadingYears, manifests, facets } = useCalendarData(requestedAnchors, signature, timezone, retry);
  const laterLoading = upcoming.expanded && laterAnchors.some((anchor) => {
    const year = Number(anchor.slice(0, 4));
    return loadingYears.includes(year) || boundaryLoadingYears.includes(year) || (!months[anchor] && !errors[year]);
  });
  const laterErrors = upcoming.expanded ? [...new Set(publishedYears.map((year) => errors[year]).filter(Boolean))] : [];
  const canShowMore = !upcoming.done && interests?.length !== 0 && laterAnchors.some((anchor) =>
    `${anchor.slice(0, 4)}-12-31` > upcoming.end);
  useEffect(() => {
    const available = [...new Set([
      ...(facets?.available_seasons || []),
      ...Object.values(manifests).flatMap((item) => item.available_seasons),
    ])].sort((a, b) => a - b);
    if (available.length) setPublishedYears((previous) => previous.join() === available.join() ? previous : available);
  }, [facets, manifests]);
  function extendUpcoming() {
    const next = nextAgendaEnd(months, upcoming.end, bounds.end);
    setUpcoming({ ...upcoming, expanded: true, pending: false, end: next || upcoming.end,
      done: !next || !nextAgendaEnd(months, next, bounds.end) });
  }
  useEffect(() => {
    if (scheduleView !== "agenda" || !upcoming.pending || laterLoading) return;
    if (laterErrors.length) setUpcoming({ ...upcoming, pending: false });
    else extendUpcoming();
  }, [scheduleView, upcoming.key, upcoming.pending, laterLoading, months, errors]);
  function showMore() {
    if (!upcoming.expanded) setUpcoming({ ...upcoming, expanded: true, pending: true });
    else extendUpcoming();
  }
  const manifest = manifests[year];
  const error = errors[year] || "";
  const loading = loadingYears.includes(year);
  const selected = day ? months[firstOfMonth(day)]?.groups.find((group) => group.date === day) : undefined;
  const selectedError = day ? errors[Number(day.slice(0, 4))] : undefined;
  const dayHeading = useRef<HTMLHeadingElement>(null);
  const interestsButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const id = setInterval(() => setToday(todayIso()), 60_000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    if (day) dayHeading.current?.focus();
  }, [day]);
  useEffect(() => {
    if (day && detailEventId) document.getElementById(`details-${detailEventId}`)?.scrollIntoView({ block: "nearest" });
  }, [day, detailEventId, selected]);
  useEffect(() => {
    const bounded = boundMonth(month, today);
    if (bounded !== month) navigateMonth(bounded);
    if (day && (day < bounds.start || day > bounds.end)) setDay(null);
  }, [today]);
  function navigateMonth(anchor: string, focusDate?: string) {
    const bounded = boundMonth(anchor, today);
    if (focusDate) focusDate = focusDate < bounds.start ? bounds.start : focusDate > bounds.end ? bounds.end : focusDate;
    if (!feedAnchors.includes(bounded)) setFeedCenter(bounded);
    setNavigation((previous) => ({ anchor: bounded, id: previous.id + 1, focusDate }));
    setMonth(bounded);
  }
  function openDay(date: string, eventId?: string) {
    if (date < bounds.start || date > bounds.end) return;
    dayOpener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setDetailEventId(eventId);
    if (scheduleView === "agenda") { setDay(date); return; }
    if (view === "year") navigateMonth(firstOfMonth(date));
    setDay(date);
    setView("month");
  }
  function openMonth(anchor: string, focusDate?: string) {
    navigateMonth(anchor, focusDate);
    setDay(null);
    setView("month");
  }
  function jumpToday() {
    const now = todayIso();
    setToday(now);
    if (scheduleView === "agenda") { setPeriod("today"); setDay(null); return; }
    openMonth(firstOfMonth(now));
  }
  function changeScheduleView(next: ScheduleView) {
    setDay(null);
    setScheduleView(next);
    try { localStorage.setItem(VIEW_KEY, next); } catch { /* View stays active for this visit. */ }
  }
  function save() {
    const next = { ...draftPreferences, leagues: draft };
    setPreferences(next);
    try {
      localStorage.setItem(INTERESTS_KEY, JSON.stringify(next));
      setStorageNote("");
    } catch {
      setStorageNote(
        "Interests are active for this visit; browser storage is unavailable.",
      );
    }
    setChoose(false);
  }
  function closeDay() {
    setDay(null);
    if (scheduleView === "agenda") {
      dayOpener.current?.focus({ preventScroll: true });
      return;
    }
    const target = document.getElementById(`day-${day}`);
    if (target) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "nearest", behavior: "instant" });
    } else if (day) openMonth(firstOfMonth(day), day);
  }
  const leagues = interestLeagues(facets?.leagues || []);
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="nav-left">
          {scheduleView === "agenda" ? null : view === "month" ? (
            <button
              className="back-button"
              onClick={() => {
                setView("year");
                setDay(null);
              }}
              aria-label={`Show ${year} year calendar`}
            >
              ‹ <span>{year}</span>
            </button>
          ) : (
            <button className="back-button" onClick={() => openMonth(month)}>
              ‹ <span>Month</span>
            </button>
          )}
        </div>
        <a className="brand" href="https://snowball-projects.github.io/">
          <img
            src={`${import.meta.env.BASE_URL}icon.png`}
            width="32"
            height="32"
            alt=""
          />
          kickoff
        </a>
        <div className="nav-right">
          <button
            ref={interestsButton}
            onClick={() => {
              setDraft(interests || leagues.map((l) => l.value));
              setDraftPreferences(preferences);
              setChoose(true);
            }}
          >
            Interests{interests ? ` · ${interests.length}` : ""}
          </button>
          <button
            className="icon-button"
            aria-label="About kickoff and schedule coverage"
            onClick={() => setInfo(true)}
          >
            i
          </button>
        </div>
      </header>
      <div className="calendar-heading">
        <h1 aria-live="polite" aria-atomic="true">{scheduleView === "agenda" ? "Agenda" : view === "year" ? year : monthTitle(month)}</h1>
        <div className="segmented-control" role="group" aria-label="Schedule view">
          <button aria-pressed={scheduleView === "calendar"} onClick={() => changeScheduleView("calendar")}>Calendar</button>
          <button aria-pressed={scheduleView === "agenda"} onClick={() => changeScheduleView("agenda")}>Agenda</button>
        </div>
      </div>
      <main className={`calendar-body ${day ? "with-day" : ""}`}>
        <section
          className="calendar-stage"
          hidden={scheduleView !== "calendar"}
          aria-label={view === "year" ? `${year} calendar` : monthLabel(month)}
          tabIndex={view === "year" ? 0 : undefined}
          onKeyDown={(event) => {
            if (view !== "year" || (event.key !== "PageUp" && event.key !== "PageDown")) return;
            event.preventDefault();
            event.currentTarget.focus();
            setMonth(boundMonth(monthAt(monthIndex(month) + (event.key === "PageUp" ? -12 : 12)), today));
          }}
        >
          {error && view === "year" && (
            <div className="empty-state" role="alert">
              <h2>{error.startsWith("Some year-boundary") ? "Partial schedule" : "Schedule unavailable"} for {year}</h2>
              <p>{error}</p>
              <button onClick={() => setRetry((x) => x + 1)}>Retry</button>
              <button onClick={jumpToday}>Current month</button>
            </div>
          )}
          {view === "year" ? (
            <div className="year-grid">
              {anchors.map((anchor) => {
                const mini = monthWeeksSunStart(
                  anchor,
                  months[anchor]?.groups || [],
                  { showAdjacentDays: false },
                );
                return (
                  <button
                    className={`mini-month ${anchor === firstOfMonth(today) ? "current-month" : ""}`}
                    key={anchor}
                    onClick={() => openMonth(anchor)}
                    aria-label={`Open ${monthLabel(anchor)}`}
                  >
                    <h2>{monthTitle(anchor)}</h2>
                    <div className="mini-weekdays">
                      {WEEKDAY_NARROW.map((d, i) => (
                        <span key={i}>{d}</span>
                      ))}
                    </div>
                    <div className="mini-days">
                      {mini.flat().map((cell, i) => (
                        <span
                          key={i}
                          className={`${cell.date === today ? "mini-today" : ""} ${cell.date && cell.date >= bounds.start && cell.date <= bounds.end && cell.group?.event_count ? "has-events" : ""}`}
                          aria-current={
                            cell.date === today ? "date" : undefined
                          }
                        >
                          {cell.date && cell.date >= bounds.start && cell.date <= bounds.end ? Number(cell.date.slice(-2)) : ""}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <>
              <div className="weekday-row">
                {WEEKDAY_LABELS.map((d) => (
                  <span key={d}>{d}</span>
                ))}
              </div>
              <MonthFeed
                active={scheduleView === "calendar"}
                anchors={feedAnchors}
                months={months}
                errors={errors}
                today={today}
                day={day}
                timezone={timezone}
                navigation={navigation}
                onVisibleMonth={setMonth}
                onRecenter={setFeedCenter}
                onNavigate={openMonth}
                onNavigationEnd={() => {}}
                onOpenDay={openDay}
                onRetry={() => setRetry((value) => value + 1)}
                renderEvent={(event) => <Pill key={event.event_id} event={event} />}
              />
            </>
          )}
          {loading && !error && view === "year" && (
            <div className="loading-note" role="status">Loading schedule…</div>
          )}
        </section>
        {scheduleView === "agenda" && <Agenda today={today} period={period} onPeriod={(value) => { setPeriod(value); setDay(null); }}
          upcomingEnd={upcoming.end} onShowMore={showMore} canShowMore={canShowMore}
          expandedYears={upcoming.expanded ? publishedYears : undefined}
          moreLoading={upcoming.pending || laterLoading} moreErrors={laterErrors} noMore={upcoming.done}
          months={months} errors={errors} timezone={timezone} resetKey={signature} onOpenDay={openDay} onRetry={() => setRetry((value) => value + 1)} />}
        {day && (
          <aside
            className="day-inspector"
            aria-label="Day events"
            onKeyDown={(e) => {
              if (e.key === "Escape") closeDay();
            }}
          >
            <header>
              <div>
                <p>
                  {new Intl.DateTimeFormat(undefined, {
                    weekday: "long", timeZone: "UTC",
                  }).format(new Date(`${day}T12:00:00Z`))}
                </p>
                <h2 ref={dayHeading} tabIndex={-1}>
                  {new Intl.DateTimeFormat(undefined, {
                    month: "long",
                    day: "numeric", timeZone: "UTC",
                  }).format(new Date(`${day}T12:00:00Z`))}
                </h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close day"
                onClick={closeDay}
              >
                ×
              </button>
            </header>
            <div className="day-scroll">
              {selectedError && !!selected?.items.length && <p role="status">{selectedError}</p>}
              {selected?.items.length ? (
                selected.items.map((e) => (
                  <EventRow key={e.event_id} event={e} timezone={timezone} />
                ))
              ) : (
                <p className="empty-state">
                  {selectedError || (!day || !months[firstOfMonth(day)] ? "Loading…" : "No published events match this day.")}
                </p>
              )}
            </div>
          </aside>
        )}
      </main>
      <footer className="bottom-bar">
        <button className="today-button" onClick={jumpToday}>
          Today
        </button>
        <span className="footer-meta">
          <span title={`Browser timezone: ${timezone}`}>{timezoneLabel(timezone)}</span>
          <span className="snapshot">
            {" "}
            ·{" "}
            {manifest?.updated_at
              ? `Updated ${manifest.updated_at.slice(0, 10)}`
              : "Published schedules"}
          </span>
        </span>
        <a
          href="https://github.com/snowball-projects/kickoff"
          target="_blank"
          rel="noreferrer"
        >
          Source ↗
        </a>
      </footer>
      {choose && (
        <Modal
          title="Interests"
          onClose={() => {
            setChoose(false);
            interestsButton.current?.focus();
          }}
        >
          {loading && !leagues.length ? (
            <p>Loading available leagues…</p>
          ) : error && !leagues.length ? (
            <p>{error}</p>
          ) : (
            <InterestGroups leagues={leagues} selected={draft} onChange={setDraft}
              sessionInterests={draftPreferences} onSessionChange={(options) =>
                setDraftPreferences((previous) => ({ ...previous, ...options }))} />
          )}
          <div className="interest-actions">
            <button onClick={() => {
              setDraft(leagues.map((l) => l.value));
              const { climbing, weightlifting } = defaultPreferences();
              setDraftPreferences((previous) => ({ ...previous, climbing, weightlifting }));
            }}>
              Select all
            </button>
            <button onClick={() => setDraft([])}>Clear</button>
          </div>
          <details className="advanced">
            <summary>Advanced options</summary>
            <label className="option-row">
              Motorsport
              <select aria-label="Motorsport" value={draftPreferences.motorsport_view} onChange={(e) =>
                setDraftPreferences((p) => ({ ...p, motorsport_view: e.target.value as "race_only" | "full_weekend" }))}>
                <option value="race_only">Races only</option>
                <option value="full_weekend">Full weekend</option>
              </select>
            </label>
            {GOLF_TOURS.map((tour) => (
              <label className="option-row" key={tour}>
                {leagueVisual(tour).shortLabel}
                <select aria-label={leagueVisual(tour).shortLabel} value={draftPreferences.golf_views[tour]} onChange={(e) =>
                  setDraftPreferences((p) => ({ ...p, golf_views: { ...p.golf_views,
                    [tour]: e.target.value as "majors_only" | "full_tour" } }))}>
                  <option value="majors_only">Majors only</option>
                  <option value="full_tour">Full tour</option>
                </select>
              </label>
            ))}
          </details>
          <button className="primary-button" onClick={save}>
            Show my calendar
          </button>
        </Modal>
      )}
      {info && (
        <Modal title="About kickoff" onClose={() => setInfo(false)}>
          <p>
            A sports calendar by{" "}
            <a href="https://snowball-projects.github.io/">snowball</a>.
          </p>
          <h3>Coverage</h3>
          <p>
            Published schedules, not live scores. Coverage is incomplete; an empty
            day means no matching published events. Dates and times can change.
          </p>
          <p>
            Golf: Full tour includes all published tournaments and majors.
            LPGA coverage is selected dates, mostly final dates outside the majors.
          </p>
          <p>
            Boxing: selected reviewed four-belt undisputed bouts and unifications
            of at least three full WBA, WBC, IBF or WBO titles in one division.
            No interim or secondary titles, exhibitions or influencer cards.
          </p>
          <p>
            <a href="https://github.com/snowball-projects/kickoff/tree/main/data/reviewed" target="_blank" rel="noreferrer">
              Coverage details and omitted events ↗
            </a>
          </p>
          <p>
            Verified times use your browser’s timezone automatically. Date-only
            events stay on their source dates with Time TBD.
          </p>
          <p>
            Schedule snapshot updated: {manifest?.updated_at || "unavailable"}.
          </p>
          <h3>Sources</h3>
          {manifest?.data_license_notice && <p>{manifest.data_license_notice}</p>}
          {manifest?.sources?.map((s) => (
            <p key={s.name}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.name}
              </a>{" "}
              ·{" "}
              <a href={s.license_url} target="_blank" rel="noreferrer">
                {s.license}
              </a>
            </p>
          ))}
          <h3>Privacy</h3>
          <p>
            Interests and options stay in this browser. No accounts, analytics,
            advertising or location access. Timezone comes from your browser;
            no lookup is sent. Static calendar browsing contacts no sports
            providers. GitHub Pages receives normal hosting requests.
          </p>
          {storageNote && <p>{storageNote}</p>}
          <p>
            <a href={`${import.meta.env.BASE_URL}THIRD-PARTY-NOTICES.md`}>
              Licenses
            </a>
            {" · "}
            <a href="https://snowball-projects.github.io/operations/#kickoff">
              Operations
            </a>
          </p>
        </Modal>
      )}
    </div>
  );
}

