import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
import { publishedFiles } from "./published-fixture.mjs";

const filters = { sport: "", league: "", competition_phase: "", country: "", city: "", tags: [] };
const signature = JSON.stringify(filters);
const bundle = (season, events = []) => ({ season, events });
function event(id, league = "EPL", sport = "soccer", year = 2026) {
  return { event_id: id, source: "fixture", season: String(year), status: "scheduled", competition_phase: "regular_season", league, sport,
    event_type: "game", title: id, calendar_date: `${year}-09-12`, start_time_utc: null, participants: [], tags: [] };
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function started(predicate) {
  for (let i = 0; i < 100; i++) { if (predicate()) return; await tick(); }
  assert.fail("The expected request did not start");
}
async function settled(store) {
  if (!store.getSnapshot().loadingYears.length) return store.getSnapshot();
  return new Promise((resolve) => {
    const unsubscribe = store.subscribe(() => {
      if (!store.getSnapshot().loadingYears.length) { unsubscribe(); resolve(store.getSnapshot()); }
    });
  });
}
function serve(t, files, intercept) {
  const requests = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    const file = url.split("/").at(-1);
    requests.push(file);
    const response = intercept?.(file, options);
    if (response !== undefined) return response;
    return files[file] ? Response.json(files[file]) : new Response("missing", { status: 404 });
  });
  return requests;
}
const ids = (calendar) => calendar.groups.flatMap((group) => group.items.map((item) => item.event_id));

test("manifest failures retry and published empty years need no event file", async (t) => {
  const files = publishedFiles([bundle(2026)]);
  let attempts = 0;
  const requests = serve(t, files, () => ++attempts === 1 ? new Response("offline", { status: 503 }) : undefined);
  const { getManifest, getCalendar } = await loadModule("data");
  await assert.rejects(getManifest(2026), /could not be loaded/);
  assert.equal((await getManifest(2026)).all_events, 0);
  assert.equal((await getCalendar("month", 2026, "2026-09-01", filters, "UTC")).total_events, 0);
  await assert.rejects(getManifest(2027), { message: "No published schedule for 2027." });
  assert.deepEqual(requests, ["manifest.json", "manifest.json"]);
  assert.deepEqual(Object.keys(files), ["manifest.json"]);
});

test("interests use only manifest metadata; calendar consumers share just selected sports", async (t) => {
  const files = publishedFiles([bundle(2026, [event("nfl", "NFL", "football"), event("soccer"), event("nba", "NBA", "basketball")])]);
  const requests = serve(t, files);
  const { getManifest, getFilters, getCalendarRange, getCalendar } = await loadModule("data");
  const [manifest, facets] = await Promise.all([getManifest(2026), getFilters(2026, filters, "UTC")]);
  assert.equal(manifest.all_events, 3);
  assert.deepEqual(facets.leagues.map(({ value }) => value), ["EPL", "NBA", "NFL"]);
  assert.deepEqual(Object.keys(facets).sort(), ["available_seasons", "leagues", "season", "sports", "total_events"]);
  assert.equal("events" in manifest, false);
  assert.deepEqual(requests, ["manifest.json"]);
  const nfl = { ...filters, followed_leagues: ["NFL"] };
  const [first, second] = await Promise.all([
    getCalendarRange(2026, ["2026-09-01", "2026-10-01"], nfl, "UTC"),
    getCalendar("month", 2026, "2026-09-01", nfl, "UTC"),
  ]);
  assert.deepEqual(ids(first["2026-09-01"]), ["nfl"]);
  assert.deepEqual(ids(second), ["nfl"]);
  assert.deepEqual(requests, ["manifest.json", "2026-football.json"]);
  assert.equal((await getCalendar("month", 2026, "2026-09-01", { ...filters, followed_leagues: [] }, "UTC")).total_events, 0);
  assert.equal(requests.length, 2);
  assert.equal((await getCalendar("month", 2026, "2026-09-01", filters, "UTC")).total_events, 3);
  assert.deepEqual(requests.slice(2).sort(), ["2026-basketball.json", "2026-soccer.json"]);
});

