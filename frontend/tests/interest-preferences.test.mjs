import assert from "node:assert/strict";
import { reviewedBundle } from "./reviewed-fixture.mjs";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const empty = { sport: "", league: "", country: "", city: "", competition_phase: "", tags: [] };
const storage = (values) => ({ getItem: (key) => values[key] || null });

test("current preferences preserve empty selections and all current options", async () => {
  const { readPreferences, defaultPreferences, INTERESTS_KEY } = await loadModule("interest-preferences");
  const saved = { leagues: ["PGA_TOUR", "LPGA_TOUR", "F1", "FUTURE"],
    golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "full_tour" }, motorsport_view: "full_weekend" };
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify(saved) })), { ...defaultPreferences(), ...saved });
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify({ ...saved, leagues: [] }) })).leagues, []);
  assert.equal(readPreferences(storage({})).leagues, null);
  assert.equal(readPreferences(storage({ [INTERESTS_KEY]: "broken" })).leagues, null);
});

test("golf interests expose only tours even when a year publishes only majors", async () => {
  const { interestGroups, leagueVisual } = await loadModule("calendar-helpers");
  assert.deepEqual(interestGroups(["GOLF_MAJORS_MEN", "GOLF_MAJORS_WOMEN", "LPGA_TOUR"]
    .map((value) => ({ value }))), [{ name: "Golf", leagues: ["PGA_TOUR", "LPGA_TOUR"] }]);
  assert.equal(leagueVisual("BOXING_MAJOR").shortLabel, "Boxing");
  assert.equal(leagueVisual("ONE").shortLabel, "One");
});

test("golf calendar modes suppress duplicate majors and football leakage", async () => {
  const bundle = reviewedBundle();
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => String(url).endsWith("/2026.json")
      ? Response.json(bundle) : new Response(null, { status: 404 });
    const { getCalendar } = await loadModule("data");
    const filters = { ...empty, followed_leagues: ["PGA_TOUR", "LPGA_TOUR"],
      golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "majors_only" } };
    const calendar = await getCalendar("month", 2026, "2026-04-01", filters, "UTC");
    assert.equal(calendar.groups.find((group) => group.date === "2026-04-09").items.length, 1);
  } finally { globalThis.fetch = original; }
});

test("retired boxing choices never hide reviewed bouts, while other saved options survive", async () => {
  const { matchesInterestOptions, readPreferences, INTERESTS_KEY } = await loadModule("interest-preferences");
  for (const categories of [[], ["four_belt"], ["three_belt_unification"], ["four_belt", "three_belt_unification"]]) {
    const old = { leagues: ["BOXING_MAJOR", "PGA_TOUR"], motorsport_view: "full_weekend",
      golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "full_tour" }, boxing_categories: categories };
    const migrated = readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify(old) }));
    assert.equal("boxing_categories" in migrated, false);
    assert.deepEqual(migrated.leagues, old.leagues);
    assert.deepEqual(migrated.golf_views, old.golf_views);
    assert.equal(migrated.motorsport_view, "full_weekend");
    for (const id of ["boxing-navarrete-foster-1", "future-reviewed-undisputed-bout"]) {
      assert.equal(matchesInterestOptions({ event_id: id, league: "BOXING_MAJOR" },
        { followed_leagues: migrated.leagues, boxing_categories: categories }), true);
    }
    assert.equal(matchesInterestOptions({ league: "BOXING_MAJOR" }, { followed_leagues: ["UFC"] }), false);
  }
});

test("duplicate suppression needs a matching identity and full span and retains source objects", async () => {
  const { uniqueGolfEvents } = await loadModule("interest-preferences");
  const reviewed = { league: "GOLF_MAJORS_MEN", title: "Open Championship", calendar_date: "2026-07-16", end_calendar_date: "2026-07-19" };
  const fed = { ...reviewed, league: "PGA_TOUR", title: "The Open" };
  assert.deepEqual(uniqueGolfEvents([reviewed, fed]), [fed]);
  assert.deepEqual(uniqueGolfEvents([reviewed]), [reviewed]);
  assert.equal(uniqueGolfEvents([reviewed, { ...fed, end_calendar_date: "2026-07-18" }]).length, 2);
});

