import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const filters = { sport: "", league: "", competition_phase: "", country: "", city: "", tags: [] };
const signature = JSON.stringify(filters);
function event(id, date, instant = null, extra = {}) {
  return {
    event_id: id, source: "test", sport: "soccer", league: "EPL", event_type: "game",
    title: `Fixture ${id}`, calendar_date: date, end_calendar_date: date,
    start_time_utc: instant, start_time_local: null, participants: [], tags: [], ...extra,
  };
}
function bundle(year, events = []) {
  return { schema_version: "1", season: year, events, providers: [], available_seasons: [year] };
}
function fixtures(t, bundles) {
  const requests = [];
  t.mock.method(globalThis, "fetch", async (url) => {
    const year = Number(url.match(/(\d+)\.json$/)[1]);
    requests.push(year);
    return bundles[year] ? Response.json(bundles[year]) : new Response("missing", { status: 404 });
  });
  return requests;
}
const on = (calendar, date) => calendar.groups.find((group) => group.date === date)?.items || [];
async function until(store, predicate) {
  if (predicate(store.getSnapshot())) return store.getSnapshot();
  return new Promise((resolve) => {
    const unsubscribe = store.subscribe(() => {
      if (predicate(store.getSnapshot())) { unsubscribe(); resolve(store.getSnapshot()); }
    });
  });
}

test("device timezone detection is local and safely falls back to UTC", async (t) => {
  const { browserTimezone, safeTimezone, timezoneLabel } = await loadModule("date-utils");
  const Original = Intl.DateTimeFormat;
  let detected = "America/Chicago";
  let failed = false;
  t.mock.method(Intl, "DateTimeFormat", function (locale, options) {
    if (options) return new Original(locale, options);
    if (failed) throw new Error("Unavailable device setting");
    return { resolvedOptions: () => ({ timeZone: detected }) };
  });
  t.mock.method(globalThis, "fetch", () => { throw new Error("Timezone detection must not make network requests"); });
  assert.equal(browserTimezone(), "America/Chicago");
  assert.equal(timezoneLabel(browserTimezone()), "Local time · Chicago");
  assert.equal(timezoneLabel("America/Argentina/Buenos_Aires"), "Local time · Buenos Aires");
  detected = undefined;
  assert.equal(browserTimezone(), "UTC");
  detected = "Invalid/Timezone";
  assert.equal(browserTimezone(), "UTC");
  assert.equal(safeTimezone("Invalid/Timezone"), "UTC");
  assert.equal(timezoneLabel("Invalid/Timezone"), "UTC");
  failed = true;
  assert.equal(browserTimezone(), "UTC");
});

test("today and event clocks agree in positive, negative and fractional offsets", async () => {
  const { todayIso, eventCalendarDate, eventTimeBucket, eventTimeLabel } = await loadModule("date-utils");
  const midnight = event("midnight", "2026-12-31", "2027-01-01T00:00:00Z");
  for (const [zone, date, clock] of [
    ["UTC", "2027-01-01", "00:00"],
    ["America/Los_Angeles", "2026-12-31", "16:00"],
    ["Pacific/Kiritimati", "2027-01-01", "14:00"],
    ["Asia/Kathmandu", "2027-01-01", "05:45"],
  ]) {
    assert.equal(todayIso(zone, new Date(midnight.start_time_utc)), date);
    assert.equal(eventCalendarDate(midnight, zone), date);
    assert.equal(eventTimeBucket(midnight, zone), clock);
    assert.equal(eventTimeLabel(midnight, zone), new Intl.DateTimeFormat(undefined, {
      hour: "numeric", minute: "2-digit", timeZone: zone,
    }).format(new Date(midnight.start_time_utc)));
  }
  assert.equal(eventCalendarDate(midnight, "Invalid/Timezone"), "2027-01-01");
  assert.equal(eventTimeBucket(midnight, "Invalid/Timezone"), "00:00");
});

test("DST uses each event's offset, preserving both fall-back instants", async () => {
  const { eventCalendarDate, eventTimeBucket, eventTimestamp } = await loadModule("date-utils");
  const clocks = [
    ["2026-03-08T06:30:00Z", "01:30"], ["2026-03-08T07:30:00Z", "03:30"],
    ["2026-11-01T05:30:00Z", "01:30"], ["2026-11-01T06:30:00Z", "01:30"],
  ];
  for (const [instant, expected] of clocks) {
    const item = event(instant, instant.slice(0, 10), instant);
    assert.equal(eventTimeBucket(item, "America/New_York"), expected);
    assert.equal(eventCalendarDate(item, "America/New_York"), instant.slice(0, 10));
  }
  assert.equal(eventTimestamp(event("later", "2026-11-01", clocks[3][0])) -
    eventTimestamp(event("earlier", "2026-11-01", clocks[2][0])), 3_600_000);
});