test("direct sport and league filters intersect saved interests before downloading", async (t) => {
  const files = publishedFiles([bundle(2026, [event("nfl", "NFL", "football"), event("epl"), event("liga", "LA_LIGA")])]);
  const requests = serve(t, files);
  const { getCalendar, getFilters } = await loadModule("data");
  assert.equal((await getCalendar("month", 2026, "2026-09-01", { ...filters, sport: "soccer", followed_leagues: ["NFL"] }, "UTC")).total_events, 0);
  const none = await getFilters(2026, { ...filters, followed_leagues: [] }, "UTC");
  assert.equal(none.total_events, 0);
  assert.deepEqual(none.sports, []);
  assert.deepEqual(none.leagues, []);
  assert.deepEqual(requests, ["manifest.json"]);
  assert.deepEqual(ids(await getCalendar("month", 2026, "2026-09-01", { ...filters, league: "epl", sport: "SOCCER", followed_leagues: ["NFL", "EPL"] }, "UTC")), ["epl"]);
  assert.deepEqual(requests, ["manifest.json", "2026-soccer.json"]);
  assert.deepEqual((await getFilters(2026, { ...filters, followed_leagues: ["LA_LIGA"] }, "UTC")).leagues,
    [{ value: "LA_LIGA", count: 1, sport: "soccer" }]);
  assert.equal(requests.length, 2);
});

test("sport cache has no artificial year cap and revisiting loaded seasons reuses files", async (t) => {
  const years = Array.from({ length: 8 }, (_, i) => 2026 + i);
  const requests = serve(t, publishedFiles(years.map((year) => bundle(year, [event(`game-${year}`, "NFL", "football", year)]))));
  const { getCalendar } = await loadModule("data");
  for (const year of [...years, years[0]]) assert.equal((await getCalendar("month", year, `${year}-09-01`, filters, "UTC")).total_events, 1);
  assert.equal(requests.filter((file) => file === "manifest.json").length, 1);
  for (const year of years) assert.equal(requests.filter((file) => file === `${year}-football.json`).length, 1);
});

test("a failed sport file retries without throwing away the shared manifest", async (t) => {
  let attempts = 0;
  const requests = serve(t, publishedFiles([bundle(2026, [event("game")])]), (file) =>
    file.endsWith("-soccer.json") && ++attempts === 1 ? new Response("offline", { status: 503 }) : undefined);
  const { getCalendar } = await loadModule("data");
  await assert.rejects(getCalendar("month", 2026, "2026-09-01", filters, "UTC"), /2026 could not be loaded/);
  assert.deepEqual(ids(await getCalendar("month", 2026, "2026-09-01", filters, "UTC")), ["game"]);
  assert.deepEqual(requests, ["manifest.json", "2026-soccer.json", "2026-soccer.json"]);
});

test("changing interests recovers from a failed sport without an explicit Retry", async (t) => {
  const files = publishedFiles([bundle(2026, [event("nfl", "NFL", "football"), event("epl")])]);
  const requests = serve(t, files, (file) => file === "2026-football.json" ? new Response("offline", { status: 503 }) : undefined);
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-09-01"], JSON.stringify({ ...filters, followed_leagues: ["NFL"] }), "UTC", 0);
  const failed = await settled(store);
  assert.match(failed.errors[2026], /could not be loaded/);
  assert.equal(failed.months["2026-09-01"], undefined);
  store.update(["2026-09-01"], JSON.stringify({ ...filters, followed_leagues: ["EPL"] }), "UTC", 0);
  const recovered = await settled(store);
  assert.deepEqual(recovered.errors, {});
  assert.deepEqual(ids(recovered.months["2026-09-01"]), ["epl"]);
  assert.deepEqual(requests, ["manifest.json", "2026-football.json", "2026-soccer.json"]);
});

