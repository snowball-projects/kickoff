import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const filters = {
  sport: "", league: "", competition_phase: "", country: "", city: "", tags: [],
};
const signature = JSON.stringify(filters);

function bundle(season, events = []) {
  return {
    schema_version: "1", season, events, providers: [], available_seasons: [season],
  };
}

function event(id, league = "EPL") {
  return {
    event_id: id, league, sport: "soccer", event_type: "game", title: id,
    calendar_date: "2026-09-12", start_time_utc: null, participants: [], tags: [],
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

async function settled(store) {
  if (store.getSnapshot().loadingYears.length) {
    await new Promise((resolve) => {
      const unsubscribe = store.subscribe(() => {
        if (!store.getSnapshot().loadingYears.length) {
          unsubscribe();
          resolve();
        }
      });
    });
  }
  return store.getSnapshot();
}

test("a transient schedule failure can be retried without reloading the page", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { getManifest } = await loadModule("data");
    let attempts = 0;
    globalThis.fetch = async () => {
      attempts += 1;
      if (attempts === 1) return new Response("unavailable", { status: 503 });
      return Response.json({
        schema_version: "1",
        season: 2026,
        events: [],
        providers: [],
        available_seasons: [2026],
      });
    };
    await assert.rejects(getManifest(2026), /unavailable/);
    const manifest = await getManifest(2026);
    assert.equal(manifest.season, 2026);
    assert.equal(manifest.all_events, 0);
    await getManifest(2026);
    assert.equal(attempts, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("concurrent consumers share a request and bundles evict by recent use", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { getManifest, getFilters, getCalendarRange } = await loadModule("data");
    const counts = new Map();
    globalThis.fetch = async (url) => {
      const year = Number(url.match(/(\d+)\.json$/)[1]);
      counts.set(year, (counts.get(year) || 0) + 1);
      return Response.json(bundle(year));
    };
    await Promise.all([
      getManifest(2026),
      getFilters(2026, filters, "UTC"),
      getCalendarRange(2026, ["2026-09-01", "2026-10-01"], filters, "UTC"),
    ]);
    assert.equal(counts.get(2026), 1);
    await getManifest(2027);
    await getManifest(2028);
    await getManifest(2026); // Keep this year, evict 2027 next.
    await getManifest(2029);
    await getManifest(2026);
    assert.equal(counts.get(2026), 1);
    await getManifest(2027);
    assert.equal(counts.get(2027), 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("an evicted request rejecting late cannot delete its newer cache entry", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { getManifest } = await loadModule("data");
    const old = deferred();
    let attempts = 0;
    globalThis.fetch = async (url) => {
      const year = Number(url.match(/(\d+)\.json$/)[1]);
      if (year === 2026 && ++attempts === 1) return old.promise;
      return Response.json(bundle(year));
    };
    const first = getManifest(2026);
    const rejection = assert.rejects(first, /unavailable/);
    for (const year of [2027, 2028, 2029]) await getManifest(year);
    await getManifest(2026);
    old.reject(new TypeError("offline"));
    await rejection;
    await getManifest(2026);
    assert.equal(attempts, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("missing years, transient failures and mismatched bundles remain distinct", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { getManifest } = await loadModule("data");
    globalThis.fetch = async () => new Response("missing", { status: 404 });
    await assert.rejects(getManifest(2027), { message: "No published schedule for 2027." });
    globalThis.fetch = async () => new Response("failure", { status: 503 });
    await assert.rejects(getManifest(2027), /Schedule data for 2027 is unavailable/);
    globalThis.fetch = async () => { throw new TypeError("offline"); };
    await assert.rejects(getManifest(2027), /Schedule data for 2027 is unavailable/);
    globalThis.fetch = async () => Response.json(bundle(2026));
    await assert.rejects(getManifest(2027), /2027.*belongs to 2026/);
    globalThis.fetch = async () => Response.json(bundle(2027));
    assert.equal((await getManifest(2027)).season, 2027);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("years settle independently and missing schedules retry only explicitly or on reentry", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { CalendarDataStore } = await loadModule("data");
    const counts = new Map();
    globalThis.fetch = async (url) => {
      const year = Number(url.match(/(\d+)\.json$/)[1]);
      counts.set(year, (counts.get(year) || 0) + 1);
      return year === 2026
        ? Response.json(bundle(year, [event("fixture")]))
        : new Response("missing", { status: 404 });
    };
    const store = new CalendarDataStore();
    store.update(["2026-12-01", "2027-01-01"], signature, "UTC", 0);
    let state = await settled(store);
    assert.deepEqual(Object.keys(state.months), ["2026-12-01"]);
    assert.equal(state.errors[2027], "No published schedule for 2027.");
    assert.deepEqual(state.facets.leagues, [{ value: "EPL", count: 1 }]);
    store.update(["2026-12-01", "2027-01-01", "2027-02-01"], signature, "UTC", 0);
    await settled(store);
    const changed = JSON.stringify({ ...filters, followed_leagues: [] });
    store.update(["2026-12-01", "2027-02-01"], changed, "UTC", 0);
    await settled(store);
    assert.equal(counts.get(2027), 1);
    store.update(["2026-12-01", "2027-02-01"], changed, "UTC", 1);
    await settled(store);
    assert.equal(counts.get(2027), 2);
    store.update(["2026-12-01"], changed, "UTC", 1);
    await settled(store);
    assert.deepEqual(store.getSnapshot().errors, {});
    store.update(["2027-02-01"], changed, "UTC", 1);
    state = await settled(store);
    assert.equal(counts.get(2027), 3);
    assert.deepEqual(state.months, {});
    assert.deepEqual(state.manifests, {});
    assert.deepEqual(state.facets.leagues, [{ value: "EPL", count: 1 }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("sliding windows reuse shared months and discard offscreen data", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { CalendarDataStore } = await loadModule("data");
    let attempts = 0;
    globalThis.fetch = async () => {
      attempts += 1;
      return Response.json(bundle(2026));
    };
    const store = new CalendarDataStore();
    store.update(["2026-09-01", "2026-10-01"], signature, "UTC", 0);
    const first = await settled(store);
    store.update(["2026-10-01", "2026-11-01"], signature, "UTC", 0);
    const second = await settled(store);
    assert.deepEqual(Object.keys(second.months), ["2026-10-01", "2026-11-01"]);
    assert.equal(second.months["2026-10-01"], first.months["2026-10-01"]);
    assert.equal(attempts, 1);
    store.update([], signature, "UTC", 0);
    assert.deepEqual(store.getSnapshot().months, {});
    assert.deepEqual(store.getSnapshot().manifests, {});
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("filter changes suppress stale results and pending windows load new anchors", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { CalendarDataStore } = await loadModule("data");
    const pending = deferred();
    let attempts = 0;
    globalThis.fetch = async () => { attempts += 1; return pending.promise; };
    const store = new CalendarDataStore();
    store.update(["2026-08-01", "2026-09-01"], signature, "UTC", 0);
    const nextSignature = JSON.stringify({ ...filters, followed_leagues: ["F1"] });
    store.update(["2026-09-01"], nextSignature, "America/Chicago", 0);
    store.update(["2026-09-01", "2026-10-01"], nextSignature, "America/Chicago", 0);
    pending.resolve(Response.json(bundle(2026, [event("football"), event("race", "F1")])));
    const state = await settled(store);
    assert.equal(attempts, 1);
    assert.deepEqual(Object.keys(state.months), ["2026-09-01", "2026-10-01"]);
    assert.deepEqual(state.months["2026-09-01"].groups
      .flatMap((group) => group.items.map((item) => item.event_id)), ["race"]);
    assert.equal(state.months["2026-09-01"].timezone, "America/Chicago");
    assert.deepEqual(state.errors, {});
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("a year removed while loading cannot repopulate the current window", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { CalendarDataStore } = await loadModule("data");
    const previous = deferred();
    globalThis.fetch = async (url) => url.includes("2026")
      ? previous.promise : Response.json(bundle(2027));
    const store = new CalendarDataStore();
    store.update(["2026-12-01", "2027-01-01"], signature, "UTC", 0);
    store.update(["2027-01-01"], signature, "UTC", 0);
    await settled(store);
    previous.resolve(Response.json(bundle(2026)));
    await new Promise((resolve) => setImmediate(resolve));
    const state = store.getSnapshot();
    assert.deepEqual(Object.keys(state.months), ["2027-01-01"]);
    assert.deepEqual(Object.keys(state.manifests), ["2027"]);
    assert.deepEqual(state.errors, {});
  } finally {
    globalThis.fetch = originalFetch;
  }
});
