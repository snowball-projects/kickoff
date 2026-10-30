import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("agenda windows follow local dates across years, leap days and DST", async () => {
  const { agendaDates, agendaAnchors } = await loadModule("agenda-state");
  assert.deepEqual(agendaDates("2027-01-01", "yesterday"), ["2026-12-31"]);
  assert.deepEqual(agendaDates("2026-12-31", "today"), ["2026-12-31"]);
  assert.deepEqual(agendaDates("2026-12-31", "upcoming"), [
    "2027-01-01", "2027-01-02", "2027-01-03", "2027-01-04", "2027-01-05", "2027-01-06", "2027-01-07",
  ]);
  assert.deepEqual(agendaAnchors("2026-12-31"), ["2026-12-01", "2027-01-01"]);
  assert.deepEqual(agendaDates("2028-03-01", "yesterday"), ["2028-02-29"]);
  assert.equal(agendaDates("2026-03-07", "upcoming").at(-1), "2026-03-14");
  assert.equal(agendaDates("2026-10-31", "upcoming").at(-1), "2026-11-07");
});

test("agenda uses the calendar's timezone, span and filter semantics; unknown clocks sort last", async () => {
  const { getCalendar } = await loadModule("data");
  const { agendaGroups, agendaScopeLabel } = await loadModule("agenda-state");
  const original = globalThis.fetch;
  const base = { status: "scheduled", season: "2026", competition_phase: "regular_season", title: "Fixture", event_type: "game", source: "fixture", sport: "soccer", league: "EPL", tags: [], participants: [],
    calendar_date: "2026-12-31", start_time_utc: null, start_time_local: null };
  try {
    globalThis.fetch = async (url) => url.endsWith("/2026.json") ? Response.json({
      schema_version: "1", season: 2026, available_seasons: [2026], providers: [], events: [
        { ...base, event_id: "date-only" },
        { ...base, event_id: "late", start_time_utc: "2026-12-31T23:00:00Z" },
        { ...base, event_id: "early", start_time_utc: "2026-12-31T18:00:00Z" },
        { ...base, event_id: "unverified", start_time_local: "2026-12-31T09:00:00" },
        { ...base, event_id: "span", calendar_date: "2026-12-30", end_calendar_date: "2027-01-02" },
        { ...base, event_id: "other-league", league: "NBA" },
      ],
    }) : new Response("missing", { status: 404 });
    const filters = { sport: "", league: "", country: "", city: "", competition_phase: "", tags: [], followed_leagues: ["EPL"] };
    const december = await getCalendar("month", 2026, "2026-12-01", filters, "Asia/Tokyo");
    const january = await getCalendar("month", 2027, "2027-01-01", filters, "Asia/Tokyo");
    const groups = agendaGroups({ "2026-12-01": december, "2027-01-01": january }, ["2026-12-31", "2027-01-01"]);
    assert.deepEqual(groups[0].items.map((event) => event.event_id), ["date-only", "span", "unverified"]);
    assert.deepEqual(groups[1].items.map((event) => event.event_id), ["early", "late", "span"]);
    assert.equal(agendaScopeLabel(groups[0].items[1], "2026-12-31"), "Through Jan 2");
    assert.equal(agendaScopeLabel({ ...base, end_calendar_date: "2026-12-31" }, "2026-12-31"), "");
    assert.deepEqual(agendaGroups({}, ["2026-12-31"]), [{ date: "2026-12-31", items: [] }]);
  } finally { globalThis.fetch = original; }
});

test("view preference safely defaults to calendar", async () => {
  const { readScheduleView } = await loadModule("agenda-state");
  for (const value of [null, "", "year", "corrupt", "calendar"]) assert.equal(readScheduleView({ getItem: () => value }), "calendar");
  assert.equal(readScheduleView({ getItem: () => "agenda" }), "agenda");
  assert.equal(readScheduleView({ getItem: () => { throw Error("blocked"); } }), "calendar");
});

test("Show more is bounded by published years and advances through occupied dates", async () => {
  const { laterAgendaAnchors, nextAgendaEnd, agendaDates } = await loadModule("agenda-state");
  const anchors = laterAgendaAnchors("2026-12-31", [2029, 2026, 2029]);
  assert.equal(anchors.length, 2);
  assert.equal(anchors[0], "2026-12-01");
  assert.equal(anchors.at(-1), "2027-01-01");
  assert.deepEqual(anchors.filter((anchor) => anchor.startsWith("2027")), ["2027-01-01"]);
  assert.equal(anchors.some((anchor) => anchor.startsWith("2028")), false);
  const dates = ["2027-01-08", "2027-01-09", "2027-01-10", "2027-01-11", "2027-01-12", "2027-01-13", "2027-01-14", "2029-02-10"];
  const months = { fixture: { groups: dates.map((date) => ({ date, items: [{ event_id: date }] })) } };
  assert.equal(nextAgendaEnd(months, "2027-01-07", "2027-12-31"), "2027-01-14");
  assert.equal(nextAgendaEnd(months, "2027-01-14", "2027-12-31"), null);
  assert.equal(nextAgendaEnd(months, "2029-02-10", "2027-12-31"), null);
  assert.equal(nextAgendaEnd({ fixture: { groups: [{ date: "2030-01-01", items: [] }] } }, "2027-01-07", "2027-12-31"), null);
  assert.equal(agendaDates("2026-12-31", "upcoming", "2027-01-14").at(-1), "2027-01-14");
});

test("Show more includes the rolling endpoint and excludes later dates in the same month", async () => {
  const { laterAgendaAnchors, nextAgendaEnd } = await loadModule("agenda-state");
  const anchors = laterAgendaAnchors("2026-10-27", [2025, 2026, 2027, 2028]);
  assert.equal(anchors.at(-1), "2027-10-01");
  const months = { fixture: { groups: ["2027-10-27", "2027-10-28"].map((date) => ({ date, items: [{}] })) } };
  assert.equal(nextAgendaEnd(months, "2027-10-26", "2027-10-27"), "2027-10-27");
  assert.equal(nextAgendaEnd(months, "2027-10-27", "2027-10-27"), null);
});
