import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const empty = { sport: "", league: "", country: "", city: "", competition_phase: "", tags: [] };
const storage = (values) => ({ getItem: (key) => values[key] || null });

test("legacy majors migrate per tour, deduplicate interests and retain unrelated and empty selections", async () => {
  const { migrateInterests, readPreferences, INTERESTS_KEY, LEGACY_INTERESTS_KEY } = await loadModule("interest-preferences");
  const migrated = migrateInterests(["GOLF_MAJORS_MEN", "LPGA_TOUR", "GOLF_MAJORS_WOMEN", "F1", "FUTURE"]);
  assert.deepEqual(migrated.leagues, ["PGA_TOUR", "LPGA_TOUR", "F1", "FUTURE"]);
  assert.deepEqual(migrated.golf_views, { PGA_TOUR: "majors_only", LPGA_TOUR: "full_tour" });
  assert.equal(migrated.motorsport_view, "race_only");
  assert.deepEqual(migrateInterests([]).leagues, []);
  assert.equal(readPreferences(storage({})).leagues, null);
  assert.equal(readPreferences(storage({ [LEGACY_INTERESTS_KEY]: "bad json" })).leagues, null);
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: "broken", [LEGACY_INTERESTS_KEY]: '["NFL"]' })).leagues, ["NFL"]);
  const saved = { ...migrated, motorsport_view: "full_weekend" };
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify(saved),
    [LEGACY_INTERESTS_KEY]: '["NFL"]' })), saved);
  assert.deepEqual(readPreferences(storage({ [LEGACY_INTERESTS_KEY]: '["GOLF_MAJORS_WOMEN"]' })).golf_views,
    { PGA_TOUR: "full_tour", LPGA_TOUR: "majors_only" });
});

test("golf interests expose only tours even when a year publishes only majors", async () => {
  const { interestGroups, leagueVisual } = await loadModule("calendar-helpers");
  assert.deepEqual(interestGroups(["GOLF_MAJORS_MEN", "GOLF_MAJORS_WOMEN", "LPGA_TOUR"]
    .map((value) => ({ value }))), [{ name: "Golf", leagues: ["PGA_TOUR", "LPGA_TOUR"] }]);
  assert.equal(leagueVisual("BOXING_MAJOR").shortLabel, "Boxing");
  assert.equal(leagueVisual("ONE").shortLabel, "One");
});

test("golf modes apply equally to search and calendar with no duplicate majors or football leakage", async () => {
  const bundle = JSON.parse(await readFile(new URL("../../data/published/2026.json", import.meta.url), "utf8"));
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => String(url).endsWith("/2026.json")
      ? Response.json(bundle) : new Response(null, { status: 404 });
    const { searchEvents, getCalendar } = await loadModule("data");
    const filters = { ...empty, followed_leagues: ["PGA_TOUR", "LPGA_TOUR"],
      golf_views: { PGA_TOUR: "majors_only", LPGA_TOUR: "majors_only" } };
    const majors = await searchEvents(2026, "", filters, "UTC");
    assert.equal(majors.total, 9);
    assert.equal(majors.items.filter((e) => e.league === "PGA_TOUR").length, 4);
    assert.equal(majors.items.filter((e) => e.league === "GOLF_MAJORS_WOMEN").length, 5);
    const calendar = await getCalendar("month", 2026, "2026-04-01", filters, "UTC");
    assert.equal(calendar.groups.find((group) => group.date === "2026-04-09").items.length, 1);
    assert.equal((await searchEvents(2026, "Sony", filters, "UTC")).total, 0);
    const full = { ...filters, golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" } };
    assert.equal((await searchEvents(2026, "", full, "UTC")).total, 79);
    assert.equal((await searchEvents(2026, "Masters Tournament", full, "UTC")).total, 1);
    assert.equal((await searchEvents(2026, "Walmart", full, "UTC")).items[0].tags.includes("final date only"), true);
    // Underlying league and phase filtering remains usable outside the chooser.
    assert.equal((await searchEvents(2026, "", { ...empty, league: "GOLF_MAJORS_MEN" }, "UTC")).total, 4);
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
