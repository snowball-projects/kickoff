import { expect, test } from "./test";
import { chooser, event, setup } from "./fixtures";

const leagues = {
  Soccer: ["UEFA_EUROPA_LEAGUE", "UEFA_CONFERENCE_LEAGUE", "UEFA_NATIONS_LEAGUE", "MLS"],
  Football: ["NFL", "COLLEGE_FOOTBALL"],
  Basketball: ["NBA", "WNBA", "NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL"],
};
const events = Object.entries(leagues).flatMap(([group, values]) => values.map(league =>
  event(`${league} fixture`, undefined, { league, sport: group === "Soccer" ? "soccer" : group === "Football" ? "football" : "basketball" })));

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test(`new team league trays ${width}px ${colorScheme}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
    const requests: string[] = [];
    await setup(page, events, { firstVisit: true, requests });
    const dialog = chooser(page);
    await expect(dialog).toBeVisible();
    expect(requests.every(file => file === "manifest.json")).toBe(true);
    for (const [name, labels] of [
      ["Soccer", ["Europa League", "Conference League", "Nations League", "MLS"]],
      ["Football", ["NFL", "College football"]],
      ["Basketball", ["NBA", "WNBA", "Men's college basketball", "Women's college basketball"]],
    ] as const) {
      await dialog.getByRole("button", { name, exact: true }).click();
      const tray = dialog.getByRole("region", { name: `${name} interests`, exact: true });
      await expect(tray).toBeVisible();
      for (const label of labels) await expect(tray.getByRole("button", { name: label, exact: true })).toHaveAttribute("aria-pressed", "true");
    }
    const basketball = dialog.getByRole("region", { name: "Basketball interests", exact: true });
    await basketball.getByRole("button", { name: "WNBA", exact: true }).click();
    await expect(dialog.getByRole("button", { name: "Basketball", exact: true })).toHaveAttribute("aria-pressed", "mixed");
    await expect(dialog.getByRole("button", { name: "Basketball", exact: true })).toContainText("3/4");
    await page.screenshot({ path: `test-results/team-leagues-${width}-${colorScheme}.png` });
    await dialog.getByRole("button", { name: "Show my calendar", exact: true }).click();
    await expect(page.locator("#day-2026-10-28")).not.toContainText("WNBA");
    await page.reload();
    await page.getByRole("button", { name: "Interests", exact: true }).click();
    await dialog.getByRole("button", { name: "Basketball", exact: true }).click();
    await expect(dialog.getByRole("region", { name: "Basketball interests", exact: true }).getByRole("button", { name: "WNBA", exact: true })).toHaveAttribute("aria-pressed", "false");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) for (const knownSide of [false, true]) test(`an undecided bowl preserves its label and known side ${knownSide} ${width} ${colorScheme}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 });
  await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
  const label = "College Football Playoff Quarterfinal at the Goodyear Cotton Bowl Classic";
  const team = { name: "Washington Huskies", participant_id: "264", short_name: "Washington", record: "7-1", role: "home", entity_type: "team" };
  const title = label + (knownSide ? ` · ${team.name}` : "");
  await setup(page, [event(title, "2027-01-01", { league: "COLLEGE_FOOTBALL", sport: "football",
    competition_phase: "postseason", round_or_stage: label, week_label: "Week 1",
    participants: knownSide ? [team] : [], home_participant: knownSide ? team : null, away_participant: null })], { now: "2027-01-01T17:00:00Z" });
  await page.getByRole("switch", { name: "Agenda view" }).click();
  const row = page.locator(".agenda-row");
  await expect(row).toContainText("Playoff Quarterfinal at the Goodyear Cotton Bowl Classic");
  await expect(row.locator(".team-name")).toHaveText(knownSide ? [team.short_name] : []);
  await expect(row.locator(".team-record")).toHaveText(knownSide ? [team.record] : []);
  await expect(row).not.toContainText("TBD");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await row.getByRole("button").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(title);
  expect((await dialog.innerText()).split(label).length - 1).toBe(1);
  if (knownSide) expect((await dialog.innerText()).split(team.name).length - 1).toBe(1);
});

test("an undecided Super Bowl keeps its source name and clock without pseudoentities", async ({ page }) => {
  await setup(page, [event("Super Bowl LXI", "2027-02-14", { league: "NFL", sport: "football",
    competition_phase: "postseason", round_or_stage: "Week 4", week_label: "Week 4",
    start_time_utc: "2027-02-14T23:30:00Z", participants: [], home_participant: null, away_participant: null })], { now: "2027-02-14T17:00:00Z" });
  await page.getByRole("switch", { name: "Agenda view" }).click();
  const row = page.locator(".agenda-row");
  await expect(row).toContainText("Super Bowl LXI");
  await expect(row.locator(".team-name, .team-record")).toHaveCount(0);
  await expect(row).not.toContainText("TBD");
  await row.getByRole("button").click();
  const dialog = page.getByRole("dialog");
  expect((await dialog.innerText()).split("Super Bowl LXI").length - 1).toBe(1);
  await expect(dialog).toContainText("5:30 PM");
});
