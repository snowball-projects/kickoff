import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("timezone placement, multi-day dates, multiple interests, and motorsport choices agree", async () => {
  const original = globalThis.fetch;
  try {
    const { getCalendar, searchEvents } = await loadModule("data");
    const base = {
      source: "test",
      sport: "soccer",
      league: "EPL",
      title: "Fixture",
      subtitle: null,
      country: "England",
      city: null,
      venue: null,
      participants: [],
      tags: [],
      calendar_date: "2026-09-12",
      end_calendar_date: "2026-09-12",
      competition_phase: "regular_season",
      start_time_utc: null,
    };
    globalThis.fetch = async () =>
      Response.json({
        schema_version: "1",
        season: 2026,
        available_seasons: [2026],
        providers: [],
        events: [
          { ...base, event_id: "late", start_time_utc: "2026-09-12T01:00:00Z" },
          {
            ...base,
            event_id: "multi",
            league: "IFSC",
            end_calendar_date: "2026-09-14",
          },
          {
            ...base,
            event_id: "race",
            league: "F1",
            sport: "motorsport",
            event_type: "race",
          },
          {
            ...base,
            event_id: "qualifying",
            league: "F1",
            sport: "motorsport",
            event_type: "qualifying",
          },
        ],
      });
    const filters = {
      sport: "",
      league: "",
      country: "",
      city: "",
      competition_phase: "",
      tags: [],
    };
    const month = await getCalendar(
      "month",
      2026,
      "2026-09-01",
      filters,
      "America/Chicago",
    );
    const on = (d) =>
      month.groups.find((g) => g.date === d).items.map((e) => e.event_id);
    assert.ok(on("2026-09-11").includes("late"));
    const late = month.groups.find((group) => group.date === "2026-09-11").items.find((event) => event.event_id === "late");
    assert.equal(late.start_calendar_date, "2026-09-11");
    assert.equal(late.end_calendar_date, "2026-09-11");
    assert.ok(!on("2026-09-12").includes("late"));
    for (const date of ["2026-09-12", "2026-09-13", "2026-09-14"])
      assert.ok(on(date).includes("multi"));
    assert.equal(month.groups.find((group) => group.date === "2026-09-14").items.find((event) => event.event_id === "multi").start_calendar_date, "2026-09-12");
    assert.ok(!on("2026-09-15").includes("multi"));
    const only = await getCalendar(
      "month",
      2026,
      "2026-09-01",
      {
        ...filters,
        followed_leagues: ["EPL", "F1"],
        motorsport_view: "race_only",
      },
      "America/Chicago",
    );
    assert.deepEqual(
      only.groups.flatMap((g) => g.items.map((e) => e.event_id)),
      ["late", "race"],
    );
    const all = await getCalendar(
      "month",
      2026,
      "2026-09-01",
      { ...filters, followed_leagues: ["F1"], motorsport_view: "full_weekend" },
      "UTC",
    );
    assert.equal(all.total_events, 2);
    const none = await getCalendar(
      "month",
      2026,
      "2026-09-01",
      { ...filters, followed_leagues: [] },
      "UTC",
    );
    assert.equal(none.total_events, 0);
    const found = await searchEvents(
      2026,
      "Fixture",
      { ...filters, followed_leagues: ["EPL"] },
      "America/Chicago",
    );
    assert.equal(found.items[0].calendar_date, "2026-09-11");
  } finally {
    globalThis.fetch = original;
  }
});
test("calendar navigation handles year boundaries and leap years", async () => {
  try {
    const { addMonths, monthGridSunStart, yearMonthAnchors } =
      await loadModule("date-utils");
    assert.equal(addMonths("2026-01-01", -1), "2025-12-01");
    assert.equal(addMonths("2026-12-01", 1), "2027-01-01");
    assert.equal(
      monthGridSunStart("2028-02-01", [], { showAdjacentDays: false }).filter(
        (d) => d.inMonth,
      ).length,
      29,
    );
    assert.equal(yearMonthAnchors(2026).length, 12);
  } finally {
  }
});
