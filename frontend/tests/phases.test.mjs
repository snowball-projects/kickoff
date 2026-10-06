import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

test("published playoff and exhibition events remain visible through the Phase filter", async () => {
  const bundle = JSON.parse(await readFile(new URL("../../data/published/2026.json", import.meta.url), "utf8"));
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => String(url).endsWith("/2026.json")
      ? Response.json(bundle) : new Response(null, { status: 404 });
    const { searchEvents } = await loadModule("data");
    const filters = { sport: "", league: "", country: "", city: "", competition_phase: "postseason", tags: [] };
    const nascar = await searchEvents(2026, "", { ...filters, league: "NASCAR_CUP" }, "UTC");
    const pga = await searchEvents(2026, "", { ...filters, league: "PGA_TOUR" }, "UTC");
    const allStar = await searchEvents(2026, "All Star", {
      ...filters, league: "NASCAR_CUP", competition_phase: "exhibition",
    }, "UTC");
    assert.equal(nascar.total, 10);
    assert.equal(pga.total, 3);
    assert.equal(allStar.total, 1);
    assert.ok([...nascar.items, ...pga.items].every((event) => event.is_postseason));
    assert.ok(allStar.items[0].is_exhibition);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
