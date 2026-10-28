import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const { clockMinute, dayTimeline, isAllDay, initialMinute, timelineLanes, visibleSlot, hourLabel, HOUR_HEIGHT, PILL_HEIGHT, DAY_HEIGHT } = await loadModule("day-timeline");
const event = (id, fields = {}) => ({
  event_id: id, source: "fixture", season: "2026", status: "scheduled", competition_phase: "regular_season",
  league: "NFL", sport: "football", event_type: "game", title: id, calendar_date: "2026-09-10",
  start_time_utc: "2026-09-10T17:30:00Z", start_time_local: null, participants: [], tags: [], ...fields,
});

test("minute positions are wall clocks in the viewer's timezone, including DST gaps and repeats", () => {
  for (const [instant, minute] of [["2026-03-08T07:30:00Z", 90], ["2026-03-08T08:30:00Z", 210],
    ["2026-11-01T06:30:00Z", 90], ["2026-11-01T07:30:00Z", 90]]) {
    assert.equal(clockMinute(Date.parse(instant), "America/Chicago"), minute);
  }
  assert.equal(clockMinute(Date.parse("2026-12-31T23:30:00Z"), "Asia/Tokyo"), 510);
  assert.equal(clockMinute(Date.parse("2026-09-10T00:00:00Z"), "UTC"), 0);
  assert.equal(DAY_HEIGHT, HOUR_HEIGHT * 24);
  assert.deepEqual(Array.from({ length: 25 }, (_, index) => hourLabel(index)),
    ["12am", "1am", "2am", "3am", "4am", "5am", "6am", "7am", "8am", "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm", "6pm", "7pm", "8pm", "9pm", "10pm", "11pm", "12am"]);
});

test("all-day, multi-day, final-date and unverified wall clocks never acquire timeline times", () => {
  for (const fields of [
    { start_time_utc: null }, { start_time_utc: null, start_time_local: "2026-09-10T12:30:00" },
    { end_calendar_date: "2026-09-11" }, { calendar_date: "2026-09-11", start_calendar_date: "2026-09-10", end_calendar_date: "2026-09-11" },
    { tags: ["final date only"] },
  ]) assert.equal(isAllDay(event("all", fields)), true);
  assert.equal(isAllDay(event("timed", { end_calendar_date: "2026-09-10" })), false);
  const groups = dayTimeline([event("timed"), event("untimed", { start_time_utc: null }), event("golf", { sport: "golf", league: "PGA_TOUR", event_type: "tournament", end_calendar_date: "2026-09-13" })], "UTC");
  assert.equal(groups.allDay.length, 2);
  assert.deepEqual(groups.timed[0].times.map((slot) => slot.minute), [1050]);
});

test("competition identities match month grouping and only visible events enter groups", () => {
  const items = [event("first"), event("same"), event("later", { start_time_utc: "2026-09-10T19:00:00Z" }),
    event("other", { league: "NBA", sport: "basketball" })];
  const { timed } = dayTimeline(items, "America/Chicago");
  assert.equal(timed.length, 2);
  const nfl = timed.find((group) => group.name === "NFL");
  assert.deepEqual(nfl.times.map((slot) => [slot.minute, slot.events.length]), [[750, 2], [840, 1]]);
  const { timed: filtered } = dayTimeline(items.slice(0, 1), "America/Chicago");
  assert.equal(filtered[0].items.length, 1);
});

test("lanes avoid visual overlaps and expansion preserves all vertical positions", () => {
  const { timed } = dayTimeline([event("one"), event("later", { start_time_utc: "2026-09-10T19:00:00Z" }),
    event("other", { league: "NBA", sport: "basketball", start_time_utc: "2026-09-10T18:15:00Z" })], "UTC");
  const collapsed = timelineLanes(timed, new Set()).groups;
  const expanded = timelineLanes(timed, new Set(timed.map((group) => group.key))).groups;
  assert.deepEqual(collapsed.map((entry) => entry.top), expanded.map((entry) => entry.top));
  assert.ok(collapsed.every((entry) => entry.end - entry.top === PILL_HEIGHT));
  assert.ok(expanded.every((entry) => entry.columns === 1));
  assert.ok(expanded.every((entry) => entry.slots.every((slot) => slot.columns === 1)));
});

test("same-minute slots keep at most three controls and expose the exact overflow", () => {
  for (const count of [1, 2, 3, 4, 13]) {
    const items = Array.from({ length: count }, (_, index) => event(String(index)));
    const { shown, more } = visibleSlot(items);
    assert.ok(shown.length + Number(!!more.length) <= 3);
    assert.deepEqual([...shown, ...more], items);
    if (count > 3) assert.equal(more.length, count - 2);
  }
});

test("opening today uses now, another day uses its first event or midnight", () => {
  const now = Date.parse("2026-09-10T17:30:00Z");
  assert.equal(initialMinute("2026-09-10", "America/Chicago", 100, now), 750);
  assert.equal(initialMinute("2026-09-11", "America/Chicago", 100, now), 100);
  assert.equal(initialMinute("2026-09-11", "America/Chicago", undefined, now), 0);
  assert.equal(initialMinute("2026-09-11", "Asia/Tokyo", 100, now), 150);
});


test("nearby starts use separate lanes without displacing their true minute positions", () => {
  const { timed } = dayTimeline([event("first"), event("second", { start_time_utc: "2026-09-10T17:45:00Z" })], "UTC");
  const slots = timelineLanes(timed, new Set([timed[0].key])).groups[0].slots;
  assert.deepEqual(slots.map((slot) => slot.top), [0, 20]);
  assert.deepEqual(slots.map((slot) => slot.columns), [2, 2]);
  assert.notEqual(slots[0].lane, slots[1].lane);
});


test("DST inversion anchors the group to its first chronological start, with children at their own clocks", () => {
  const { timed } = dayTimeline([event("first", { start_time_utc: "2026-11-01T06:45:00Z" }),
    event("later", { start_time_utc: "2026-11-01T07:15:00Z" })], "America/Chicago");
  assert.equal(timed[0].minute, 105);
  assert.equal(timed[0].items[0].event_id, "first");
  assert.equal(timelineLanes(timed, new Set()).groups[0].top, 140);
  const open = timelineLanes(timed, new Set([timed[0].key])).groups[0];
  assert.equal(open.top, 100);
  assert.equal(open.headerTop, 40);
  assert.deepEqual(open.slots.map((slot) => [slot.minute, slot.top]), [[75, 0], [105, 40]]);
});

test("unrelated competitions sharing a start use a flat overflow list instead of four columns", () => {
  const { timed } = dayTimeline(["NFL", "NBA", "MLB", "NHL"].map((league) => event(league, { league })), "UTC");
  const layout = timelineLanes(timed, new Set());
  assert.equal(layout.overflow.length, 1);
  assert.equal(layout.overflow[0].value.events.length, 4);
  assert.equal(layout.overflow[0].columns, 1);
  assert.ok(layout.groups.every((group) => !group.header));
});
