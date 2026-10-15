import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const bundle = JSON.parse(await readFile(new URL("../../data/published/2026.json", import.meta.url), "utf8"));
const sessions = bundle.events.filter((event) => event.source === "world_climbing");
const dates = await loadModule("date-utils");

test("climbing finals cross midnight only when the display zone requires it", () => {
  const final = sessions.find((e) => e.title === "Salt Lake City — Men's Boulder final");
  assert.equal(dates.eventCalendarDate(final, "America/Denver"), "2026-10-17");
  assert.equal(dates.eventCalendarDate(final, "UTC"), "2026-10-18");
  assert.equal(dates.eventTimeBucket(final, "America/Denver"), "19:00");
  assert.equal(dates.eventTimeBucket(final, "UTC"), "01:00");
  const speed = sessions.find((e) => e.title.includes("Speed final"));
  assert.equal(dates.eventTimeBucket(speed, "America/Santiago"), "18:00");
  assert.equal(dates.eventTimeBucket(speed, "UTC"), "21:00");
  assert.equal(dates.eventCalendarDate(speed, "Asia/Tokyo"), "2026-10-25");
});

test("disputed climbing clocks remain Time TBD on their source dates in every zone", () => {
  const unknown = sessions.filter((e) => !e.start_time_utc);
  assert.equal(unknown.length, 5);
  for (const event of unknown) {
    for (const zone of ["UTC", "America/Denver", "America/Santiago", "Asia/Tokyo"]) {
      assert.equal(dates.eventCalendarDate(event, zone), event.calendar_date);
      assert.equal(dates.eventTimeLabel(event, zone), "Time TBD");
    }
    assert.match(event.subtitle, /Time withheld:/);
    assert.ok(event.tags.some((t) => ["Boulder", "Lead", "Speed"].includes(t)));
  }
});


test("shared starts label both gender rounds without claiming individual clocks", () => {
  const shared = sessions.filter((e) => e.start_time_scope === "shared_session");
  assert.equal(sessions.length, 16);
  assert.equal(shared.length, 4);
  for (const event of shared) {
    assert.match(dates.eventTimeLabel(event, "UTC"), /^Session starts /);
    assert.match(event.subtitle, /individual start time is not separately published/);
    assert.ok(event.tags.includes("Men") || event.tags.includes("Women"));
    assert.ok(!event.title.includes(" & "));
  }
  assert.deepEqual(shared.filter((e) => e.title.includes("Speed")).map((e) => e.title).sort(), [
    "Santiago — Men's Speed final", "Santiago — Women's Speed final",
  ]);
  assert.equal(sessions.filter((e) => e.title.includes("Speed") && e.round_or_stage === "semi-final").length, 0);
});