test("date-only and unverified local clocks keep their source date", async () => {
  const { eventCalendarDate, eventTimeBucket, eventTimeLabel, eventInstant } = await loadModule("date-utils");
  for (const item of [
    event("date-only", "2026-01-01"),
    event("unverified", "2026-01-01", null, { start_time_local: "2026-01-01T01:00:00" }),
    event("invalid", "2026-01-01", "not-a-date"),
  ]) {
    for (const zone of ["Pacific/Kiritimati", "America/Los_Angeles"]) {
      assert.equal(eventCalendarDate(item, zone), "2026-01-01");
      assert.equal(eventTimeLabel(item, zone), "Time TBD");
      assert.equal(eventTimeBucket(item, zone), "tbd");
      assert.equal(eventInstant(item), null);
    }
  }
  const verified = event("offset", "2026-01-01", null, { start_time_local: "2026-01-01T01:30:00+09:00" });
  assert.equal(eventCalendarDate(verified, "America/Los_Angeles"), "2025-12-31");
  assert.equal(eventTimeBucket(verified, "America/Los_Angeles"), "08:30");
});

test("calendar-only labels and grids survive a device's skipped civil date", async () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = "Pacific/Apia";
    const { formatLongDate, formatShortDate, formatDayNumber, monthGridSunStart } = await loadModule("date-utils");
    assert.equal(formatLongDate("2011-12-30"), "Friday, December 30, 2011");
    assert.equal(formatShortDate("2011-12-30"), "Dec 30");
    assert.equal(formatDayNumber("2011-12-30"), 30);
    const cells = monthGridSunStart("2011-12-01", []);
    assert.equal(cells.filter((cell) => cell.date === "2011-12-30").length, 1);
    assert.equal(cells.filter((cell) => cell.inMonth).length, 31);
    assert.equal(cells[0].date, "2011-11-27");
  } finally {
    if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous;
  }
});

test("calendar placement crosses month boundaries while date-only spans stay inclusive", async (t) => {
  fixtures(t, { 2026: bundle(2026, [
    event("early", "2026-03-01", "2026-03-01T00:30:00Z"),
    event("late", "2026-03-31", "2026-03-31T23:30:00Z"),
    event("span", "2026-03-07", null, { end_calendar_date: "2026-03-09" }),
  ]) });
  const { getCalendar } = await loadModule("data");
  assert.equal(on(await getCalendar("month", 2026, "2026-02-01", filters, "America/Chicago"), "2026-02-28")[0].event_id, "early");
  assert.equal(on(await getCalendar("month", 2026, "2026-04-01", filters, "Asia/Tokyo"), "2026-04-01")[0].event_id, "late");
  for (const zone of ["America/New_York", "Pacific/Kiritimati"]) {
    const march = await getCalendar("month", 2026, "2026-03-01", filters, zone);
    for (const date of ["2026-03-07", "2026-03-08", "2026-03-09"]) {
      const span = on(march, date).find((item) => item.event_id === "span");
      assert.equal(span.start_calendar_date, "2026-03-07");
      assert.equal(span.end_calendar_date, "2026-03-09");
    }
  }
});

test("calendar and year-scoped search include neighboring-year events exactly once", async (t) => {
  fixtures(t, {
    2026: bundle(2026, [event("east", "2026-12-31", "2026-12-31T23:30:00Z"), event("date-only", "2026-12-31")]),
    2027: bundle(2027, [event("west", "2027-01-01", "2027-01-01T00:30:00Z")]),
  });
  const { getCalendar, searchEvents } = await loadModule("data");
  const january = await getCalendar("month", 2027, "2027-01-01", filters, "Pacific/Kiritimati");
  assert.deepEqual(on(january, "2027-01-01").map((item) => item.event_id), ["east", "west"]);
  assert.ok(on(january, "2027-01-01").every((item) => item.end_calendar_date === "2027-01-01"));
  const december = await getCalendar("month", 2026, "2026-12-01", filters, "America/Los_Angeles");
  assert.deepEqual(on(december, "2026-12-31").map((item) => item.event_id), ["date-only", "east", "west"]);
  const search = await searchEvents(2027, "Fixture", filters, "Pacific/Kiritimati");
  assert.deepEqual(search.items.map((item) => item.event_id), ["east", "west"]);
  assert.ok(search.items.every((item) => item.calendar_date === "2027-01-01" && item.end_calendar_date === "2027-01-01"));
  assert.equal(search.timezone, "Pacific/Kiritimati");
  assert.deepEqual((await searchEvents(2026, "Fixture", filters, "Pacific/Kiritimati")).items.map((item) => item.event_id), ["date-only"]);
});

