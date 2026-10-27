import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const state = await loadModule("month-feed-state");
const today = "2026-10-27";
test("month windows cross years, stay bounded, and preserve overlap for reanchoring", () => {
  const december = state.monthWindow("2026-12-01", today);
  assert.deepEqual(december, ["2026-08-01", "2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", "2027-03-01", "2027-04-01"]);
  assert.equal(state.shouldRecenter(december, "2026-12-01", today), false);
  assert.equal(state.shouldRecenter(december, "2027-03-01", today), true);
  const next = state.monthWindow("2027-03-01", today);
  assert.ok(next.includes("2027-03-01"));
  assert.equal(next.length, 9);
  const bounds = state.scheduleWindow(today);
  for (let index = state.monthIndex(bounds.start); index <= state.monthIndex(bounds.end); index += 1) {
    const months = state.monthWindow(state.monthAt(index), today);
    assert.equal(months.length, 9);
    assert.equal(new Set(months).size, 9);
    assert.ok(months[0] >= "2025-10-01");
    assert.ok(months.at(-1) <= "2027-10-01");
    assert.equal(state.shouldRecenter(months, months[0], today), months[0] !== "2025-10-01");
    assert.equal(state.shouldRecenter(months, months.at(-1), today), months.at(-1) !== "2027-10-01");
  }
});
test("visible heading follows the viewport across variable-height months", () => {
  const sections = [
    { anchor: "2026-12-01", top: 0 },
    { anchor: "2027-01-01", top: 808 },
    { anchor: "2027-02-01", top: 1616 },
    { anchor: "2027-03-01", top: 2284 },
  ];
  assert.equal(state.visibleMonthAt(sections, 600, 600), "2026-12-01");
  assert.equal(state.visibleMonthAt(sections, 650, 600), "2027-01-01");
  assert.equal(state.visibleMonthAt(sections, 2165, 400), "2027-03-01");
  assert.equal(state.visibleMonthAt([], 0, 600), undefined);
});
test("day keyboard navigation crosses months and clamps leap-year page jumps", () => {
  assert.equal(state.dayAfter("2026-12-31", 1), "2027-01-01");
  assert.equal(state.dayAfter("2026-01-01", -1), "2025-12-31");
  assert.equal(state.dayAfter("2028-03-01", -1), "2028-02-29");
  assert.equal(state.dayInMonth("2028-01-31", 1), "2028-02-29");
  assert.equal(state.dayInMonth("2028-02-29", 12), "2029-02-28");
  assert.equal(state.dayInMonth("2026-12-31", 1), "2027-01-31");
});
test("explicit navigation respects reduced motion", () => {
  assert.equal(state.scrollBehavior(true), "auto");
  assert.equal(state.scrollBehavior(false), "smooth");
});

test("rolling windows use anniversaries and clamp leap days without UTC/DST shifts", () => {
  for (const [date, start, end] of [
    ["2026-10-27", "2025-10-27", "2027-10-27"],
    ["2027-01-01", "2026-01-01", "2028-01-01"],
    ["2028-02-29", "2027-02-28", "2029-02-28"],
    ["2026-03-08", "2025-03-08", "2027-03-08"],
  ]) {
    assert.deepEqual(state.scheduleWindow(date), { start, end });
    assert.equal(state.boundMonth("1900-01-01", date), `${start.slice(0, 7)}-01`);
    assert.equal(state.boundMonth("2100-12-01", date), `${end.slice(0, 7)}-01`);
  }
});
