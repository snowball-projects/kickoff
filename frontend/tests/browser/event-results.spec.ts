import { expect, test } from "./test";
import { agendaToggle, event, setup } from "./fixtures";

const proof = { source_url: "https://example.com/official-result", checked_date: "2026-11-04" };
const team = (name: string, role: string | null, final_score: number, extra = {}) => ({ name, role, final_score, entity_type: "team", participant_id: name, ...extra });
const attempt = (weight_kg: number | null, status: "made" | "missed" | "unused") => ({ weight_kg, status });
const lifters = Array.from({ length: 19 }, (_, i) => ({ name: `Source athlete ${i}`, nation: i === 0 ? "WRT" : "GER", gender: "women", weight_class: "59", group: "A", total_rank: i < 3 ? i + 1 : null,
  total_kg: i < 3 ? 250 - i : null, ...(i === 0 ? {} : { country_code: "DE" }),
  snatch: [attempt(100, "missed"), attempt(100, "made"), attempt(null, "unused")], clean_and_jerk: [attempt(120, "made"), attempt(125, "missed"), attempt(null, "unused")] }));
const medal = (name: string, rank: number, extra = {}) => ({ name, rank, nation: "GER", gender: "women", weight_class: "59", country_code: "DE", ...extra });
const weightResult = { kind: "weightlifting", ...proof, athletes: lifters,
  medal_classes: [{ gender: "women", weight_class: "59" }], mixed_classes: false,
  total_medalists: [medal("Global class gold", 1), medal("Global class silver", 2), medal("Global bronze from B", 3)],
  snatch_medalists: [medal("Explicit snatch gold", 1, { weight_kg: 110 })], clean_and_jerk_medalists: [medal("Explicit jerk bronze", 3, { weight_kg: 125 })],
  sources: [{ ...proof, gender: "women", weight_class: "59", revision: "101" }, { ...proof, source_url: "https://example.com/other-class", gender: "men", weight_class: "+109", checked_date: "2026-11-03", revision: "99" }] };
const roster = [{ name: "Old roster athlete", role: null, participant_id: "old", entity_type: "athlete", entry_total_kg: 150, start_list_source_url: "https://example.com/roster", start_list_checked_date: "2026-11-02" }];

