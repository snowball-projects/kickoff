import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { startList } = await loadModule("weightlifting-startlist");

test("start-list totals sort descending, preserve ties deterministically and keep all source entries", () => {
  const entries = [{ name: "Zulu", entity_type: "athlete", entry_total_kg: 180 },
    { name: "Alpha", entity_type: "athlete", entry_total_kg: 180 },
    { name: "Highest", entity_type: "athlete", entry_total_kg: 250 },
    { name: "No source total", entity_type: "athlete" },
    { name: "Team", entity_type: "team", entry_total_kg: 999 }];
  const before = structuredClone(entries);
  assert.deepEqual(startList(entries).map(entry => entry.name), ["Highest", "Alpha", "Zulu"]);
  assert.deepEqual(entries, before);
  const many = Array.from({ length: 24 }, (_, i) => ({ name: String(i), entity_type: "athlete", entry_total_kg: i + 1 }));
  assert.equal(startList(many).length, 24);
});