test("aborting one consumer suppresses its result while the shared sport request finishes and caches", async (t) => {
  const pending = deferred();
  const files = publishedFiles([bundle(2026, [event("game")])]);
  const requests = serve(t, files, (file, options) => {
    assert.equal(options?.signal, undefined, "shared transport outlives individual consumers");
    return file === "2026-soccer.json" ? pending.promise : undefined;
  });
  const { getCalendar } = await loadModule("data");
  const controller = new AbortController();
  const first = getCalendar("month", 2026, "2026-09-01", filters, "UTC", controller.signal);
  const aborted = assert.rejects(first, { name: "AbortError" });
  const second = getCalendar("month", 2026, "2026-09-01", filters, "UTC");
  await started(() => requests.includes("2026-soccer.json"));
  controller.abort();
  pending.resolve(Response.json(files["2026-soccer.json"]));
  await aborted;
  assert.deepEqual(ids(await second), ["game"]);
  assert.deepEqual(ids(await getCalendar("month", 2026, "2026-09-01", filters, "UTC")), ["game"]);
  assert.equal(requests.filter((file) => file === "2026-soccer.json").length, 1);
});

test("explicit Retry reloads index and sports; a stale rejection cannot delete the replacement cache", async (t) => {
  const old = deferred();
  const files = publishedFiles([bundle(2026, [event("fresh")])]);
  let sportAttempts = 0;
  const requests = serve(t, files, (file) => file === "2026-soccer.json" && ++sportAttempts === 1 ? old.promise : undefined);
  const { CalendarDataStore, getCalendar } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-09-01"], signature, "UTC", 0);
  await started(() => sportAttempts === 1);
  store.update(["2026-09-01"], signature, "UTC", 1);
  assert.deepEqual(ids((await settled(store)).months["2026-09-01"]), ["fresh"]);
  old.reject(new TypeError("old request failed"));
  await tick();
  assert.deepEqual(ids(await getCalendar("month", 2026, "2026-09-01", filters, "UTC")), ["fresh"]);
  assert.equal(sportAttempts, 2);
  assert.equal(requests.filter((file) => file === "manifest.json").length, 2);
  assert.deepEqual(store.getSnapshot().errors, {});
});

test("missing years come from the index and explicit Retry discovers newly published years", async (t) => {
  const files = publishedFiles([bundle(2026, [event("fixture")])]);
  const requests = serve(t, files);
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-09-01", "2027-09-01"], signature, "UTC", 0);
  const initial = await settled(store);
  assert.deepEqual(Object.keys(initial.months), ["2026-09-01"]);
  assert.equal(initial.errors[2027], "No published schedule for 2027.");
  assert.deepEqual(initial.facets.leagues, [{ value: "EPL", count: 1, sport: "soccer" }]);
  store.update(["2027-09-01"], JSON.stringify({ ...filters, followed_leagues: [] }), "UTC", 0);
  assert.equal((await settled(store)).errors[2027], "No published schedule for 2027.");
  assert.equal(requests.filter((file) => file === "manifest.json").length, 1);
  Object.assign(files, publishedFiles([bundle(2026), bundle(2027, [event("new", "NFL", "football", 2027)])]));
  store.update(["2027-09-01"], JSON.stringify({ ...filters, followed_leagues: [] }), "UTC", 1);
  const discovered = await settled(store);
  assert.deepEqual(discovered.errors, {});
  assert.equal(discovered.manifests[2027].all_events, 1);
  assert.equal(discovered.months["2027-09-01"].total_events, 0);
  assert.equal(requests.filter((file) => file === "manifest.json").length, 2);
  assert.equal(requests.includes("2027-football.json"), false);
});

test("sliding windows reuse shared months and discard offscreen data", async (t) => {
  const requests = serve(t, publishedFiles([bundle(2026, [event("fixture")])]));
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-09-01", "2026-10-01"], signature, "UTC", 0);
  const first = await settled(store);
  store.update(["2026-10-01", "2026-11-01"], signature, "UTC", 0);
  const second = await settled(store);
  assert.deepEqual(Object.keys(second.months), ["2026-10-01", "2026-11-01"]);
  assert.equal(second.months["2026-10-01"], first.months["2026-10-01"]);
  assert.deepEqual(requests, ["manifest.json", "2026-soccer.json"]);
  store.update([], signature, "UTC", 0);
  assert.deepEqual(store.getSnapshot().months, {});
  assert.deepEqual(store.getSnapshot().manifests, {});
});

