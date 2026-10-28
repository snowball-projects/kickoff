import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const { monthCompetition, monthCompetitions, competitionSummary } = await loadModule("month-competitions");
const filters = { sport: "", league: "", competition_phase: "", country: "", city: "", tags: [] };
const event = (id, fields = {}) => ({
  event_id: id, source: "fixture", season: "2026", status: "scheduled", competition_phase: "regular_season",
  league: "NFL", sport: "football", event_type: "game", title: id, calendar_date: "2026-09-10",
  start_time_utc: null, start_time_local: null, participants: [], tags: [], ...fields,
});

test("competition groups use league identity and keep named meets/stops separate", () => {
  const one = event("one"), two = event("two", { source: "another-origin" });
  const lift = event("lift", { sport: "weightlifting", league: "IWF_WORLDS", event_type: "session", title: "World Championships · Men's 60 kg, Group A" });
  const liftB = { ...lift, event_id: "lift-b", title: "World Championships · Men's 60 kg, Group B" };
  const climb = event("climb", { sport: "climbing", league: "IFSC_WORLD_CUP", event_type: "session", title: "Santiago — Men's Lead final" });
  const climbElsewhere = { ...climb, event_id: "elsewhere", title: "Seoul — Women's Boulder final" };
  const grouped = monthCompetitions([one, two, lift, liftB, climb, climbElsewhere]);
  assert.deepEqual(grouped.map((group) => [group.name, group.items.length]), [["NFL", 2], ["World Championships", 2], ["Santiago", 1], ["Seoul", 1]]);
  const golf = event("golf", { sport: "golf", league: "PGA_TOUR", event_type: "tournament", title: "The Open" });
  assert.equal(monthCompetitions([golf, { ...golf, event_id: "other-golf", title: "Another tournament" }]).length, 2);
  assert.deepEqual(monthCompetitions([]), []);
  assert.equal(monthCompetitions([one])[0].items.length, 1);
});

test("summary uses the first known clock in the viewer zone, with no invented date-only clock", () => {
  const items = [event("tbd"), event("later", { start_time_utc: "2026-09-10T20:00:00Z" }), event("first", { start_time_utc: "2026-09-10T18:00:00Z" })];
  assert.equal(competitionSummary(items, "Europe/London"), "3 games · from 19:00");
  assert.equal(competitionSummary(items, "Asia/Tokyo"), "3 games · from 03:00");
  assert.equal(competitionSummary([items[0], event("other")], "UTC"), "2 games · Time TBD");
  assert.deepEqual(monthCompetitions(items)[0].items.map((item) => item.event_id), ["first", "later", "tbd"]);
});

test("month counts compare before interests, keep other filters and expose no hidden event details", async () => {
  const original = globalThis.fetch;
  try {
    const items = [
      event("race-a", { sport: "motorsport", league: "F1", event_type: "race", country: "Italy" }),
      event("race-b", { sport: "motorsport", league: "F1", event_type: "race", country: "Italy", start_time_utc: "2026-09-10T18:00:00Z" }),
      event("hidden-practice", { sport: "motorsport", league: "F1", event_type: "practice", country: "Italy" }),
      event("other-country", { sport: "motorsport", league: "F1", event_type: "practice", country: "USA" }),
      event("hidden-league", { league: "NBA", sport: "basketball", country: "Italy" }),
    ];
    globalThis.fetch = async () => Response.json({ schema_version: "1", season: 2026, events: items, providers: [], available_seasons: [2026] });
    const { getCalendar } = await loadModule("data");
    const selected = { ...filters, country: "Italy", followed_leagues: ["F1"], motorsport_view: "race_only" };
    const month = await getCalendar("month", 2026, "2026-09-01", selected, "UTC");
    const day = month.groups.find((group) => group.date === "2026-09-10");
    const groups = monthCompetitions(day.items, day.competition_counts);
    assert.equal(day.event_count, 2);
    assert.deepEqual(day.items.map((item) => item.event_id), ["race-a", "race-b"]);
    assert.deepEqual(day.competition_counts, { [monthCompetition(items[0]).key]: 3 });
    assert.equal(groups[0].hidden, 1);
    assert.equal(JSON.stringify(day).includes("hidden-practice"), false);
    assert.equal(JSON.stringify(day).includes("hidden-league"), false);
    const ungrouped = await getCalendar("day", 2026, "2026-09-10", selected, "UTC");
    assert.equal(ungrouped.groups[0].items.length, 2);
    assert.equal(ungrouped.groups[0].competition_counts, undefined);
    const none = await getCalendar("month", 2026, "2026-09-01", { ...selected, followed_leagues: [] }, "UTC");
    assert.ok(none.groups.every((group) => group.event_count === 0 && !Object.keys(group.competition_counts).length));
  } finally { globalThis.fetch = original; }
});

test("viewer-local days, adjacent years and inclusive date-only spans determine counts", async () => {
  const original = globalThis.fetch;
  try {
    const items = [event("late", { calendar_date: "2026-12-31", start_time_utc: "2026-12-31T23:30:00Z" }), event("date-only", { calendar_date: "2027-01-01", end_calendar_date: "2027-01-02" })];
    globalThis.fetch = async (url) => {
      const season = Number(url.match(/(\d{4})\.json/)[1]);
      return Response.json({ schema_version: "1", season, providers: [], available_seasons: [2026, 2027], events: season === 2026 ? [items[0]] : [items[1]] });
    };
    const { getCalendar } = await loadModule("data");
    const month = await getCalendar("month", 2027, "2027-01-01", filters, "Asia/Tokyo");
    for (const [date, count] of [["2027-01-01", 2], ["2027-01-02", 1]]) {
      const day = month.groups.find((group) => group.date === date);
      assert.equal(day.items.length, count);
      assert.equal(Object.values(day.competition_counts)[0], count);
    }
  } finally { globalThis.fetch = original; }
});
