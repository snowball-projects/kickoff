import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const state = await loadModule("month-feed-state");
test("month windows cross years, stay bounded, and preserve overlap for reanchoring", () => {
  const december = state.monthWindow("2026-12-01");
  assert.deepEqual(december, ["2026-08-01", "2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", "2027-03-01", "2027-04-01"]);
  assert.equal(state.shouldRecenter(december, "2026-12-01"), false);
  assert.equal(state.shouldRecenter(december, "2027-03-01"), true);
  const next = state.monthWindow("2027-03-01");
  assert.ok(next.includes("2027-03-01"));
  assert.equal(next.length, 9);
  for (let index = state.monthIndex(state.FIRST_MONTH); index <= state.monthIndex(state.LAST_MONTH); index += 7) {
    const months = state.monthWindow(state.monthAt(index));
    assert.equal(months.length, 9);
    assert.equal(new Set(months).size, 9);
    assert.ok(months[0] >= state.FIRST_MONTH);
    assert.ok(months.at(-1) <= state.LAST_MONTH);
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
