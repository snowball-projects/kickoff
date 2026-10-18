import assert from "node:assert/strict";
import test from "node:test";
import { readFile, mkdir, mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const bundle = JSON.parse(await readFile(new URL("../../data/published/2026.json", import.meta.url), "utf8"));
const schema = await readFile(new URL("../src/bundle-schema.ts", import.meta.url));
const script = await readFile(new URL("../../scripts/prepare-web.mjs", import.meta.url));

for (const [name, mutate, message] of [
  ...[
    ["missing title", (e) => { delete e.title; }, /invalid title/],
    ["missing date", (e) => { delete e.calendar_date; }, /invalid calendar_date/],
    ["impossible date", (e) => { e.calendar_date = "2026-02-30"; }, /invalid calendar_date/],
    ["reversed span", (e) => { e.end_calendar_date = "2025-01-01"; }, /invalid end_calendar_date/],
    ["missing tags", (e) => { delete e.tags; }, /invalid tags/],
    ["non-string tag", (e) => { e.tags = [123]; }, /invalid tags/],
    ["missing participants", (e) => { delete e.participants; }, /invalid participants/],
    ["malformed participant", (e) => { e.participants = [{}]; }, /invalid participants/],
    ["naive timestamp", (e) => { e.start_time_utc = "2026-10-17T19:00:00"; }, /invalid start_time_utc/],
  ].map(([name, mutateEvent, message]) => [name, (b) => mutateEvent(b.events[0]), message]),
  ["wrong bundle season", (b) => { b.season = 2027; b.available_seasons = [2027]; }, /filename and season differ/],
  ["non-array sources", (b) => { b.sources = {}; }, /missing publication metadata/],
  ["unreviewed source", (b) => { b.events[0].source = "unreviewed"; }, /Unreviewed public data source/],
  ["unreviewed official climbing stop", (b) => { b.events.find((e) => e.source === "world_climbing").source_url = "https://www.worldclimbing.com/events/unreviewed"; }, /Unreviewed official climbing source/],
  ["invented climbing discipline", (b) => { b.events.find((e) => e.source === "world_climbing").tags = ["session", "invalid"]; }, /Invalid official climbing session/],
  ["invalid shared clock scope", (b) => { b.events.find((e) => e.source === "world_climbing").start_time_scope = "guessed"; }, /shared session clock scope/],
  ["missing climbing gender", (b) => { const e = b.events.find((e) => e.source === "world_climbing"); e.tags = e.tags.filter((t) => !["Men", "Women"].includes(t)); }, /Invalid climbing gender or stage/],
  ["invented clock", (b) => { b.events.find((e) => e.source === "wikidata").start_time_utc = "2026-10-27T00:00:00Z"; }, /unsupported clock semantics/],
  ["Wikidata prose labeled CC0", (b) => {
    const event = b.events.find((e) => e.source === "wikidata");
    const notice = b.sources.find((s) => s.url === event.source_url);
    const url = new URL(event.source_url);
    url.searchParams.set("title", "Wikidata:Licensing");
    event.source_url = notice.url = url.href;
  }, /Unreviewed Wikimedia article\/entity namespace/],
]) {
  test(`public build rejects ${name}`, async () => {
    const root = await mkdtemp(join(tmpdir(), "kickoff-publish-test-"));
    try {
      await mkdir(join(root, "scripts"));
      await mkdir(join(root, "frontend/src"), { recursive: true });
      await writeFile(join(root, "frontend/src/bundle-schema.ts"), schema);
      await mkdir(join(root, "data/published"), { recursive: true });
      await writeFile(join(root, "scripts/prepare-web.mjs"), script);
      const candidate = structuredClone(bundle);
      mutate(candidate);
      await writeFile(join(root, "data/published/2026.json"), JSON.stringify(candidate));
      const result = spawnSync(process.execPath, [join(root, "scripts/prepare-web.mjs")], { encoding: "utf8" });
      assert.notEqual(result.status, 0);
      assert.match(result.stderr, message);
    } finally { await rm(root, { recursive: true, force: true }); }
  });
}