test("a slow neighboring year merges later without blocking the current year", async (t) => {
  let resolvePrevious;
  const previous = new Promise((resolve) => { resolvePrevious = resolve; });
  t.mock.method(globalThis, "fetch", async (url) => url.endsWith("2026.json") ? previous : Response.json(bundle(2027, [event("own", "2027-01-02")])));
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2027-01-01"], signature, "UTC", 0);
  const ready = await until(store, (state) => !state.loadingYears.length);
  assert.equal(on(ready.months["2027-01-01"], "2027-01-02")[0].event_id, "own");
  resolvePrevious(Response.json(bundle(2026, [event("spillover", "2026-12-31", "2027-01-01T01:00:00Z")])));
  const merged = await until(store, (state) => on(state.months["2027-01-01"], "2027-01-01").length === 1);
  assert.equal(on(merged.months["2027-01-01"], "2027-01-01")[0].event_id, "spillover");
});

test("published January 2027 includes all six real events from the 2026 bundle", async (t) => {
  const bundles = Object.fromEntries(await Promise.all([2026, 2027].map(async (year) => [year,
    JSON.parse(await readFile(new URL(`../../data/published/${year}.json`, import.meta.url), "utf8")),
  ])));
  fixtures(t, bundles);
  const { getCalendar } = await loadModule("data");
  const january = await getCalendar("month", 2027, "2027-01-01", filters, "UTC");
  const actual = new Set(on(january, "2027-01-01").map((item) => item.event_id));
  const spillovers = bundles[2026].events.filter((item) => item.start_time_utc?.startsWith("2027-01-01"));
  assert.equal(spillovers.length, 6);
  for (const item of spillovers) assert.ok(actual.has(item.event_id), item.event_id);
});

test("an unpublished year still exposes neighboring spillovers and keeps its notice", async (t) => {
  fixtures(t, { 2026: bundle(2026, [event("spillover", "2026-01-01", "2026-01-01T01:00:00Z")]) });
  const { CalendarDataStore, getCalendar } = await loadModule("data");
  const december = await getCalendar("month", 2025, "2025-12-01", filters, "America/Los_Angeles");
  assert.equal(on(december, "2025-12-31")[0].event_id, "spillover");
  await assert.rejects(getCalendar("month", 2025, "2025-06-01", filters, "America/Los_Angeles"), /No published schedule for 2025/);
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  // The empty January boundary must not discard December's available event.
  store.update(["2025-01-01", "2025-12-01"], signature, "America/Los_Angeles", 0);
  const state = await until(store, (snapshot) => Boolean(snapshot.months["2025-12-01"]));
  assert.equal(on(state.months["2025-12-01"], "2025-12-31")[0].event_id, "spillover");
  assert.equal(state.errors[2025], "No published schedule for 2025.");
  assert.equal(state.months["2025-01-01"], undefined);
  store.update(["2025-12-01"], signature, "Pacific/Kiritimati", 0);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(store.getSnapshot().months["2025-12-01"], undefined);
});

test("reentering a missing year's boundary can reveal a known neighboring event", async (t) => {
  fixtures(t, { 2026: bundle(2026, [event("spillover", "2026-01-01", "2026-01-01T01:00:00Z")]) });
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2025-06-01"], signature, "America/Los_Angeles", 0);
  await until(store, (state) => !state.loadingYears.length);
  store.update(["2025-12-01"], signature, "America/Los_Angeles", 0);
  const state = await until(store, (snapshot) => Boolean(snapshot.months["2025-12-01"]));
  assert.equal(on(state.months["2025-12-01"], "2025-12-31")[0].event_id, "spillover");
  assert.equal(state.errors[2025], "No published schedule for 2025.");
});

