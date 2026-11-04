import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { clockMinute, currentMinute, dayOverflow, dayTimeline, isAllDay, initialMinute, hourLabel, HOUR_HEIGHT, PILL_HEIGHT, DAY_HEIGHT } = await loadModule("day-timeline");
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
test("the current-time marker uses the viewer's date and wall clock across midnight and DST", () => {
  for (const [instant, zone, date, minute] of [
    ["2026-12-31T23:59:00Z", "UTC", "2026-12-31", 1439],
    ["2027-01-01T00:00:00Z", "UTC", "2027-01-01", 0],
    ["2026-12-31T23:30:00Z", "Asia/Kathmandu", "2027-01-01", 315],
    ["2027-01-01T00:30:00Z", "America/Los_Angeles", "2026-12-31", 990],
    ["2026-03-08T07:59:00Z", "America/Chicago", "2026-03-08", 119],
    ["2026-03-08T08:00:00Z", "America/Chicago", "2026-03-08", 180],
    ["2026-11-01T06:59:00Z", "America/Chicago", "2026-11-01", 119],
    ["2026-11-01T07:00:00Z", "America/Chicago", "2026-11-01", 60],
  ]) {
    assert.equal(currentMinute(date, zone, Date.parse(instant)), minute);
    assert.equal(currentMinute("2026-09-10", zone, Date.parse(instant)), null);
  }
});

test("two overlaps remain visible and three or more reserve the third lane for overflow", () => {
  for (const count of [2, 3, 4]) {
    const items = Array.from({ length: count }, (_, index) => event(`same-${index}`));
    const { slots } = dayTimeline(items, "UTC");
    assert.equal(slots.filter((slot) => !slot.overflow).length, 2);
    const overflow = slots.filter((slot) => slot.overflow);
    assert.equal(overflow.length, count > 2 ? 1 : 0);
    if (count > 2) assert.equal(overflow[0].items.length, count - 2);
    assert.deepEqual(slots.flatMap((slot) => slot.items).map((item) => item.event_id).sort(), items.map((item) => item.event_id).sort());
    for (const slot of slots) assert.equal(slot.top, 17.5 * HOUR_HEIGHT);
  }
});


test("measured overflow keeps every event exactly once and prefers the existing same-clock control", () => {
  for (const count of [1, 2, 3, 4]) {
    const items = Array.from({ length: count }, (_, index) => event(`same-${index}`));
    const { slots } = dayTimeline(items, "UTC");
    const original = structuredClone(slots);
    for (let mask = 0; mask < 2 ** Math.min(2, count); mask++) {
      const unreadable = new Set(items.slice(0, 2).filter((_, index) => mask & 2 ** index).map(item => item.event_id));
      const shown = dayOverflow(slots, unreadable);
      assert.deepEqual(shown.flatMap(slot => slot.items).map(item => item.event_id).sort(), items.map(item => item.event_id).sort());
      assert.equal(shown.filter(slot => slot.overflow).length, count > 2 || mask ? 1 : 0);
      assert(shown.filter(slot => !slot.overflow).length <= 2);
      for (const slot of shown) {
        assert.equal(slot.top, 17.5 * HOUR_HEIGHT);
        assert.equal(slot.columns, Math.min(count, 3));
      }
      if (count > 2) assert.equal(shown.find(slot => slot.overflow).lane, 2);
    }
    assert.deepEqual(slots, original, "fallback does not mutate measurement geometry or source arrays");
  }
});
test("fallback controls preserve nearby clocks, baseline lanes and repeated DST source instants", () => {
  const items = [event("first"), event("nearby", { start_time_utc: "2026-09-10T17:40:00Z" })];
  const baseline = dayTimeline(items, "UTC").slots;
  const shown = dayOverflow(baseline, new Set(items.map(item => item.event_id)));
  assert.deepEqual(shown.map(slot => [slot.top, slot.lane, slot.columns]), baseline.map(slot => [slot.top, slot.lane, slot.columns]));
  assert(shown.every(slot => slot.overflow && slot.items.length === 1));
  const repeated = [event("early", { start_time_utc: "2026-11-01T06:30:00Z" }), event("late", { start_time_utc: "2026-11-01T07:30:00Z" })];
  const dst = dayOverflow(dayTimeline(repeated, "America/Chicago").slots, new Set(["early", "late"]));
  assert.equal(dst.length, 1);
  assert.equal(dst[0].top, 1.5 * HOUR_HEIGHT);
  assert.deepEqual(dst[0].items.map(item => item.start_time_utc), repeated.map(item => item.start_time_utc));
});


test("overflow priority never moves a later postseason game ahead of its anchored clock", () => {
  const items = [event("a"), event("b"), event("c"), event("later-postseason", {
    start_time_utc: "2026-09-10T17:40:00Z", competition_phase: "postseason",
  })];
  const baseline = dayTimeline(items, "UTC").slots;
  assert.deepEqual(dayOverflow(baseline, new Set()), baseline);
  const more = dayOverflow(baseline, new Set(["a", "b"])).find(slot => slot.overflow);
  assert.deepEqual(more.items.map(item => item.event_id), ["a", "b", "c", "later-postseason"]);
  assert.equal(more.top, 17.5 * HOUR_HEIGHT);
});
