import { useEffect, useRef, useState } from "react";
import { searchEvents } from "./data";
import {
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
import MonthFeed, { type MonthNavigation } from "./MonthFeed";
import { FIRST_MONTH, LAST_MONTH, monthAt, monthIndex, monthWindow } from "./month-feed-state";
import { useCalendarData } from "./use-calendar-data";

const EMPTY: FilterState = {
  sport: "",
  league: "",
  competition_phase: "",
  country: "",
  city: "",
  tags: [],
  motorsport_view: "race_only",
};
const KEY = "sportsbro.interests.v1";
function savedInterests(): string[] | null {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "null");
    return Array.isArray(v) && v.every((x) => typeof x === "string") ? v : null;
  } catch {
    return null;
  }
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
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog ref={ref} aria-label={title} onCancel={onClose}>
      <header>
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close">
          ×
        </button>
      </header>
      {children}
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
    <article className="agenda-event">
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
  const pendingMonth = useRef<string | null>(null);
  const [view, setView] = useState<"month" | "year">("month");
  const [day, setDay] = useState<string | null>(null);
  const [interests, setInterests] = useState<string[] | null>(savedInterests);
  const [draft, setDraft] = useState<string[]>(() => savedInterests() || []);
  const [choose, setChoose] = useState(() => savedInterests() === null);
  const [info, setInfo] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<EventCard[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [retry, setRetry] = useState(0);
  const [storageNote, setStorageNote] = useState("");
  const year = Number(month.slice(0, 4));
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const activeFilters = {
    ...filters,
    followed_leagues: interests ?? undefined,
  };
  const signature = JSON.stringify(activeFilters);
  const anchors = yearMonthAnchors(year);
  const feedAnchors = monthWindow(feedCenter);
  const requestedAnchors = [...new Set([
    ...(view === "year" ? anchors : feedAnchors),
    ...(day ? [firstOfMonth(day)] : []),
  ])].sort();
  const { months, errors, loadingYears, manifests, facets } = useCalendarData(requestedAnchors, signature, timezone, retry);
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
    let active = true;
    setResults([]);
    setSearchError("");
    if (search.trim().length < 2) {
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = setTimeout(
      () =>
        searchEvents(year, search.trim(), JSON.parse(signature), timezone)
          .then((r) => {
            if (active) {
              setResults(r.items);
              setSearchTotal(r.total);
            }
          })
          .catch((e) => {
            if (active) setSearchError(e.message);
          })
          .finally(() => {
            if (active) setSearching(false);
          }),
      150,
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [search, signature, year, timezone, retry]);
  function navigateMonth(anchor: string, focusDate?: string) {
    const bounded = monthAt(monthIndex(anchor));
    pendingMonth.current = bounded;
    if (!feedAnchors.includes(bounded)) setFeedCenter(bounded);
    setNavigation((previous) => ({ anchor: bounded, id: previous.id + 1, focusDate }));
    setMonth(bounded);
  }
  function openDay(date: string) {
    if (search.trim().length >= 2 || view === "year") navigateMonth(firstOfMonth(date));
    setDay(date);
    setView("month");
    setSearch("");
  }
  function openMonth(anchor: string, focusDate?: string) {
    navigateMonth(anchor, focusDate);
    setDay(null);
    setView("month");
  }
  function moveMonth(delta: number) {
    const from = view === "year" ? month : pendingMonth.current || month;
    const anchor = monthAt(monthIndex(from) + delta);
    if (view === "year") setMonth(anchor);
    else navigateMonth(anchor);
    setDay(null);
  }
  function jumpToday() {
    const now = todayIso();
    setToday(now);
    openMonth(firstOfMonth(now));
    setSearch("");
  }
  function save() {
    setInterests(draft);
    try {
      localStorage.setItem(KEY, JSON.stringify(draft));
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
    const target = document.getElementById(`day-${day}`);
    if (target) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "nearest", behavior: "instant" });
    } else if (day) openMonth(firstOfMonth(day), day);
  }
  const leagues = facets?.leagues || [];
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="nav-left">
          {view === "month" ? (
            <button
              className="back-button"
              onClick={() => {
                setView("year");
                setDay(null);
                setSearch("");
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
          sportsbro
        </a>
        <div className="nav-right">
          <button
            ref={interestsButton}
            onClick={() => {
              setDraft(interests || leagues.map((l) => l.value));
              setChoose(true);
            }}
          >
            Interests{interests ? ` · ${interests.length}` : ""}
          </button>
          <button
            className="icon-button"
            aria-label="About sportsbro and schedule coverage"
            onClick={() => setInfo(true)}
          >
            i
          </button>
        </div>
      </header>
      <div className="calendar-heading">
        <h1 aria-live="polite" aria-atomic="true">{view === "year" ? year : monthTitle(month)}</h1>
        <div className="heading-actions">
          <label className="search">
            <span className="sr-only">Search teams, events and places</span>
            <input
              type="search"
              value={search}
              onChange={(e) => {
                if (search.trim().length < 2 && e.target.value.trim().length >= 2) navigateMonth(month);
                setSearch(e.target.value);
              }}
              placeholder="Search events"
            />
          </label>
          <button
            className="icon-button"
            aria-label={`Previous ${view}`}
            disabled={monthIndex(month) - (view === "year" ? 12 : 1) < monthIndex(FIRST_MONTH)}
            onClick={() => moveMonth(view === "year" ? -12 : -1)}
          >
            ‹
          </button>
          <button
            className="icon-button"
            aria-label={`Next ${view}`}
            disabled={monthIndex(month) + (view === "year" ? 12 : 1) > monthIndex(LAST_MONTH)}
            onClick={() => moveMonth(view === "year" ? 12 : 1)}
          >
            ›
          </button>
        </div>
      </div>
      <main className={`calendar-body ${day ? "with-day" : ""}`}>
        <section
          className="calendar-stage"
          aria-label={view === "year" ? `${year} calendar` : monthLabel(month)}
        >
          {error && view === "year" && search.trim().length < 2 ? (
            <div className="empty-state" role="alert">
              <h2>Schedule unavailable for {year}</h2>
              <p>{error}</p>
              <button onClick={() => setRetry((x) => x + 1)}>Retry</button>
              <button onClick={jumpToday}>Current month</button>
            </div>
          ) : search.trim().length >= 2 ? (
            <section className="search-results" aria-label="Search results">
              <p role="status">
                {searching
                  ? "Searching…"
                  : searchError ||
                    `${searchTotal} matches in ${year}${searchTotal > 30 ? " · first 30 shown" : ""}`}
              </p>
              {results.map((e) => (
                <button
                  className="search-result"
                  key={e.event_id}
                  onClick={() => e.calendar_date && openDay(e.calendar_date)}
                >
                  <time>{e.calendar_date}</time>
                  <Pill event={e} />
                </button>
              ))}
            </section>
          ) : view === "year" ? (
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
                          className={`${cell.date === today ? "mini-today" : ""} ${cell.group?.event_count ? "has-events" : ""}`}
                          aria-current={
                            cell.date === today ? "date" : undefined
                          }
                        >
                          {cell.date ? Number(cell.date.slice(-2)) : ""}
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
                onNavigationEnd={() => { pendingMonth.current = null; }}
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
                    weekday: "long",
                  }).format(new Date(`${day}T12:00:00`))}
                </p>
                <h2 ref={dayHeading} tabIndex={-1}>
                  {new Intl.DateTimeFormat(undefined, {
                    month: "long",
                    day: "numeric",
                  }).format(new Date(`${day}T12:00:00`))}
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
          {timezone.replaceAll("_", " ")}
          <span className="snapshot">
            {" "}
            ·{" "}
            {manifest?.updated_at
              ? `Snapshot ${manifest.updated_at.slice(0, 10)}`
              : "Published schedules"}
          </span>
        </span>
        <a
          href="https://github.com/snowball-projects/sportsbro"
          target="_blank"
          rel="noreferrer"
        >
          Source ↗
        </a>
      </footer>
      {choose && (
        <Modal
          title="Follow your sports"
          onClose={() => {
            setChoose(false);
            interestsButton.current?.focus();
          }}
        >
          <p className="modal-intro">
            Choose leagues for your calendar. Saved only on this device.
          </p>
          {loading && !leagues.length ? (
            <p>Loading available leagues…</p>
          ) : error && !leagues.length ? (
            <p>{error}</p>
          ) : (
            <InterestGroups leagues={leagues} selected={draft} onChange={setDraft} />
          )}
          <div className="interest-actions">
            <button onClick={() => setDraft(leagues.map((l) => l.value))}>
              Select all
            </button>
            <button onClick={() => setDraft([])}>Clear</button>
          </div>
          <label className="option-row">
            Motorsport
            <select
              value={filters.motorsport_view}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  motorsport_view: e.target.value as
                    "race_only" | "full_weekend",
                }))
              }
            >
              <option value="race_only">Races only</option>
              <option value="full_weekend">Full weekend</option>
            </select>
          </label>
          <details className="advanced">
            <summary>More filters</summary>
            {(
              [
                ["sport", "Sport", "sports"],
                ["competition_phase", "Phase", "competition_phases"],
                ["country", "Country", "countries"],
                ["city", "City", "cities"],
              ] as const
            ).map(([field, label, facet]) => (
              <label className="option-row" key={field}>
                {label}
                <select
                  value={filters[field]}
                  onChange={(e) =>
                    setFilters((f) => ({ ...f, [field]: e.target.value }))
                  }
                >
                  <option value="">All</option>
                  {facets?.[facet].map((x) => (
                    <option key={x.value} value={x.value}>
                      {x.value.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <div className="tag-filters">
              {facets?.tags.map((t) => (
                <button
                  aria-pressed={filters.tags.includes(t.value)}
                  key={t.value}
                  onClick={() =>
                    setFilters((f) => ({
                      ...f,
                      tags: f.tags.includes(t.value)
                        ? f.tags.filter((v) => v !== t.value)
                        : [...f.tags, t.value],
                    }))
                  }
                >
                  {t.value}
                </button>
              ))}
            </div>
            <button onClick={() => setFilters(EMPTY)}>
              Reset extra filters
            </button>
          </details>
          <p className="fine-print">
            Only published coverage appears here. More sports will be added as
            reusable sources are verified.
          </p>
          <button className="primary-button" onClick={save}>
            Show my calendar
          </button>
        </Modal>
      )}
      {info && (
        <Modal title="About sportsbro" onClose={() => setInfo(false)}>
          <p>
            A sports calendar by{" "}
            <a href="https://snowball-projects.github.io/">snowball</a>.
          </p>
          <h3>Coverage</h3>
          <p>
            {manifest?.coverage ||
              "Selected published schedules. No live scores or guarantee of complete coverage."}
          </p>
          <p>
            <a href="https://github.com/snowball-projects/sportsbro/blob/main/docs/PUBLIC_RELEASE.md" target="_blank" rel="noreferrer">
              Coverage details and omitted events ↗
            </a>
          </p>
          <p>
            Dates and times can change. Known UTC times appear in your device’s
            timezone. Dates without a verified timezone stay on the source date;
            their time is marked TBD.
          </p>
          <p>
            Snapshot: {manifest?.updated_at || "unavailable"}. An empty day
            means no matching published records, not necessarily no sporting
            events.
          </p>
          <h3>Sources</h3>
          {manifest?.data_license_notice && <p>{manifest.data_license_notice}</p>}
          {manifest?.components?.map((component) => (
            <p key={component.path}>
              <a href={`${import.meta.env.BASE_URL}data/${component.path}`} download>
                Download {component.path.includes("wikipedia") ? "Wikipedia" : "Wikidata"} schedule data
              </a>
            </p>
          ))}
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
            No accounts, analytics or advertising. Only your league choices are
            saved in this browser. Calendar data is static; browsing does not
            contact sports providers. GitHub Pages receives normal hosting
            requests.
          </p>
          {storageNote && <p>{storageNote}</p>}
          <p>
            {manifest && <>
              <a href={`${import.meta.env.BASE_URL}data/${year}.json`} download>
                Download schedule JSON
              </a>{" · "}
            </>}
            <a href={`${import.meta.env.BASE_URL}THIRD-PARTY-NOTICES.md`}>
              Licenses
            </a>
            {" · "}
            <a href="https://snowball-projects.github.io/operations/#sportsbro">
              Operations
            </a>
          </p>
        </Modal>
      )}
    </div>
  );
}
