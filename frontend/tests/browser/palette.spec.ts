import { expect, test, type Locator } from "@playwright/test";
import { contrast, readPalette, simulate, simulations } from "../palette-audit.mjs";

const categories = [
  ["EPL", "soccer", "soccer"], ["F1", "motorsport", "motorsport"],
  ["NFL", "football", "american-football"], ["NBA", "basketball", "basketball"],
  ["MLB", "baseball", "baseball"], ["NHL", "hockey", "hockey"],
  ["UFC", "combat", "combat"], ["PGA_TOUR", "golf", "golf"],
  ["IFSC_WORLD_CUP", "climbing", "climbing"], ["IWF_WORLDS", "weightlifting", "weightlifting"],
];
const events = [...categories, ["FUTURE_SERIES", "motorsport", "motorsport"]].map(([league, sport], i) => ({
  league, sport, event_id: `palette-${i}`, title: `${league} fixture`, source: "offline-browser-fixture",
  season: "2026", event_type: sport === "motorsport" ? "race" : "match", subtitle: null,
  calendar_date: "2026-09-10", end_calendar_date: "2026-09-10", start_time_utc: null, start_time_local: null,
  timezone: null, status: "scheduled", venue: null, city: null, region: null, country: null,
  round_or_stage: null, competition_phase: "regular_season", tags: [], participants: [],
  home_participant: null, away_participant: null, home_participant_name: null, away_participant_name: null,
  week_label: null, is_regular_season: true, is_postseason: false, is_exhibition: false, is_support_event: false,
}));
const hex = (rgb: string) => "#" + rgb.match(/[\d.]+/g)!.slice(0, 3).map((part) => Number(part).toString(16).padStart(2, "0")).join("");

