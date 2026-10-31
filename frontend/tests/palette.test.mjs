import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadModule } from "./load-module.mjs";
import { contrast, simulatedContrast, paletteReport, readPalette, simulations, simulate, lab, pairwise } from "./palette-audit.mjs";

test("every named category has its own family colour", async () => {
  const { CATEGORY_KEYS, categoryForLeague, leagueVisual } = await loadModule("calendar-helpers");
  const palette = (await readPalette()).filter((entry) => entry.base);
  assert.equal(palette.length, Object.values(CATEGORY_KEYS).length);
  assert.equal(new Set(palette.map((entry) => entry.base)).size, palette.length);
  assert.deepEqual(palette.map((entry) => entry.key).sort(), Object.values(CATEGORY_KEYS).sort());
  for (const sport of ["Cycling", "Athletics", "Cricket"]) assert(CATEGORY_KEYS[sport]);
  for (const key of Object.values(CATEGORY_KEYS)) assert(palette.some((entry) => entry.key === key));
  for (const league of ["F1", "NASCAR_CUP", "INDYCAR"])
    assert.equal(leagueVisual(league).className, "category-motorsport");
  for (const league of ["EPL", "LA_LIGA", "CHAMPIONSHIP", "UEFA_CHAMPIONS_LEAGUE", "FIFA_WORLD_CUP"])
    assert.equal(leagueVisual(league).className, "category-soccer");
  for (const league of ["PGA_TOUR", "LPGA_TOUR", "DP_WORLD_TOUR", "LIV_GOLF"])
    assert.equal(leagueVisual(league).className, "category-golf");
  assert.equal(categoryForLeague("FUTURE_SERIES", "motorsport"), "motorsport");
  assert.equal(leagueVisual("FUTURE_LEAGUE", "soccer").className, "category-soccer");
  assert.equal(categoryForLeague("FUTURE_CLIMBING_EVENT", "climbing"), "climbing");
  assert.equal(categoryForLeague("FUTURE_WEIGHTLIFTING_EVENT", "weightlifting"), "weightlifting");
  assert.equal(categoryForLeague("NEW_SPORT"), null);
  assert.equal(leagueVisual("NEW_SPORT").className, "category-unknown");
  const css = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
  assert(!/\.league-(?!label\b)[\w-]+\s*\{/.test(css), "per-league colour rules must not return");
});

test("category ink meets WCAG AA on the shared light/dark sport fills", async () => {
  assert.equal(contrast("#ffffff", "#000000"), 21);
  assert.equal(contrast("#ffffff", "#ffffff"), 1);
  for (const row of (await paletteReport()).contrast) for (const [mode, ratio] of Object.entries(row)) {
    if (mode !== "key") assert(ratio >= 4.5, `${row.key} ${mode}: ${ratio}`);
  }
  // Neutral fallback is deliberately separate from known sport families.
  const neutral = (await readPalette()).find((entry) => entry.key === "unknown");
  for (const mode of ["light", "dark"]) assert(contrast(neutral[`${mode}-bg`], neutral[`${mode}-ink`]) >= 4.5);
});

test("all chip-fill pairs retain distance in protan/deutan/tritan simulations in both themes", async () => {
  assert(Math.abs(lab(simulate("#ffffff", simulations.normal))[0] - 100) < .001);
  const palette = (await readPalette()).filter((entry) => entry.base);
  for (const mode of ["light", "dark"]) for (const [name, matrix] of Object.entries(simulations)) {
    const pairs = pairwise(palette, mode, matrix);
    assert.equal(pairs.length, palette.length * (palette.length - 1) / 2);
    // Diagnostic guard against regressions, not an accessibility pass/fail standard.
    assert(pairs[0].distance >= 20, `${mode} ${name}: ${JSON.stringify(pairs[0])}`);
  }
});

// Check text as well as swatch differences under the same simulations.
test("chip text retains contrast in common colour-vision simulations", async () => {
  const palette = (await readPalette()).filter((entry) => entry.base);
  for (const entry of palette) for (const mode of ["light", "dark"]) for (const [name, matrix] of Object.entries(simulations))
    assert(simulatedContrast(entry[`${mode}-bg`], entry[`${mode}-ink`], matrix) >= 4.5, `${entry.key} ${mode} ${name}`);
});