for (const width of [320, 375, 1280]) test(`source-backed team outcomes and ordering stay truthful at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 960 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const games = [
    event("Drawn leg", undefined, { title: "Original neutral-venue title", league: "COPA_LIBERTADORES", status: "finished", participants: [team("Home club", "home", 1, { result_winner: false, aggregate_score: 3, shootout_score: 1 }), team("Away qualifier", "away", 1, { result_winner: true, result_advance: true, aggregate_score: 3, shootout_score: 2 })] }),
    event("Lost leg", undefined, { league: "COPA_LIBERTADORES", status: "finished", participants: [team("Leg winner", "home", 2, { result_winner: false, aggregate_score: 3, shootout_score: 1 }), team("Advancing club", "away", 1, { result_winner: true, result_advance: true, aggregate_score: 3, shootout_score: 2 })] }),
    event("Normal draw", undefined, { status: "finished", participants: [team("Draw home", "home", 0, { result_winner: false }), team("Draw away", "away", 0, { result_winner: false })] }),
    event("Basketball final", undefined, { league: "NBA", sport: "basketball", status: "finished", participants: [team("Home side", "home", 90, { result_winner: false }), team("Away side", "away", 100, { result_winner: true })] }),
    event("Winning advancer", undefined, { title: "Source winning-leg title", league: "COPA_LIBERTADORES", status: "finished", participants: [team("Winning qualifier", "home", 3, { result_winner: true, result_advance: true }), team("Other leg side", "away", 1, { result_winner: false })] }),
    event("Openfootball final", undefined, { source: "openfootball", title: "Literal openfootball source title", status: "finished", participants: [team("Higher home", "home", 2), team("Lower away", "away", 0)] }),
    event("NHL final", undefined, { source: "nhl", league: "NHL", sport: "hockey", title: "Literal NHL source title", status: "finished", participants: [team("Home hockey", "home", 2), team("Away hockey", "away", 4)] }),
    event("Roleless cricket", undefined, { league: "IPL", sport: "cricket", status: "finished", participants: [team("First source team", null, 180), team("Second source team", null, 180)] }),
  ];
  await setup(page, games);
  await agendaToggle(page).click();
  const row = page.locator('[id="agenda-2026-10-28-Drawn leg"]');
  await expect(row.locator(".team-name")).toHaveText(["Away qualifier", "Home club"]);
  await expect(row).toContainText("1–1FinalAggregate 3–3Shootout 2–1");
  await expect(row.locator(".agenda-team-outcome")).toHaveText(["Advances"]);
  await expect(row.locator(".agenda-team-winner")).toHaveCount(0);
  await row.getByRole("button").click();
  const popup = page.getByRole("dialog");
  await expect(popup.locator("h3")).toContainText("Original neutral-venue title");
  const scores = popup.getByRole("table", { name: "Final team scores" });
  await expect(scores.locator("tbody th")).toHaveText(["Home club", "Away qualifierAdvances"]);
  await expect(scores.locator("tbody tr").first().locator("td")).toHaveText(["1", "3", "1"]);
  await expect(scores.locator(".event-result-match-winner")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(row.getByRole("button")).toBeFocused();
  const nba = page.locator('[id="agenda-2026-10-28-Basketball final"]');
  await expect(nba.locator(".team-name")).toHaveText(["Away side", "Home side"]);
  await expect(nba.locator(".agenda-team-winner")).toContainText("Away side");
  await expect(page.locator('[id="agenda-2026-10-28-Normal draw"] .agenda-team-outcome')).toHaveCount(0);
  await expect(page.locator('[id="agenda-2026-10-28-Lost leg"] .agenda-team-outcome')).toHaveText(["Advances", "Winner"]);
  const roleless = page.locator('[id="agenda-2026-10-28-Roleless cricket"]');
  await expect(roleless.locator(".agenda-team")).toHaveCount(0);
  await roleless.getByRole("button").click();
  await expect(popup.getByRole("table", { name: "Final team scores" }).locator("tbody th")).toHaveText(["First source team", "Second source team"]);
  await expect(popup.locator(".event-result-match-winner")).toHaveCount(0);
  await page.keyboard.press("Escape");
  const advancingWin = page.locator('[id="agenda-2026-10-28-Winning advancer"]');
  await expect(advancingWin.locator(".agenda-team-outcome")).toHaveText(["Winner", "Advances"]);
  await expect(advancingWin.locator(".agenda-team-winner")).toContainText("Winning qualifier");
  await advancingWin.getByRole("button").click();
  await expect(popup.locator("h3")).toContainText("Source winning-leg title");
  await expect(popup.locator(".event-result-match-winner small")).toHaveText(["Winner", "Advances"]);
  await page.keyboard.press("Escape");
  for (const [id, names, winner, title] of [
    ["Openfootball final", ["Lower away", "Higher home"], "Higher home", "Literal openfootball source title"],
    ["NHL final", ["Away hockey", "Home hockey"], "Away hockey", "Literal NHL source title"],
  ] as const) {
    const inferred = page.locator(`[id="agenda-2026-10-28-${id}"]`);
    await expect(inferred.locator(".team-name")).toHaveText([...names]);
    await expect(inferred.locator(".agenda-team-winner .team-name")).toHaveText(winner);
    await inferred.getByRole("button").click();
    await expect(popup.locator("h3")).toContainText(title);
    await expect(popup.locator(".event-result-match-winner small")).toHaveText(["Winner"]);
    await page.keyboard.press("Escape");
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

for (const width of [320, 375, 1280]) test(`complete weightlifting results replace the roster without invented IDs at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 960 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setup(page, [event("Weight session", undefined, { title: "Source session title · Women 59 A", league: "IWF_WORLDS", sport: "weightlifting", status: "finished", result: weightResult, participants: roster })]);
  // The result is absent from calendar pills and appears only in Agenda/details.
  await expect(page.locator(".event-pill")).not.toContainText("Global class gold");
  await agendaToggle(page).click();
  const row = page.locator(".agenda-row");
  await expect(row.locator(".agenda-result-summary")).toContainText("Global bronze from B");
  await row.getByRole("button").click();
  const popup = page.getByRole("dialog");
  await expect(popup.locator("h3")).toContainText("Source session title · Women 59 A");
  await expect(popup.getByRole("region", { name: "Start list", exact: true })).toHaveCount(0);
  await expect(popup.getByRole("region", { name: "Total medalists", exact: true }).locator("li")).toHaveCount(3);
  await expect(popup.getByRole("region", { name: "Snatch medalists", exact: true })).toContainText("Explicit snatch gold");
  await expect(popup.getByRole("region", { name: "Clean & jerk medalists", exact: true })).toContainText("Explicit jerk bronze");
  const medalists = popup.locator(".event-result-medalists");
  for (const section of await medalists.all()) {
    await expect(section).not.toContainText("GER");
    await expect(section).not.toContainText("Women's 59 kg");
  }
  await expect(medalists.getByRole("img", { name: "Germany", exact: true })).toHaveCount(5);
  const attempts = popup.getByRole("table", { name: "Weightlifting attempts and totals" });
  await expect(attempts.locator("tbody tr")).toHaveCount(19);
  const first = attempts.locator("tbody tr").first();
  await expect(first).toContainText("Source athlete 0WRT");
  await expect(first.getByRole("img")).toHaveCount(0);
  await expect(first.locator("s")).toHaveText(["100", "125"]);
  await expect(first.getByRole("cell", { name: "Snatch attempt 1, 100 kg, missed", exact: true })).toBeVisible();
  await expect(first.getByRole("cell", { name: "Snatch attempt 3, Unused", exact: true })).toBeAttached();
  await expect(popup.locator(".event-result-source")).toHaveCount(2);
  await expect(popup.getByRole("link", { name: /Women's 59 kg result source/ })).toHaveAttribute("href", proof.source_url);
  await expect(popup).toContainText("Checked 2026-11-03 · 99");
  const scroll = popup.getByRole("region", { name: "Athlete attempts" });
  await popup.screenshot({ path: testInfo.outputPath(`weightlifting-results-${width}.png`) });
  await scroll.focus();
  await expect(scroll).toBeFocused();
  if (width < 700) expect(await scroll.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("podium and tennis final facts render in Agenda and source-titled popups, including a retired incomplete set", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const race = event("Race result", undefined, { sport: "motorsport", event_type: "race", league: "NASCAR_CUP", title: "Literal source race title", status: "finished", result: { kind: "podium", ...proof, rows: [{ rank: 1, name: "Source winner" }, { rank: 2, name: "Source second" }, { rank: 3, name: "Source third" }] } });
  const tennis = event("Final result", undefined, { sport: "tennis", league: "WTA", title: "Literal tournament name", status: "finished", result: { kind: "tennis-final", ...proof, winner: { name: "Champion" }, runner_up: { name: "Finalist" }, status: "retired", score: { winner: [{ value: 6, winner: true }, { value: 2 }], runner_up: [{ value: 4, winner: false }, { value: 0 }] } } });
  await setup(page, [race, tennis]);
  await agendaToggle(page).click();
  const raceRow = page.locator('[id="agenda-2026-10-28-Race result"]');
  await expect(raceRow.locator(".agenda-result-summary")).toHaveText("1 Source winner · 2 Source second · 3 Source third");
  await raceRow.getByRole("button").click();
  await expect(page.locator(".event-details h3")).toContainText("Literal source race title");
  await expect(page.getByRole("table", { name: "Podium", exact: true }).locator("tbody th")).toHaveText(["Source winner", "Source second", "Source third"]);
  await page.keyboard.press("Escape");
  const row = page.locator('[id="agenda-2026-10-28-Final result"]');
  await expect(row.locator(".agenda-result-summary")).toContainText("2–0 · Retired");
  await row.getByRole("button").click();
  await expect(page.locator(".event-details h3")).toContainText("Literal tournament name");
  const table = page.getByRole("table", { name: "Singles final" });
  await expect(table.locator("thead th")).toHaveText(["Player", "Set 1", "Set 2"]);
  await expect(table.locator(".event-result-set-winner")).toHaveCount(1);
  await expect(table.locator('td[aria-label="2"]')).toHaveCount(1);
  await expect(page.getByRole("link", { name: "Result source" })).toHaveAttribute("href", proof.source_url);
});

test("a medal-only result shows explicit medals with no invented attempts; a missing result keeps the dated start list", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setup(page, [event("Medal only", undefined, { league: "IWF_WORLDS", sport: "weightlifting", result: { ...weightResult, athletes: [], snatch_medalists: [], clean_and_jerk_medalists: [] } }),
    event("Roster only", undefined, { league: "WEIGHTLIFTING_EUROPE", sport: "weightlifting", participants: roster })]);
  await agendaToggle(page).click();
  await page.locator('[id="agenda-2026-10-28-Medal only"]').getByRole("button").click();
  await expect(page.getByRole("region", { name: "Total medalists", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Athlete attempts", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Snatch medalists", exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.locator('[id="agenda-2026-10-28-Roster only"]').getByRole("button").click();
  await expect(page.getByRole("region", { name: "Start list", exact: true })).toContainText("Old roster athlete");
  await expect(page.getByRole("region", { name: "Result", exact: true })).toHaveCount(0);
});


test("walkover and grouped source podiums show only supplied facts", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setup(page, [event("Walkover", undefined, { sport: "tennis", league: "ATP", status: "finished", result: { kind: "tennis-final", ...proof, winner: { name: "Confirmed champion" }, runner_up: { name: "Confirmed runner-up" }, status: "walkover" } }),
    event("Grouped podium", undefined, { sport: "climbing", league: "IFSC_WORLD_CUP", status: "finished", result: { kind: "podiums", ...proof, allocation_source: { source_url: "https://ifsc.results.info/events/1491/infosheet", checked_date: "2026-11-03", page: 3, sha256: "private-source-hash", scope: "private-allocation-review-prose" }, categories: [{ label: "LEAD Women B3", rows: [{ rank: 1, name: "First category winner" }, { rank: 3, name: "Tied bronze A" }, { rank: 3, name: "Tied bronze B" }] }, { label: "SPEED RELAY Men", rows: [{ rank: 1, name: "CHN" }, { rank: 2, name: "CHN" }] }] } })]);
  await agendaToggle(page).click();
  await page.locator('[id="agenda-2026-10-28-Walkover"]').getByRole("button").click();
  const final = page.getByRole("table", { name: "Singles final" });
  await expect(final.locator("thead th")).toHaveText(["Player"]);
  await expect(final.locator("tbody th")).toHaveText(["ChampionConfirmed champion", "Runner-upConfirmed runner-up"]);
  await expect(page.locator(".event-result-status")).toHaveText("Walkover");
  await page.keyboard.press("Escape");
  const row = page.locator('[id="agenda-2026-10-28-Grouped podium"]');
  await expect(row.locator(".agenda-result-summary")).toContainText("SPEED RELAY Men: 1 CHN · 2 CHN");
  await row.getByRole("button").click();
  await expect(page.getByRole("table", { name: "LEAD Women B3 podium" }).locator("tbody td")).toHaveText(["1", "3", "3"]);
  await expect(page.getByRole("table", { name: "SPEED RELAY Men podium" }).locator("tbody th")).toHaveText(["CHN", "CHN"]);
  const result = page.getByRole("region", { name: "Result", exact: true });
  await expect(result.getByRole("link", { name: "Result source" })).toHaveAttribute("href", proof.source_url);
  await expect(result.getByRole("link", { name: "Result source" }).locator("..")).toContainText("Checked 2026-11-04");
  await expect(result.getByRole("link", { name: "Session source" })).toHaveAttribute("href", "https://ifsc.results.info/events/1491/infosheet");
  await expect(result.getByRole("link", { name: "Session source" }).locator("..")).toHaveText("Session source ↗ · Checked 2026-11-03 · Page 3");
  await expect(result).not.toContainText("private-source-hash");
  await expect(result).not.toContainText("private-allocation-review-prose");
});


for (const width of [375, 1280]) test(`weightlifting lower and mixed groups keep their own attempts and only decided medals at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 960 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const otherClass = medal("57 kg gold decided later", 1, { weight_class: "57" });
  const earlier = { ...weightResult, medal_classes: [], athletes: [lifters[0]], mixed_classes: false };
  const mixed = { ...weightResult, medal_classes: [{ gender: "women", weight_class: "59" }], mixed_classes: true,
    total_medalists: [...weightResult.total_medalists, otherClass], snatch_medalists: [otherClass], clean_and_jerk_medalists: [otherClass], athletes: [lifters[0]] };
  await setup(page, [event("Earlier group", undefined, { league: "IWF_WORLDS", sport: "weightlifting", result: earlier }),
    event("Mixed classes", undefined, { league: "IWF_WORLDS", sport: "weightlifting", result: mixed })]);
  await agendaToggle(page).click();
  await expect(page.locator('[id="agenda-2026-10-28-Earlier group"] .agenda-result-summary')).toHaveCount(0);
  await expect(page.locator('[id="agenda-2026-10-28-Mixed classes"] .agenda-result-summary')).not.toContainText("57 kg gold decided later");
  await page.locator('[id="agenda-2026-10-28-Earlier group"]').getByRole("button").click();
  const popup = page.getByRole("dialog");
  await expect(popup.locator(".event-result-medalists")).toHaveCount(0);
  await expect(popup.getByRole("table", { name: "Weightlifting attempts and totals" }).locator("tbody tr")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await page.locator('[id="agenda-2026-10-28-Mixed classes"]').getByRole("button").click();
  await expect(popup.getByRole("region", { name: "Total medalists", exact: true }).locator("li")).toHaveCount(3);
  await expect(popup.locator(".event-result-medalists")).not.toContainText("57 kg gold decided later");
  await expect(popup.locator(".event-result-medalists")).not.toContainText("GER");
  await expect(popup.locator(".event-result-medalists")).toContainText("Women's 59 kg");
  await expect(popup.getByRole("region", { name: "Snatch medalists", exact: true })).toHaveCount(0);
  await expect(popup.getByRole("region", { name: "Clean & jerk medalists", exact: true })).toHaveCount(0);
  const attempts = popup.getByRole("table", { name: "Weightlifting attempts and totals" });
  await expect(attempts.locator("tbody tr")).toHaveCount(1);
  await expect(attempts.locator("tbody tr").first()).toContainText("Source athlete 0WRT");
});
