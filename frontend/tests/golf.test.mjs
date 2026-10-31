import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { readLeaderboard, golfRound, leaderboardId } = await loadModule("golf");
const fixture = JSON.parse(readFileSync(new URL("./fixtures/golf-leaderboard.json", import.meta.url), "utf8")).payloads;

test("the trimmed ESPN fixture sorts competitors, preserves ties and extracts the current round score", () => {
  const original = JSON.stringify(fixture.live);
  const board = readLeaderboard(fixture.live, "401850978", "America/Chicago", false);
  assert.equal(board.final, false);
  assert.equal(board.inProgress, true);
  assert.equal(board.round, 2);
  assert.deepEqual(board.players.map((p) => p.name), ["Mackenzie Hughes", "Jackson Suber", "Matthieu Pavon", "Adrien Dumont de Chassart", "Kensei Hirata"]);
  assert.deepEqual(board.players[0], { id: "6931", name: "Mackenzie Hughes", position: "T1", total: "-6", today: "-2", thru: "12" });
  assert.equal(JSON.stringify(fixture.live), original);
});

test("LPGA pre-start tee times use the viewer's zone; a completed round does not poll overnight", () => {
  const board = readLeaderboard(fixture.between_rounds, "401835174", "America/Chicago", false);
  assert.equal(board.final, false);
  assert.equal(board.inProgress, false);
  assert.equal(board.players[0].name, "Miyu Yamashita");
  assert.equal(board.players[0].today, "8:27 PM");
  assert.equal(board.players[0].thru, "0");
  assert.equal(readLeaderboard(fixture.between_rounds, "401835174", "Asia/Tokyo", false).players[0].today, "10:27 AM");
});

test("past days receive final tournament results and never an ongoing tournament snapshot", () => {
  assert.equal(readLeaderboard(fixture.live, "401850978", "UTC", true), null);
  assert.equal(readLeaderboard(fixture.between_rounds, "401835174", "UTC", true), null);
  const board = readLeaderboard(fixture.final, "401835149", "UTC", true);
  assert.equal(board.final, true);
  assert.equal(board.inProgress, false);
  assert.equal(board.round, 4);
  assert.equal(board.players[0].name, "Nelly Korda");
  assert.equal(board.players[0].today, "-2");
  assert.equal(board.players[0].thru, "18");
  assert.equal(readLeaderboard(fixture.final, "wrong-event", "UTC", true), null);
  assert.equal(readLeaderboard({}, "401835149", "UTC", true), null);
});

test("only ESPN golf IDs create leaderboard requests", () => {
  const event = { sport: "golf", source: "espn", event_id: "espn-lpga_tour-401835149" };
  assert.equal(leaderboardId(event), "401835149");
  for (const patch of [{ sport: "soccer" }, { source: "wikipedia" }, { event_id: "unknown" }])
    assert.equal(leaderboardId({ ...event, ...patch }), undefined);
});

test("round cards use one calendar day, including short events, DST, year boundaries and a Monday finish", async () => {
  const { eventTimeLabel, eventInstant } = await loadModule("date-utils");
  const { pillGroups } = await loadModule("calendar-helpers");
  const base = { event_id: "golf", title: "Tournament", sport: "golf", league: "PGA_TOUR", competition_phase: "regular_season",
    source_url: "https://www.espn.com/golf/leaderboard?tournamentId=1", start_time_utc: "2026-10-28T18:00Z" };
  for (const [start, end, n] of [["2026-05-29", "2026-05-31", 3], ["2026-06-25", "2026-06-29", 5], ["2026-10-30", "2026-11-02", 4], ["2026-12-30", "2027-01-02", 4]]) {
    const card = golfRound(base, end, start);
    assert.equal(card.title, `Tournament, Round ${n}`);
    assert.equal(card.calendar_date, end);
    assert.equal(card.start_calendar_date, end);
    assert.equal(card.end_calendar_date, end);
    assert.equal(card.source_url, base.source_url);
    assert.equal(eventInstant(card), null);
    assert.equal(eventTimeLabel(card, "America/Chicago"), "");
  }
  assert.equal(pillGroups([base, { ...base, event_id: "other", title: "Other tournament" }]).length, 2);
});

test("the calendar expands golf spans into daily round cards before every view", async () => {
  const original = globalThis.fetch;
  try {
    const raw = { event_id: "espn-pga_tour-1", title: "Tournament", event_type: "tournament", sport: "golf", league: "PGA_TOUR", source: "espn",
      calendar_date: "2026-10-29", end_calendar_date: "2026-11-02", start_time_utc: null, start_time_local: null, tags: [], competition_phase: "regular_season" };
    globalThis.fetch = async (url) => url.endsWith("/2026.json") ? Response.json({ schema_version: "1", season: 2026, available_seasons: [2026], events: [raw] }) : new Response(null, { status: 404 });
    const { getCalendar } = await loadModule("data");
    const filters = { sport: "", league: "", country: "", city: "", competition_phase: "", tags: [] };
    const calendar = await getCalendar("month", 2026, "2026-10-01", filters, "Pacific/Honolulu");
    const november = await getCalendar("month", 2026, "2026-11-01", filters, "Pacific/Honolulu");
    const cards = [...calendar.groups, ...november.groups].flatMap((g) => g.items);
    assert.deepEqual(cards.map((e) => e.title), [1, 2, 3, 4, 5].map((n) => `Tournament, Round ${n}`));
    assert.deepEqual(cards.map((e) => e.calendar_date), ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]);
    assert(cards.every((e) => e.calendar_date === e.start_calendar_date && e.calendar_date === e.end_calendar_date));
    assert.equal(raw.title, "Tournament");
  } finally { globalThis.fetch = original; }
});
