import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { boundMonth, scheduleWindow, dayAfter, dayInMonth } = await loadModule("month-feed-state");

test("rolling bounds clamp leap days, cross years and include both endpoints", () => {
  assert.deepEqual(scheduleWindow("2028-02-29"), { start: "2027-02-28", end: "2029-02-28" });
  assert.deepEqual(scheduleWindow("2026-12-31"), { start: "2025-12-31", end: "2027-12-31" });
  assert.equal(boundMonth("2020-01-01", "2026-12-31"), "2025-12-01");
  assert.equal(boundMonth("2030-01-01", "2026-12-31"), "2027-12-01");
  assert.equal(dayAfter("2026-12-31", 1), "2027-01-01");
  assert.equal(dayAfter("2028-03-01", -1), "2028-02-29");
  assert.equal(dayInMonth("2026-01-31", 1), "2026-02-28");
});
