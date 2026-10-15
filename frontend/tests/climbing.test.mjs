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
  const speed = sessions.find((e) => e.title.includes("Speed finals"));
  assert.equal(dates.eventTimeBucket(speed, "America/Santiago"), "18:00");
  assert.equal(dates.eventTimeBucket(speed, "UTC"), "21:00");
  assert.equal(dates.eventCalendarDate(speed, "Asia/Tokyo"), "2026-10-25");
});

test("disputed climbing clocks remain Time TBD on their source dates in every zone", () => {
  const unknown = sessions.filter((e) => !e.start_time_utc);
  assert.equal(unknown.length, 4);
  for (const event of unknown) {
    for (const zone of ["UTC", "America/Denver", "America/Santiago", "Asia/Tokyo"]) {
      assert.equal(dates.eventCalendarDate(event, zone), event.calendar_date);
      assert.equal(dates.eventTimeLabel(event, zone), "Time TBD");
    }
    assert.match(event.subtitle, /Time withheld:/);
    assert.ok(event.tags.some((t) => ["Boulder", "Lead", "Speed"].includes(t)));
  }
});
