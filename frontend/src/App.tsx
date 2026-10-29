import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { browserTimezone, firstOfMonth, formatLongDate, monthAnchorsInRange, monthLabel, monthTitle, monthWeeksSunStart,
  timezoneLabel, todayIso, WEEKDAY_NARROW, yearMonthAnchors } from "./date-utils";
import type { EventCard, FilterState } from "./types";
import InterestGroups from "./InterestGroups";
import { defaultPreferences, INTERESTS_KEY, interestLeagues, readPreferences, type InterestPreferences } from "./interest-preferences";
import MonthFeed, { weekStart, type MonthNavigation } from "./MonthFeed";
import { boundMonth, dayAfter, monthAt, monthIndex, scheduleWindow } from "./month-feed-state";
import { useCalendarData } from "./use-calendar-data";
import Agenda from "./Agenda";
import DayTimeline from "./DayTimeline";
import Sheet, { EventSheet } from "./Sheet";
import { agendaAnchors, laterAgendaAnchors, nextAgendaEnd, readScheduleView, VIEW_KEY, type AgendaPeriod, type ScheduleView } from "./agenda-state";

type OpenSheet = { kind: "interests" | "info" } | { kind: "events"; items: EventCard[]; date: string } | null;
type UpcomingWindow = { key: string; end: string; expanded: boolean; pending: boolean; done: boolean };
const EMPTY: FilterState = { sport: "", league: "", competition_phase: "", country: "", city: "", tags: [] };
function savedPreferences() {
  try { return readPreferences(localStorage); } catch { return defaultPreferences(); }
}
export default function App() {
  const timezone = browserTimezone();
  const [today, setToday] = useState(todayIso);
  const [month, setMonth] = useState(() => firstOfMonth(today));
  const [view, setView] = useState<"month" | "year" | "day">("month");
  const [navigation, setNavigation] = useState<MonthNavigation>({ date: today, id: 0 });
  const [scheduleView, setScheduleView] = useState<ScheduleView>(() => {
    try { return readScheduleView(localStorage); } catch { return "calendar"; }
  });
  const [period, setPeriod] = useState<AgendaPeriod>("today");
  const [day, setDay] = useState(today);
  const [splitDate, setSplitDate] = useState<string | null>(null);
  const [sheet, setSheet] = useState<OpenSheet>(null);
  const [preferences, setPreferences] = useState(savedPreferences);
  const [draft, setDraft] = useState<string[] | null>(null);
  const [draftPreferences, setDraftPreferences] = useState<InterestPreferences>(savedPreferences);
  const [storageNote, setStorageNote] = useState("");
  const [retry, setRetry] = useState(0);
  const [publishedYears, setPublishedYears] = useState<number[]>([]);
  const [savedUpcoming, setUpcoming] = useState<UpcomingWindow | null>(null);
  const dayHeading = useRef<HTMLHeadingElement>(null);
  const touch = useRef<number | null>(null);
  const transition = useRef<ViewTransition | null>(null);
  const bounds = scheduleWindow(today);
  const signature = JSON.stringify({ ...EMPTY, ...preferences, followed_leagues: preferences.leagues ?? undefined });
  const upcomingKey = `${today}:${signature}`;
  const sameDay = savedUpcoming?.key.startsWith(`${today}:`);
  const upcoming: UpcomingWindow = savedUpcoming?.key === upcomingKey ? savedUpcoming : {
    key: upcomingKey, end: sameDay && savedUpcoming ? savedUpcoming.end : dayAfter(today, 7),
    expanded: sameDay && savedUpcoming ? savedUpcoming.expanded : false, pending: false, done: false,
  };
  const laterAnchors = laterAgendaAnchors(today, publishedYears);
  const requestedAnchors = [...new Set([
    ...monthAnchorsInRange(bounds.start, bounds.end),
    ...(scheduleView === "agenda" ? agendaAnchors(today) : []),
    ...(scheduleView === "agenda" && upcoming.expanded ? laterAnchors : []),
  ])].sort();
  const { months, errors, loadingYears, boundaryLoadingYears, manifests, facets } = useCalendarData(requestedAnchors, signature, timezone, retry);
  const laterLoading = upcoming.expanded && laterAnchors.some((anchor) => {
    const year = Number(anchor.slice(0, 4));
    return loadingYears.includes(year) || boundaryLoadingYears.includes(year) || (!months[anchor] && !errors[year]);
  });
  const laterErrors = upcoming.expanded ? [...new Set(publishedYears.map((year) => errors[year]).filter(Boolean))] : [];
  const canShowMore = !upcoming.done && preferences.leagues?.length !== 0 && laterAnchors.some((anchor) => `${anchor.slice(0, 4)}-12-31` > upcoming.end);
  useEffect(() => {
    const available = [...new Set([...(facets?.available_seasons || []), ...Object.values(manifests).flatMap((item) => item.available_seasons)])].sort((a, b) => a - b);
    if (available.length) setPublishedYears((previous) => previous.join() === available.join() ? previous : available);
  }, [facets, manifests]);
  function extendUpcoming() {
    const next = nextAgendaEnd(months, upcoming.end, bounds.end);
    setUpcoming({ ...upcoming, expanded: true, pending: false, end: next || upcoming.end, done: !next || !nextAgendaEnd(months, next, bounds.end) });
  }
  useEffect(() => {
    if (scheduleView !== "agenda" || !upcoming.pending || laterLoading) return;
    if (laterErrors.length) setUpcoming({ ...upcoming, pending: false }); else extendUpcoming();
  }, [scheduleView, upcoming.key, upcoming.pending, laterLoading, months, errors]);
  useEffect(() => {
    const timer = setInterval(() => setToday(todayIso()), 60_000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (day < bounds.start || day > bounds.end) { setDay(today); setView("month"); navigate(today); }
  }, [today]);
  useLayoutEffect(() => { if (view === "day") dayHeading.current?.focus({ preventScroll: true }); }, [view]);
  function animate(update: () => void, motion = "zoom") {
    transition.current?.skipTransition();
    if (motion === "zoom") flushSync(() => setSplitDate(null));
    if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) { update(); return; }
    document.documentElement.dataset.motion = motion;
    transition.current = document.startViewTransition(() => flushSync(update));
    void transition.current.finished.catch(() => {});
  }
  function navigate(date: string, focus = false) {
    const bounded = date < bounds.start ? bounds.start : date > bounds.end ? bounds.end : date;
    setMonth(firstOfMonth(bounded));
    setNavigation((previous) => ({ date: bounded, focus, id: previous.id + 1 }));
  }
  function openMonth(anchor: string) {
    flushSync(() => setMonth(firstOfMonth(anchor)));
    animate(() => { navigate(anchor, true); setView("month"); });
  }
  function openDay(date: string) {
    flushSync(() => setSplitDate(date));
    animate(() => { setDay(date); setView("day"); }, "open-day");
  }
  function closeDay() {
    animate(() => { setView("month"); setMonth(firstOfMonth(day));
      setNavigation((previous) => ({ date: day, focus: true, returnFromDay: true, id: previous.id + 1 })); }, "close-day");
  }
  function switchDay(date: string) {
    if (date < bounds.start || date > bounds.end) return;
    setDay(date); setSplitDate(date); setMonth(firstOfMonth(date));
    requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(`.week-strip [data-date="${date}"]`)?.focus({ preventScroll: true }));
  }
  function showEvents(items: EventCard[], date: string) { setSheet({ kind: "events", items, date }); }
  function jumpToday() {
    const now = todayIso();
    setToday(now);
    if (scheduleView === "agenda") { setPeriod("today"); return; }
    if (view === "day") { switchDay(now); return; }
    animate(() => { setView("month"); navigate(now); });
  }
  function changeScheduleView() {
    const next = scheduleView === "calendar" ? "agenda" : "calendar";
    setScheduleView(next);
    try { localStorage.setItem(VIEW_KEY, next); } catch { /* Active for this visit. */ }
  }
  function save() {
    const next = { ...draftPreferences, leagues: draft ?? leagues.map((league) => league.value) };
    setPreferences(next);
    try { localStorage.setItem(INTERESTS_KEY, JSON.stringify(next)); setStorageNote(""); }
    catch { setStorageNote("Interests are active for this visit; browser storage is unavailable."); }
    setSheet(null);
  }
  const year = Number(month.slice(0, 4));
  const yearAnchors = yearMonthAnchors(year);
  const manifest = manifests[view === "day" ? Number(day.slice(0, 4)) : year];
  const leagues = interestLeagues(facets?.leagues || []);
  const selected = months[firstOfMonth(day)]?.groups.find((group) => group.date === day);
  const dayError = errors[Number(day.slice(0, 4))];
  const calendarActive = scheduleView === "calendar";
  const week = Array.from({ length: 7 }, (_, index) => dayAfter(weekStart(day), index));
  function yearKey(delta: number) {
    document.querySelector<HTMLElement>(".year-grid")?.focus();
    setMonth(boundMonth(monthAt(monthIndex(month) + delta * 12), today));
  }
  return <div className="app-shell">
    <header className={`calendar-header ${view === "day" && calendarActive ? "day-header" : ""}`}>
      <div className="topbar">
        <div className="nav-left">{calendarActive && view !== "year" && <button className="back-button"
          aria-label={view === "day" ? `Back to ${monthTitle(day)}` : `Show ${year} year calendar`}
          onClick={() => view === "day" ? closeDay() : animate(() => setView("year"))}>
          ‹ {view === "day" ? monthTitle(day) : year}
        </button>}</div>
        <a className="brand" href="https://snowball-projects.github.io/">
          <img src={`${import.meta.env.BASE_URL}icon.png`} width="24" height="24" alt="" />kickoff
        </a>
        <div className="nav-right">
          <button className="interests-button" aria-label="Interests" onClick={() => {
            setDraft(preferences.leagues); setDraftPreferences(preferences); setSheet({ kind: "interests" });
          }}><span className="hamburger" aria-hidden="true"><i /><i /><i /></span></button>
          <button className="icon-button" aria-label="About kickoff and schedule coverage" onClick={() => setSheet({ kind: "info" })}>i</button>
        </div>
      </div>
      {view === "day" && calendarActive ? <>
        <div className="week-strip" style={{ viewTransitionName: "selected-week" }}
          onTouchStart={(event) => { touch.current = event.touches[0].clientX; }}
          onTouchEnd={(event) => { if (touch.current !== null) { const delta = event.changedTouches[0].clientX - touch.current;
            if (Math.abs(delta) > 50) switchDay(dayAfter(day, delta < 0 ? 7 : -7)); } touch.current = null; }}
          onKeyDown={(event) => {
            const delta = ({ ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 } as Record<string, number>)[event.key];
            if (delta) { event.preventDefault(); switchDay(dayAfter(day, delta)); }
          }}>
          {week.map((date, index) => <button key={date} data-date={date} disabled={date < bounds.start || date > bounds.end}
            aria-label={formatLongDate(date)} aria-pressed={date === day} onClick={() => switchDay(date)}>
            <span>{WEEKDAY_NARROW[index]}</span><b className={`${date === day ? "selected" : ""} ${date === today ? "today" : ""}`}>{Number(date.slice(-2))}</b>
          </button>)}
        </div>
        <h1 className="long-date" ref={dayHeading} tabIndex={-1}>{formatLongDate(day)}</h1>
      </> : <>
        <div className="heading-row">
          <h1 aria-live="polite">{!calendarActive ? "Agenda" : view === "year" ? year : monthTitle(month)}</h1>
          <button className={`view-slider ${!calendarActive ? "agenda-on" : ""}`} role="switch" aria-label="Agenda view"
            aria-checked={!calendarActive} onClick={changeScheduleView}>
            <span aria-hidden="true">▦</span><span aria-hidden="true">☷</span>
          </button>
        </div>
        {calendarActive && <div className="weekday-row" aria-hidden="true">{WEEKDAY_NARROW.map((label, index) => <span key={index}>{label}</span>)}</div>}
      </>}
    </header>
    <main className="calendar-body" onKeyDown={(event) => { if (event.key === "Escape" && view === "day" && !sheet) closeDay(); }}>
      <div hidden={!calendarActive || view !== "month"} className="month-stage">
        <div className="calendar-status" aria-live="polite">
          {errors[year] && <span>{errors[year]} <button onClick={() => setRetry((value) => value + 1)}>Retry</button></span>}
          {loadingYears.includes(year) && !errors[year] && <span>Loading schedule…</span>}
        </div>
        <MonthFeed start={bounds.start} end={bounds.end} today={today} months={months} navigation={navigation}
          active={calendarActive && view === "month"} splitDate={splitDate} onVisibleMonth={setMonth} onOpenDay={openDay} onEvents={showEvents} />
      </div>
      {calendarActive && view === "year" && <section className="year-grid" aria-label={`${year} calendar`} tabIndex={0}
        onKeyDown={(event) => { if (["PageUp", "PageDown", "ArrowLeft", "ArrowRight"].includes(event.key)) {
          event.preventDefault(); yearKey(["PageUp", "ArrowLeft"].includes(event.key) ? -1 : 1);
        } }}>
        {yearAnchors.map((anchor) => <button key={anchor} className={`mini-month ${anchor === firstOfMonth(today) ? "current-month" : ""}`}
          disabled={anchor < firstOfMonth(bounds.start) || anchor > firstOfMonth(bounds.end)} style={anchor === month ? { viewTransitionName: "calendar-zoom" } : undefined} aria-label={`Open ${monthLabel(anchor)}`} onClick={() => openMonth(anchor)}>
          <h2>{monthTitle(anchor).slice(0, 3)}</h2>
          <div className="mini-weekdays">{WEEKDAY_NARROW.map((label, index) => <span key={index}>{label}</span>)}</div>
          <div className="mini-days">{monthWeeksSunStart(anchor, [], { showAdjacentDays: false }).flat().map((cell, index) =>
            <span key={index} className={cell.date === today ? "mini-today" : ""}>{cell.date ? Number(cell.date.slice(-2)) : ""}</span>)}</div>
        </button>)}
      </section>}
      {calendarActive && view === "day" && <DayTimeline key={`${day}:${timezone}`} date={day} timezone={timezone} items={selected?.items || []}
        loading={!months[firstOfMonth(day)] && !dayError} error={dayError} onEvents={showEvents} onRetry={() => setRetry((value) => value + 1)} />}
      {!calendarActive && <Agenda today={today} period={period} onPeriod={setPeriod} upcomingEnd={upcoming.end}
        onShowMore={() => upcoming.expanded ? extendUpcoming() : setUpcoming({ ...upcoming, expanded: true, pending: true })}
        canShowMore={canShowMore} expandedYears={upcoming.expanded ? publishedYears : undefined}
        moreLoading={upcoming.pending || laterLoading} moreErrors={laterErrors} noMore={upcoming.done}
        months={months} errors={errors} timezone={timezone} resetKey={signature}
        onOpenDay={(date, id) => { const items = months[firstOfMonth(date)]?.groups.find((group) => group.date === date)?.items || [];
          const event = items.find((item) => item.event_id === id); if (event) showEvents([event], date); }} onRetry={() => setRetry((value) => value + 1)} />}
    </main>
    <button className="today-button" onClick={jumpToday}>Today</button>
    {sheet?.kind === "events" && <EventSheet items={sheet.items} date={sheet.date} timezone={timezone} onClose={() => setSheet(null)} />}
    {sheet?.kind === "interests" && <Sheet title="Interests" onClose={() => setSheet(null)}>
      {!leagues.length ? <p>{errors[year] || "Loading available leagues…"}</p> : <InterestGroups leagues={leagues} selected={draft ?? leagues.map((league) => league.value)} onChange={setDraft}
        preferences={draftPreferences} onPreferencesChange={setDraftPreferences} />}
      <div className="interest-actions"><button onClick={() => { setDraft(null);
        const { climbing, weightlifting } = defaultPreferences(); setDraftPreferences((previous) => ({ ...previous, climbing, weightlifting })); }}>Select all</button>
        <button onClick={() => setDraft([])}>Clear</button></div>
      <button className="primary-button" disabled={!facets || loadingYears.length > 0} onClick={save}>Show my calendar</button>
    </Sheet>}
    {sheet?.kind === "info" && <Sheet title="About kickoff" onClose={() => setSheet(null)}>
      <p>A sports calendar by <a href="https://snowball-projects.github.io/">snowball</a>.</p>
      <p>{timezoneLabel(timezone)} · {timezone}</p>
      <p>Updated {manifest?.updated_at?.slice(0, 10) || "unavailable"}</p>
      <p><a href="https://github.com/snowball-projects/kickoff" target="_blank" rel="noreferrer">Source ↗</a></p>
      <h3>Coverage</h3>
      <p>Published schedules, not live scores. Coverage is incomplete; an empty day means no matching published events. Dates and times can change.</p>
      <p>Golf: Full tour includes all published tournaments and majors. LPGA coverage is selected dates, mostly final dates outside the majors.</p>
      <p>Boxing: selected reviewed four-belt undisputed bouts and unifications of at least three full WBA, WBC, IBF or WBO titles in one division.
        No interim or secondary titles, exhibitions or influencer cards.</p>
      <p><a href="https://github.com/snowball-projects/kickoff/tree/main/data/reviewed" target="_blank" rel="noreferrer">Coverage details and omitted events ↗</a></p>
      <p>Verified times use your browser’s timezone automatically. Date-only events stay on their source dates with Time TBD.</p>
      <h3>Sources</h3>
      {manifest?.data_license_notice && <p>{manifest.data_license_notice}</p>}
      {manifest?.sources?.map((source) => <p key={source.name}><a href={source.url} target="_blank" rel="noreferrer">{source.name}</a>
        {" · "}<a href={source.license_url} target="_blank" rel="noreferrer">{source.license}</a></p>)}
      <h3>Privacy</h3>
      <p>Interests and options stay in this browser. No accounts, analytics, advertising or location access. Timezone comes from your browser;
        no lookup is sent. Static calendar browsing contacts no sports providers. GitHub Pages receives normal hosting requests.</p>
      {storageNote && <p>{storageNote}</p>}
      <p><a href={`${import.meta.env.BASE_URL}THIRD-PARTY-NOTICES.md`}>Licenses</a>{" · "}<a href="https://snowball-projects.github.io/operations/#kickoff">Operations</a></p>
    </Sheet>}
  </div>;
}
