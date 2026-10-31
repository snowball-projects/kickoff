import { expect, test } from "./test";
import { event, month, setup } from "./fixtures";

const source = "https://github.com/openfootball/worldcup.json/blob/516d3825c3bd23fdc298c4014e84bde78f2d4965/2026/worldcup.json";
const fixture = (home: string, away: string, date: string, codes: string[], fields = {}) => event(`${home} vs ${away}`, date, {
  source: "openfootball", source_url: source, league: "FIFA_WORLD_CUP", status: "finished",
  country: "MX", country_source_url: "https://www.fifa.com/en/articles/fifa-world-cup-2026-hosts-cities-dates-usa-mexico-canada",
  participants: [home, away].map((name, i) => ({ name, country_code: codes[i], entity_type: "national_team", role: i ? "away" : "home" })),
  ...fields,
});

test("World Cup fixtures remain visible in June and July with national flags and phases", async ({ page }) => {
  await setup(page, [
    fixture("Mexico", "South Africa", "2026-06-11", ["MX", "ZA"], { subtitle: "Group A", start_time_utc: "2026-06-11T19:00:00Z" }),
    fixture("Spain", "Argentina", "2026-07-19", ["ES", "AR"], { subtitle: "Final", competition_phase: "postseason", country: "US", start_time_utc: "2026-07-19T19:00:00Z" }),
  ], { saved: { leagues: ["FIFA_WORLD_CUP"] } });
  for (const [label, date, title, phase, flag] of [
    ["June 2026", "2026-06-11", "Mexico vs South Africa", "Group A", "Mexico: Mexico"],
    ["July 2026", "2026-07-19", "Spain vs Argentina", "Final", "Spain: Spain"],
  ]) {
    await month(page, label);
    await page.locator(`#day-${date} .event-pill`).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText(title);
    await expect(dialog).toContainText(phase);
    await expect(dialog.getByRole("img", { name: flag, exact: true })).toBeVisible();
    await expect(dialog.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", source);
    await page.keyboard.press("Escape");
  }
});