for (const theme of ["light", "dark"] as const) for (const width of [1280, 390, 320]) {
  test(`${theme} ${width}px: family colours, text, controls and focus survive calendar/list/interests`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
    await page.setViewportSize({ width, height: 844 });
    await page.clock.setFixedTime(new Date("2026-09-10T17:00:00Z"));
    await page.addInitScript((leagues) => localStorage.setItem("kickoff.interests.v2", JSON.stringify({
      leagues, golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" }, motorsport_view: "race_only",
    })), events.map((event) => event.league));
    await page.route("**/data/*.json", (route) => route.request().url().endsWith("/2026.json")
      ? route.fulfill({ json: { schema_version: "1", season: 2026, available_seasons: [2026], providers: [], events } })
      : route.fulfill({ status: 404, body: "No published schedule" }));
    await page.goto("/");
    const day = page.locator("#day-2026-09-10");
    await expect(day.locator(".event-pill")).toHaveCount(11);
    const palette = await readPalette();
    async function expectSportFill(element: Locator, category: string) {
      const token = palette.find((entry: { key: string }) => entry.key === category)!;
      const colors = await element.evaluate((node) => {
        const style = getComputedStyle(node); return [style.backgroundColor, style.color];
      });
      expect(hex(colors[0])).toBe(token[`${theme}-bg`]);
      expect(hex(colors[1])).toBe(token[`${theme}-ink`]);
      expect(contrast(hex(colors[0]), hex(colors[1]))).toBeGreaterThanOrEqual(4.5);
    }
    for (const [, , category] of categories) {
      const pill = day.locator(`.event-pill.category-${category}`).first();
      await expect(pill).toHaveText(/fixture/);
      await expectSportFill(pill, category);
    }
    const motorsport = await day.locator(".category-motorsport").evaluateAll((elements) => elements.map((element) => getComputedStyle(element).backgroundColor));
    expect(motorsport.length).toBe(2);
    expect(new Set(motorsport).size).toBe(1);
    await day.focus();
    const focus = await day.evaluate((element) => {
      const style = getComputedStyle(element); return [style.outlineColor, style.backgroundColor];
    });
    expect(contrast(hex(focus[0]), hex(focus[1]))).toBeGreaterThanOrEqual(3);
    await page.screenshot({ path: `test-results/palette-month-${theme}-${width}.png` });
    await day.click();
    await expect(page.getByRole("complementary", { name: "Day events" })).toBeVisible();
    for (const [, , category] of categories)
      await expectSportFill(page.locator(`.day-inspector .timeline-pill.category-${category}`).first(), category);
    await page.locator('.day-inspector [data-event-id="palette-0"]').click();
    await expectSportFill(page.locator(".day-inspector .league-label.category-soccer"), "soccer");
    await page.screenshot({ path: `test-results/palette-day-${theme}-${width}.png` });
    await page.getByRole("button", { name: "Close day", exact: true }).click();
    await page.getByRole("button", { name: /^Interests ·/ }).click();
    const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
    const button = chooser.getByRole("button", { name: "Show my calendar" });
    const controls = await button.evaluate((element) => {
      const style = getComputedStyle(element); return [style.color, style.backgroundColor];
    });
    expect(contrast(hex(controls[0]), hex(controls[1]))).toBeGreaterThanOrEqual(4.5);
    const tokens = await chooser.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return Object.fromEntries(["text", "muted", "green", "page", "surface", "hover", "control", "control-line", "focus", "chosen-bg", "soft", "day-hover", "selected", "primary-hover", "on-green"].map((key) => [key, style.getPropertyValue(`--${key}`).trim()]));
    });
    for (const background of ["page", "surface", "hover", "chosen-bg", "control", "soft", "day-hover", "selected"]) {
      for (const foreground of ["text", "muted", "green"]) expect(contrast(tokens[foreground], tokens[background]), `${theme} ${foreground}/${background}`).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tokens.focus, tokens[background])).toBeGreaterThanOrEqual(3);
    }
    expect(contrast(tokens["control-line"], tokens.control)).toBeGreaterThanOrEqual(3);
    expect(contrast(tokens["on-green"], tokens["primary-hover"])).toBeGreaterThanOrEqual(4.5);
    const motorsports = chooser.getByRole("region", { name: "Motorsports interests" });
    await motorsports.locator("summary").click();
    const future = motorsports.getByRole("checkbox", { name: "FUTURE SERIES", exact: true });
    await expect(future).toBeChecked();
    const futureSwatch = motorsports.locator("label.interest").filter({ has: page.getByRole("checkbox", { name: "FUTURE SERIES", exact: true }) }).locator(".interest-swatch");
    await expect(futureSwatch).toHaveClass(/category-motorsport/);
    await expect(chooser.getByRole("region", { name: "Miscellaneous interests" })).toHaveCount(0);
    const futureColor = await futureSwatch.evaluate((element) => getComputedStyle(element).backgroundColor);
    expect(hex(futureColor)).toBe(palette.find((entry: { key: string }) => entry.key === "motorsport")![`${theme}-bg`]);
    await expect(chooser.locator("summary .sport-chip")).toHaveCount(10);
    for (const [, , category] of categories) {
      const chip = chooser.locator(`summary .sport-chip.category-${category}`);
      await expectSportFill(chip, category);
      const summaryInk = await chip.locator("..").evaluate((element) => getComputedStyle(element).color);
      expect(hex(summaryInk)).toBe(tokens.text);
      const group = chip.locator("../..");
      if (category !== "motorsport") await group.locator("summary").click();
      const swatches = group.locator(".interest-swatch");
      if (category === "soccer") {
        const league = group.locator("label.interest").filter({ has: page.getByRole("img", { name: "England", exact: true }) });
        await expect(league.locator(".interest-swatch.category-soccer")).toBeVisible();
        await expect(league.getByRole("img", { name: "England", exact: true })).toBeVisible();
        expect(await league.locator("span").last().evaluate((element) =>
          element.getBoundingClientRect().height <= parseFloat(getComputedStyle(element).fontSize) * 1.5)).toBe(true);
        await page.screenshot({ path: `test-results/palette-soccer-interests-${theme}-${width}.png` });
      }
      expect(await swatches.count()).toBeGreaterThan(0);
      for (const swatch of await swatches.all()) {
        const style = await swatch.evaluate((element) => {
          const css = getComputedStyle(element);
          return [css.backgroundColor, css.width, css.height, css.borderRadius];
        });
        expect(hex(style[0])).toBe(palette.find((entry: { key: string }) => entry.key === category)![`${theme}-bg`]);
        expect(style.slice(1)).toEqual(["12px", "12px", "3px"]);
      }
    }
    await page.screenshot({ path: `test-results/palette-interests-${theme}-${width}.png` });
    expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await button.click();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!).leagues)).toContain("FUTURE_SERIES");
    await page.getByRole("button", { name: "Agenda", exact: true }).click();
    const rows = page.locator(".agenda-row");
    await expect(rows).toHaveCount(11);
    await rows.filter({ hasText: "F1 fixture" }).hover();
    const previewChip = page.getByRole("tooltip").locator(".sport-chip");
    await expect(previewChip).toBeVisible();
    await expectSportFill(previewChip, "motorsport");
    await page.keyboard.press("Escape");
    for (const [, , category] of categories)
      await expectSportFill(rows.locator(`.league-label.category-${category}`).first(), category);
    const f1Row = rows.filter({ hasText: "F1 fixture" });
    await f1Row.focus();
    await page.keyboard.press("Tab");
    await page.keyboard.press("Shift+Tab");
    await expect(f1Row).toBeFocused();
    await expect(previewChip).toBeVisible();
    await expectSportFill(previewChip, "motorsport");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/palette-list-${theme}-${width}.png` });
  });
}

test("palette swatches retain visible labels in normal/protan/deutan/tritan simulations", async ({ page }) => {
  const palette = (await readPalette()).filter((entry: { base?: string }) => entry.base);
  const srgb = (value: number) => value <= .0031308 ? value * 12.92 : 1.055 * value ** (1 / 2.4) - .055;
  const simulatedHex = (color: string, matrix: number[][]) => "#" + simulate(color, matrix).map((value: number) => Math.round(srgb(value) * 255).toString(16).padStart(2, "0")).join("");
  await page.setViewportSize({ width: 1440, height: 920 });
  await page.setContent(`<style>body{margin:0;font:13px system-ui}.mode{padding:14px}.row{display:grid;grid-template-columns:repeat(12,1fr);gap:5px}.swatch{padding:14px 6px;min-height:75px;border-radius:5px}h2{font-size:16px;margin:0 0 9px}small{display:block;margin-top:6px}</style>` + ["light", "dark"].map((mode) => `<div class="mode" style="background:${mode === "light" ? "#fafbf7" : "#131c25"};color:${mode === "light" ? "#243b32" : "#e8eef0"}">${Object.entries(simulations).map(([name, matrix]) => `<h2>${mode} · ${name}</h2><div class="row">${palette.map((entry: Record<string, string>) => `<div class="swatch" style="background:${simulatedHex(entry[`${mode}-bg`], matrix as number[][])};color:${simulatedHex(entry[`${mode}-ink`], matrix as number[][])}">${entry.key}<small>${entry.base}</small></div>`).join("")}</div>`).join("")}</div>`).join(""));
  await page.screenshot({ path: "test-results/palette-simulations.png", fullPage: true });
});
