import assert from "node:assert/strict";
import { reviewedBundle } from "./reviewed-fixture.mjs";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
import { publishedFiles } from "./published-fixture.mjs";

const empty = { sport: "", league: "", country: "", city: "", competition_phase: "", tags: [] };
const storage = (values) => ({ getItem: (key) => values[key] || null });

test("new preferences start empty, ignore the old key and save explicit option choices", async () => {
  const { readPreferences, defaultPreferences, allPreferences, INTERESTS_KEY } = await loadModule("interest-preferences");
  assert.equal(INTERESTS_KEY, "kickoff.interests.v3");
  assert.deepEqual(readPreferences(storage({})), defaultPreferences());
  assert.deepEqual(readPreferences(storage({ "kickoff.interests.v2": JSON.stringify({ leagues: ["NFL"] }) })), defaultPreferences());
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: "broken" })), defaultPreferences());
  assert.deepEqual(defaultPreferences(), { leagues: [], motorsport_events: [], climbing: { genders: [], disciplines: [] }, weightlifting: { genders: [] } });
  const saved = { ...allPreferences(["PGA_TOUR", "F1", "IFSC_WORLD_CUP"]), motorsport_events: ["qualifying", "race"], climbing: { genders: ["Women"], disciplines: ["Lead"] } };
  assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify(saved) })), saved);
});

test("wrong-shaped current preferences fall back to empty selections without migration", async () => {
  const { readPreferences, defaultPreferences, allPreferences, INTERESTS_KEY } = await loadModule("interest-preferences");
  const valid = allPreferences(["F1"]);
  for (const value of [true, "saved", [], {}, { leagues: null }, { leagues: ["F1"] },
    { ...valid, leagues: "F1" }, { ...valid, leagues: [1] }, { ...valid, motorsport_events: null },
    { ...valid, climbing: {} }, { ...valid, climbing: { genders: ["Men"], disciplines: null } },
    { ...valid, weightlifting: null }, { ...valid, weightlifting: { genders: [false] } }])
    assert.deepEqual(readPreferences(storage({ [INTERESTS_KEY]: JSON.stringify(value) })), defaultPreferences());
});

test("motorsport options match each event type exactly, including sprint qualifying", async () => {
  const { matchesInterestOptions, MOTORSPORT_EVENTS } = await loadModule("interest-preferences");
  for (const selected of [...MOTORSPORT_EVENTS.map((type) => [type]), [], [...MOTORSPORT_EVENTS]]) {
    for (const event_type of MOTORSPORT_EVENTS) {
      assert.equal(matchesInterestOptions({ sport: "motorsport", league: "F1", event_type }, { motorsport_events: selected }), selected.includes(event_type));
    }
    assert.equal(matchesInterestOptions({ sport: "motorsport", league: "F1", title: "Sprint qualifying", event_type: "qualifying" }, { motorsport_events: selected }), selected.includes("qualifying"));
    for (const league of ["INDYCAR", "NASCAR_CUP"])
      assert.equal(matchesInterestOptions({ sport: "motorsport", league, event_type: "race" }, { motorsport_events: selected }), selected.includes("race"));
  }
  assert.equal(matchesInterestOptions({ sport: "soccer", league: "EPL" }, { motorsport_events: [] }), true);
});

test("golf tours include regular events and majors; league choices remain independent", async () => {
  const { matchesInterestOptions } = await loadModule("interest-preferences");
  for (const league of ["PGA_TOUR", "LPGA_TOUR"]) for (const competition_phase of ["championship", "regular_season"]) {
    assert.equal(matchesInterestOptions({ sport: "golf", league, competition_phase }, { followed_leagues: [league] }), true);
    assert.equal(matchesInterestOptions({ sport: "golf", league, competition_phase }, { followed_leagues: [] }), false);
  }
});

test("gender and discipline intersect, combined sessions match either, and unknowns remain visible", async () => {
  const { matchesInterestOptions } = await loadModule("interest-preferences");
  const filters = { climbing: { genders: ["Women"], disciplines: ["Lead"] }, weightlifting: { genders: ["Men"] } };
  const climbing = (tags) => ({ sport: "climbing", league: "IFSC_WORLD_CUP", tags });
  assert.equal(matchesInterestOptions(climbing(["Women", "Boulder", "Lead"]), filters), true);
  assert.equal(matchesInterestOptions(climbing(["Women", "Boulder"]), filters), false);
  assert.equal(matchesInterestOptions(climbing(["Men", "Lead"]), filters), false);
  assert.equal(matchesInterestOptions(climbing(["Men", "Women", "Lead"]), filters), true);
  assert.equal(matchesInterestOptions(climbing(["Lead"]), filters), true);
  assert.equal(matchesInterestOptions(climbing(["Women"]), filters), true);
  assert.equal(matchesInterestOptions(climbing([]), filters), true);
  assert.equal(matchesInterestOptions(climbing([]), { climbing: { genders: [], disciplines: ["Lead"] } }), false);
  assert.equal(matchesInterestOptions(climbing([]), { climbing: { genders: ["Women"], disciplines: [] } }), false);
  const lifting = (tags) => ({ sport: "weightlifting", league: "MASTERS_WORLDS", tags });
  assert.equal(matchesInterestOptions(lifting(["Men", "Women"]), filters), true);
  assert.equal(matchesInterestOptions(lifting(["Women"]), filters), false);
  assert.equal(matchesInterestOptions(lifting([]), filters), true);
  assert.equal(matchesInterestOptions(lifting([]), { weightlifting: { genders: [] } }), false);
  assert.equal(matchesInterestOptions({ sport: "soccer", league: "EPL", tags: [] }, filters), true);
});

test("reviewed session facets apply to the calendar without altering source records", async () => {
  const bundle = reviewedBundle();
  const original = globalThis.fetch;
  try {
    const files = publishedFiles([bundle]);
    globalThis.fetch = async (url) => files[url.split("/").at(-1)] ? Response.json(files[url.split("/").at(-1)]) : new Response(null, { status: 404 });
    const { getCalendar } = await loadModule("data");
    const filters = { ...empty, followed_leagues: ["IFSC_WORLD_CUP", "IWF_WORLDS"],
      climbing: { genders: ["Women"], disciplines: ["Boulder"] }, weightlifting: { genders: ["Women"] } };
    const expected = bundle.events.filter((e) => (e.league === "IWF_WORLDS" && e.tags.includes("Women"))
      || (e.league === "IFSC_WORLD_CUP" && e.tags.includes("Boulder") && !e.tags.includes("Men")));
    const calendar = await getCalendar("month", 2026, "2026-10-01", filters, "UTC");
    const ids = new Set(calendar.groups.flatMap((day) => day.items.map((e) => e.event_id)));
    assert.deepEqual([...ids].sort(), expected.filter((e) => e.calendar_date.startsWith("2026-10")).map((e) => e.event_id).sort());
  } finally { globalThis.fetch = original; }
});