test("filter changes suppress stale sport results and pending windows load new anchors", async (t) => {
  const pending = deferred();
  const files = publishedFiles([bundle(2026, [event("football"), event("race", "F1", "motorsport")])]);
  const requests = serve(t, files, (file) => file === "2026-soccer.json" ? pending.promise : undefined);
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-08-01", "2026-09-01"], signature, "UTC", 0);
  await started(() => requests.includes("2026-soccer.json"));
  const next = JSON.stringify({ ...filters, followed_leagues: ["F1"] });
  store.update(["2026-09-01"], next, "America/Chicago", 0);
  store.update(["2026-09-01", "2026-10-01"], next, "America/Chicago", 0);
  const state = await settled(store);
  assert.deepEqual(Object.keys(state.months), ["2026-09-01", "2026-10-01"]);
  assert.deepEqual(ids(state.months["2026-09-01"]), ["race"]);
  assert.equal(state.months["2026-09-01"].timezone, "America/Chicago");
  pending.resolve(Response.json(files["2026-soccer.json"]));
  await tick();
  assert.deepEqual(ids(store.getSnapshot().months["2026-09-01"]), ["race"]);
  assert.deepEqual(store.getSnapshot().errors, {});
});

test("a year removed while its sport loads cannot repopulate the current window", async (t) => {
  const previous = deferred();
  const files = publishedFiles([bundle(2026, [event("old")]), bundle(2027, [event("new", "EPL", "soccer", 2027)])]);
  const requests = serve(t, files, (file) => file === "2026-soccer.json" ? previous.promise : undefined);
  const { CalendarDataStore } = await loadModule("data");
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-09-01", "2027-09-01"], signature, "UTC", 0);
  await started(() => requests.includes("2026-soccer.json"));
  store.update(["2027-09-01"], signature, "UTC", 0);
  await settled(store);
  previous.resolve(Response.json(files["2026-soccer.json"]));
  await tick();
  assert.deepEqual(Object.keys(store.getSnapshot().months), ["2027-09-01"]);
  assert.deepEqual(Object.keys(store.getSnapshot().manifests), ["2027"]);
  assert.deepEqual(store.getSnapshot().errors, {});
});

test("league sport metadata survives multi-year facets into future-family interests without changing IDs", async (t) => {
  const files = publishedFiles([2026, 2027].map((year) => bundle(year, [event(`future-${year}`, "FUTURE_SERIES", "motorsport", year)])));
  serve(t, files);
  const { getFilters, CalendarDataStore } = await loadModule("data");
  const { readPreferences, allPreferences, INTERESTS_KEY } = await loadModule("interest-preferences");
  const { interestGroups, leagueVisual } = await loadModule("calendar-helpers");
  assert.deepEqual((await getFilters(2026, filters, "UTC")).leagues, [{ value: "FUTURE_SERIES", count: 1, sport: "motorsport" }]);
  const store = new CalendarDataStore();
  t.after(() => store.cancel());
  store.update(["2026-09-01", "2027-09-01"], signature, "UTC", 0);
  const facets = (await settled(store)).facets;
  assert.deepEqual(facets.leagues, [{ value: "FUTURE_SERIES", count: 2, sport: "motorsport" }]);
  assert.deepEqual(interestGroups(facets.leagues), [{ name: "Motorsports", leagues: ["FUTURE_SERIES"] }]);
  assert.equal(leagueVisual(facets.leagues[0].value, facets.leagues[0].sport).className, "category-motorsport");
  const saved = ["FUTURE_SERIES", "OLD_UNPUBLISHED_ID"];
  assert.deepEqual(readPreferences({ getItem: (key) => key === INTERESTS_KEY ? JSON.stringify(allPreferences(saved)) : null }).leagues, saved);
});
