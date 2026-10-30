import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { clockMinute, dayTimeline, isAllDay, initialMinute, hourLabel, HOUR_HEIGHT, PILL_HEIGHT, DAY_HEIGHT } = await loadModule("day-timeline");
const event = (id, fields = {}) => ({
  event_id: id, source: "fixture", season: "2026", status: "scheduled", competition_phase: "regular_season",
  league: "NFL", sport: "football", event_type: "game", title: id, calendar_date: "2026-09-10",
  start_time_utc: "2026-09-10T17:30:00Z", start_time_local: null, participants: [], tags: [], ...fields,
});

test("wall-clock slots preserve DST gaps, repeats, midnight and viewer dates", () => {
  for (const [instant, minute] of [["2026-03-08T07:30:00Z", 90], ["2026-03-08T08:30:00Z", 210],
    ["2026-11-01T06:30:00Z", 90], ["2026-11-01T07:30:00Z", 90]])
    assert.equal(clockMinute(Date.parse(instant), "America/Chicago"), minute);
  assert.equal(clockMinute(Date.parse("2026-12-31T23:30:00Z"), "Asia/Tokyo"), 510);
  assert.equal(DAY_HEIGHT, HOUR_HEIGHT * 24);
  assert.deepEqual([hourLabel(0), hourLabel(12), hourLabel(24)], ["12am", "12pm", "12am"]);
});
test("unverified clocks and inclusive multi-day events stay all-day", () => {
  for (const fields of [ { start_time_utc: null }, { start_time_utc: null, start_time_local: "2026-09-10T12:30:00" },
    { end_calendar_date: "2026-09-11" }, { calendar_date: "2026-09-11", start_calendar_date: "2026-09-10", end_calendar_date: "2026-09-11" } ]) assert(isAllDay(event("all", fields)));
  assert(!isAllDay(event("timed", { end_calendar_date: "2026-09-10" })));
  assert.equal(dayTimeline([event("known"), event("unknown", { start_time_utc: null })], "UTC").allDay[0].items[0].event_id, "unknown");
});
test("nearby starts keep their minute positions with at most three non-overlapping lanes", () => {
  const items = Array.from({ length: 12 }, (_, index) => event(String(index), {
    start_time_utc: `2026-09-10T17:${String(30 + index * 2).padStart(2, "0")}:00Z`,
  }));
  const { slots } = dayTimeline(items, "UTC");
  assert.deepEqual(slots.flatMap((slot) => slot.items).map((e) => e.event_id).sort(), items.map((e) => e.event_id).sort());
  assert(slots.some((slot) => slot.overflow));
  for (const slot of slots) {
    assert(slot.columns <= 3 && slot.lane < 3);
    assert.equal(slot.top, clockMinute(Date.parse(slot.items[0].start_time_utc), "UTC") * HOUR_HEIGHT / 60);
    assert(slots.every((other) => other === slot || other.lane !== slot.lane
      || other.top >= slot.top + PILL_HEIGHT || slot.top >= other.top + PILL_HEIGHT));
  }
});
test("today starts at now and other dates at the first known start or midnight", () => {
  const now = Date.parse("2026-09-10T17:30:00Z");
  assert.equal(initialMinute("2026-09-10", "America/Chicago", 100, now), 750);
  assert.equal(initialMinute("2026-09-11", "America/Chicago", 100, now), 100);
  assert.equal(initialMinute("2026-09-11", "America/Chicago", undefined, now), 0);
});
