import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { boundMonth, scheduleWindow, dayAfter, dayInMonth, monthRows, weekStart } = await loadModule("month-feed-state");

test("rolling bounds clamp leap days, cross years and include both endpoints", () => {
  assert.deepEqual(scheduleWindow("2028-02-29"), { start: "2027-02-28", end: "2029-02-28" });
  assert.deepEqual(scheduleWindow("2026-12-31"), { start: "2025-12-31", end: "2027-12-31" });
  assert.equal(boundMonth("2020-01-01", "2026-12-31"), "2025-12-01");
  assert.equal(boundMonth("2030-01-01", "2026-12-31"), "2027-12-01");
  assert.equal(dayAfter("2026-12-31", 1), "2027-01-01");
  assert.equal(dayAfter("2028-03-01", -1), "2028-02-29");
  assert.equal(dayInMonth("2026-01-31", 1), "2026-02-28");
});


test("month boundaries split a Sunday-start week with null cells in weekday columns", () => {
  assert.deepEqual(monthRows("2026-09-27", "2026-10-03"), [
    ["2026-09-27", "2026-09-28", "2026-09-29", "2026-09-30", null, null, null],
    [null, null, null, null, "2026-10-01", "2026-10-02", "2026-10-03"],
  ]);
  assert.deepEqual(monthRows("2026-10-25", "2026-11-07"), [
    ["2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"],
    ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07"],
  ]);
});

test("bounded rows retain every civil date exactly once, including leap days and new years", () => {
  for (const [start, end] of [["2026-12-29", "2027-01-04"], ["2028-02-28", "2028-03-02"],
    ["2025-10-28", "2027-10-28"], ["2026-10-28", "2026-10-28"]]) {
    const rows = monthRows(start, end);
    const expected = [];
    for (let date = start; date <= end; date = dayAfter(date, 1)) expected.push(date);
    assert.deepEqual(rows.flat().filter(Boolean), expected);
    for (const row of rows) {
      assert.equal(row.length, 7);
      assert.equal(new Set(row.filter(Boolean).map((date) => date.slice(0, 7))).size, 1);
      row.forEach((date, column) => { if (date) assert.equal(dayAfter(weekStart(date), column), date); });
    }
  }
});
