import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
import { reviewedBundle } from "./reviewed-fixture.mjs";

const dates = await loadModule("date-utils");
const bundle = reviewedBundle();
const sessions = bundle.events.filter((event) => event.source === "weightlifting");

test("Ningbo session clocks convert across visitor dates and DST", () => {
  const first = sessions.find((event) => event.league === "IWF_WORLDS" && event.calendar_date === "2026-10-27");
  assert.equal(dates.eventCalendarDate(first, "Asia/Shanghai"), "2026-10-27");
  assert.equal(dates.eventTimeBucket(first, "Asia/Shanghai"), "11:00");
  assert.equal(dates.eventCalendarDate(first, "America/Chicago"), "2026-10-26");
  assert.equal(dates.eventTimeBucket(first, "America/Chicago"), "22:00");
  const november = sessions.find((event) => event.league === "IWF_WORLDS" && event.calendar_date === "2026-11-02");
  assert.equal(dates.eventCalendarDate(november, "America/Chicago"), "2026-11-01");
  assert.equal(dates.eventTimeBucket(november, "America/Chicago"), "21:00");
});

test("combined sessions stay single events, parallel Masters platforms stay separate", () => {
  const shared = sessions.filter((event) => event.league === "IWF_WORLDS" && event.calendar_date === "2026-10-29" && event.start_time_utc === "2026-10-29T03:00:00Z");
  assert.equal(shared.length, 1);
  assert.match(shared[0].title, /53 kg, Group D \/ Women's 57 kg, Group B/);
  const masters = sessions.filter((event) => event.league === "MASTERS_WORLDS" && event.start_time_utc === "2026-09-17T06:00:00Z");
  assert.equal(masters.length, 3);
  assert.equal(new Set(masters.map((event) => event.title.split("Platform ")[1])).size, 3);
});
