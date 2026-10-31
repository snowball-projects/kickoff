import assert from "node:assert/strict";
import { reviewedBundle } from "./reviewed-fixture.mjs";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const bundle = reviewedBundle();
const records = bundle.events.filter((event) => event.source === "world_climbing");
const dates = await loadModule("date-utils");
const byId = (id) => records.find((event) => event.event_id === id);

test("official climbing rounds cross midnight only when the viewer zone requires it", () => {
  const final = byId("world-climbing-series-2026-salt-lake-city-boulder-mens-final");
  assert.equal(dates.eventCalendarDate(final, "America/Denver"), "2026-10-17");
  assert.equal(dates.eventCalendarDate(final, "Europe/London"), "2026-10-18");
  const speed = byId("world-climbing-series-2026-santiago-speed-mens-final");
  assert.equal(dates.eventCalendarDate(speed, "Asia/Tokyo"), "2026-10-25");
});

test("unknown climbing clocks retain their reviewed dates in every zone", () => {
  const unknown = records.filter((event) => !event.start_time_utc);
  assert.ok(unknown.length > 0);
  for (const event of unknown) {
    for (const zone of ["UTC", "America/Denver", "America/Santiago", "Europe/London", "Asia/Tokyo"]) {
      assert.equal(dates.eventCalendarDate(event, zone), event.calendar_date);
      assert.equal(dates.eventTimeLabel(event, zone), "");
    }
    assert.equal(event.subtitle, null);
    assert.ok(event.tags.some((tag) => ["Boulder", "Lead", "Speed"].includes(tag)));
  }
});

test("shared blocks stay explicit and resolved Santiago clocks become exact instants", () => {
  const shared = records.filter((event) => event.start_time_scope === "shared_session");
  assert.ok(shared.length > 0);
  for (const event of shared) {
    assert.match(dates.eventTimeLabel(event, "UTC"), /^Session starts /);
    assert.ok(event.start_time_utc);
    assert.equal(event.subtitle, null);
  }
  for (const gender of ["men", "women"]) {
    const final = byId(`world-climbing-series-2026-santiago-speed-${gender}s-final`);
    assert.equal(final.start_time_scope, "shared_session");
  }
});
