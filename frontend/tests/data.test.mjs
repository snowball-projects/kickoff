import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("a transient schedule failure can be retried without reloading the page", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const { getManifest } = await loadModule("data");
    let attempts = 0;
    globalThis.fetch = async () => {
      attempts += 1;
      if (attempts === 1) return new Response("unavailable", { status: 503 });
      return Response.json({
        schema_version: "1",
        season: 2026,
        events: [],
        providers: [],
        available_seasons: [2026],
      });
    };
    await assert.rejects(getManifest(2026), /unavailable/);
    const manifest = await getManifest(2026);
    assert.equal(manifest.season, 2026);
    assert.equal(manifest.all_events, 0);
    await getManifest(2026);
    assert.equal(attempts, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