test("session options default to all without changing existing competition selections", async () => {
  const { readPreferences, INTERESTS_KEY, defaultPreferences, matchesInterestOptions } = await loadModule("interest-preferences");
  const leagues = ["IFSC_WORLD_CUP", "IWF_WORLDS", "MASTERS_WORLDS", "FUTURE"];
  const old = readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify({ leagues }) }));
  assert.deepEqual(old.leagues, leagues);
  assert.deepEqual(old.climbing, defaultPreferences().climbing);
  assert.deepEqual(old.weightlifting, defaultPreferences().weightlifting);
  assert.equal(matchesInterestOptions({ sport: "weightlifting", league: "IWF_JUNIOR_WORLDS", tags: ["Men"] },
    { followed_leagues: ["IWF_WORLDS"] }), false);
  const current = { ...old, climbing: { genders: [], disciplines: ["Lead"] }, weightlifting: { genders: ["Women"] } };
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify(current) })), current);
});

test("gender and discipline intersect, combined sessions match either, and unknowns remain visible", async () => {
  const { matchesInterestOptions } = await loadModule("interest-preferences");
  const filters = { climbing: { genders: ["Women"], disciplines: ["Lead"] }, weightlifting: { genders: ["Men"] } };
  const climbing = (tags) => ({ sport: "climbing", league: "IFSC_WORLD_CUP", tags });
  assert.equal(matchesInterestOptions(climbing(["Women", "Boulder", "Lead"]), filters), true);
  assert.equal(matchesInterestOptions(climbing(["Women", "Boulder"]), filters), false);
  assert.equal(matchesInterestOptions(climbing(["Men", "Lead"]), filters), false);
  assert.equal(matchesInterestOptions(climbing(["Men", "Women", "Lead"]), filters), true);
  assert.equal(matchesInterestOptions(climbing(["Lead"]), filters), true);
  assert.equal(matchesInterestOptions(climbing(["Women"]), filters), true);
  assert.equal(matchesInterestOptions(climbing([]), filters), true);
  assert.equal(matchesInterestOptions(climbing([]), { climbing: { genders: [], disciplines: ["Lead"] } }), false);
  assert.equal(matchesInterestOptions(climbing([]), { climbing: { genders: ["Women"], disciplines: [] } }), false);
  const lifting = (tags) => ({ sport: "weightlifting", league: "MASTERS_WORLDS", tags });
  assert.equal(matchesInterestOptions(lifting(["Men", "Women"]), filters), true);
  assert.equal(matchesInterestOptions(lifting(["Women"]), filters), false);
  assert.equal(matchesInterestOptions(lifting([]), filters), true);
  assert.equal(matchesInterestOptions(lifting([]), { weightlifting: { genders: [] } }), false);
  assert.equal(matchesInterestOptions({ sport: "soccer", league: "EPL", tags: [] }, filters), true);
});

test("reviewed session facets apply to the calendar without altering source records", async () => {
  const bundle = reviewedBundle();
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => String(url).endsWith("/2026.json")
      ? Response.json(bundle) : new Response(null, { status: 404 });
    const { getCalendar } = await loadModule("data");
    const filters = { ...empty, followed_leagues: ["IFSC_WORLD_CUP", "IWF_WORLDS"],
      climbing: { genders: ["Women"], disciplines: ["Boulder"] }, weightlifting: { genders: ["Women"] } };
    const expected = bundle.events.filter((e) => (e.league === "IWF_WORLDS" && e.tags.includes("Women"))
      || (e.league === "IFSC_WORLD_CUP" && e.tags.includes("Boulder") && !e.tags.includes("Men")));
    const calendar = await getCalendar("month", 2026, "2026-10-01", filters, "UTC");
    const ids = new Set(calendar.groups.flatMap((day) => day.items.map((e) => e.event_id)));
    assert.deepEqual([...ids].sort(), expected.filter((e) => e.calendar_date.startsWith("2026-10")).map((e) => e.event_id).sort());
  } finally { globalThis.fetch = original; }
});
