import assert from "node:assert/strict";
import test from "node:test";
import { readFile, mkdir, mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const bundle = JSON.parse(await readFile(new URL("../../data/published/2026.json", import.meta.url), "utf8"));
const script = await readFile(new URL("../../scripts/prepare-web.mjs", import.meta.url));

for (const [name, mutate, message] of [
  ["unreviewed source", (b) => { b.events[0].source = "unreviewed"; }, /Unreviewed public data source/],
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
    const root = await mkdtemp(join(tmpdir(), "sportsbro-publish-test-"));
    try {
      await mkdir(join(root, "scripts"));
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
