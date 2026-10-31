import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

const { sessionLevel, matchesInterestOptions, allPreferences, CLIMBING_LEVELS, WEIGHTLIFTING_LEVELS } = await loadModule("interest-preferences");
const directory = resolve(process.env.KICKOFF_PUBLISHED_DATA || new URL("../public/data", import.meta.url).pathname);

const files = await readdir(directory);
const manifest = files.includes("manifest.json")
  ? JSON.parse(await readFile(resolve(directory, "manifest.json"), "utf8")) : null;

async function publishedSessions(year, sport) {
  if (!manifest) {
    const bundle = JSON.parse(await readFile(resolve(directory, `${year}.json`), "utf8"));
    return bundle.events.filter((event) => event.sport === sport);
  }
  const entry = manifest.seasons[String(year)].sports.find((entry) => entry.value === sport);
  assert.ok(entry, `${year} ${sport}: manifest entry required`);
  const bundle = JSON.parse(await readFile(resolve(directory, entry.file), "utf8"));
  assert.equal(bundle.events.length, entry.count, `${year} ${sport}: complete manifest coverage`);
  assert.ok(bundle.events.every((event) => event.sport === sport));
  return bundle.events;
}

for (const year of [2026, 2027]) test(`every published ${year} climbing and weightlifting record matches exactly one level`, async (t) => {
  const counts = {};
  for (const [sport, levels] of [["climbing", CLIMBING_LEVELS], ["weightlifting", WEIGHTLIFTING_LEVELS]]) {
    const records = await publishedSessions(year, sport);
    assert.ok(records.length > 0, `${year} ${sport}: published records required`);
    counts[sport] = {};
    for (const event of records) {
      const original = JSON.stringify(event);
      const preferences = allPreferences([event.league]);
      const matches = levels.filter((level) => matchesInterestOptions(event, { [sport]: { ...preferences[sport], levels: [level] } }));
      assert.deepEqual(matches, [sessionLevel(event)], event.event_id);
      counts[sport][matches[0]] = (counts[sport][matches[0]] || 0) + 1;
      assert.equal(JSON.stringify(event), original, `${event.event_id}: source facts unchanged`);
    }
    assert.equal(Object.values(counts[sport]).reduce((sum, count) => sum + count, 0), records.length);
  }
  t.diagnostic(JSON.stringify({ year, counts }));
});