test("a boundary fetch failure preserves primary events and an explicit retry repairs it", async (t) => {
  let failed = true;
  t.mock.method(globalThis, "fetch", async (url) => url.endsWith("2026.json")
    ? failed ? new Response("failure", { status: 503 })
      : Response.json(bundle(2026, [event("spillover", "2026-12-31", "2027-01-01T01:00:00Z")]))
    : Response.json(bundle(2027, [event("own", "2027-01-02")])));
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2027-01-01"], signature, "UTC", 0);
  const state = await until(store, (snapshot) => Boolean(snapshot.errors[2027]));
  assert.match(state.errors[2027], /Some year-boundary events could not be loaded/);
  assert.equal(on(state.months["2027-01-01"], "2027-01-02")[0].event_id, "own");
  failed = false;
  store.update(["2027-01-01"], signature, "UTC", 1);
  const retried = await until(store, (snapshot) => snapshot.months["2027-01-01"] && on(snapshot.months["2027-01-01"], "2027-01-01").length === 1);
  assert.deepEqual(retried.errors, {});
  assert.equal(on(retried.months["2027-01-01"], "2027-01-01")[0].event_id, "spillover");
});

test("changing timezone while a neighbor loads cannot restore stale boundary placement", async (t) => {
  let resolvePrevious;
  const previous = new Promise((resolve) => { resolvePrevious = resolve; });
  t.mock.method(globalThis, "fetch", async (url) => url.endsWith("2026.json") ? previous : Response.json(bundle(2027)));
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2027-01-01"], signature, "UTC", 0);
  await until(store, (state) => !state.loadingYears.length);
  store.update(["2027-01-01"], signature, "America/Los_Angeles", 0);
  await until(store, (state) => !state.loadingYears.length);
  resolvePrevious(Response.json(bundle(2026, [event("spillover", "2026-12-31", "2027-01-01T01:00:00Z")])));
  await new Promise((resolve) => setImmediate(resolve));
  const month = store.getSnapshot().months["2027-01-01"];
  assert.equal(month.timezone, "America/Los_Angeles");
  assert.equal(month.total_events, 0);
});

test("a failed neighbor cannot block scrolling to June or recomputing interests", async (t) => {
  const current = bundle(2027, [
    event("january-football", "2027-01-02"),
    event("january-race", "2027-01-03", null, { league: "F1" }),
    event("june-football", "2027-06-02"),
    event("june-race", "2027-06-03", null, { league: "F1" }),
  ]);
  t.mock.method(globalThis, "fetch", async (url) => url.endsWith("2026.json")
    ? new Response("failure", { status: 503 }) : Response.json(current));
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2027-01-01"], signature, "UTC", 0);
  const failed = await until(store, (state) => Boolean(state.errors[2027]));
  assert.match(failed.errors[2027], /Some year-boundary events could not be loaded/);
  assert.equal(failed.months["2027-01-01"].total_events, 2);

  const footballOnly = JSON.stringify({ ...filters, followed_leagues: ["EPL"] });
  store.update(["2027-01-01"], footballOnly, "UTC", 0);
  const changed = await until(store, (state) => !state.loadingYears.length);
  assert.equal(changed.months["2027-01-01"].total_events, 1);
  assert.equal(on(changed.months["2027-01-01"], "2027-01-02")[0].event_id, "january-football");

  store.update(["2027-06-01"], footballOnly, "UTC", 0);
  const june = await until(store, (state) => !state.loadingYears.length);
  assert.equal(june.months["2027-06-01"].total_events, 1);
  assert.equal(on(june.months["2027-06-01"], "2027-06-02")[0].event_id, "june-football");
  assert.deepEqual(june.errors, {});
  store.update(["2027-06-01"], signature, "UTC", 0);
  const all = await until(store, (state) => !state.loadingYears.length);
  assert.equal(all.months["2027-06-01"].total_events, 2);
});

test("December spillovers publish while January's unrelated neighbor is still loading", async (t) => {
  let resolvePrevious;
  const previous = new Promise((resolve) => { resolvePrevious = resolve; });
  t.mock.method(globalThis, "fetch", async (url) => {
    if (url.endsWith("2025.json")) return previous;
    if (url.endsWith("2027.json")) return Response.json(bundle(2027, [event("december-spillover", "2027-01-01", "2027-01-01T01:00:00Z")]));
    return Response.json(bundle(2026));
  });
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => { store.cancel(); resolvePrevious(Response.json(bundle(2025))); });
  store.update(["2026-01-01", "2026-12-01"], signature, "America/Los_Angeles", 0);
  const state = await until(store, (snapshot) => snapshot.months["2026-12-01"]?.total_events === 1);
  assert.equal(on(state.months["2026-12-01"], "2026-12-31")[0].event_id, "december-spillover");
  assert.equal(state.months["2026-01-01"].total_events, 0);
  assert.deepEqual(state.errors, {});
  resolvePrevious(Response.json(bundle(2025)));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(store.getSnapshot().months["2026-12-01"].total_events, 1);
});
