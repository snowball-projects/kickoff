import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { agendaToggle, event, setup } from "./fixtures";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const events = JSON.parse(execFileSync(python, ["-c", `
import json
from pathlib import Path
from unittest.mock import patch
from kickoff import feeds
from kickoff.web import _event_payload
fixture=json.loads(Path('tests/fixtures/espn-tournaments.json').read_text())['feeds']
national=json.loads(Path('tests/fixtures/espn-national-matches.json').read_text())
result=[]
for league,key,year in [('SIX_NATIONS','rugby/180659/2025',2025),
                        ('BRITISH_IRISH_LIONS','rugby/268565/2025',2025),
                        ('RUGBY_WORLD_CUP','rugby/164205/2027',2027)]:
    with patch('kickoff.feeds.get_json',lambda _:fixture[key]):
        result.extend(_event_payload(event) for event in feeds.FEEDS[league][1](year))
for row in national['events']:
    result.append(_event_payload(feeds._espn_event(row,league='UEFA_NATIONS_LEAGUE',sport='soccer',
        zone=feeds.EASTERN,fallback_url=national['source_urls'][0],input_url=national['source_urls'][0])))
print(json.dumps(result))
`], { cwd: root, env: { ...process.env, PYTHONPATH: `${root}src` } }).toString());

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`national identities ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("source-backed Wales, Nations, World Cup and composite identities", async ({ page }) => {
      for (const [id, flag, absent] of [
        ["espn-six_nations-600250", "Wales: Wales", ""],
        ["espn-british_irish_lions-602527", "Argentina: Argentina", "British and Irish Lions"],
        ["espn-uefa_nations_league-401861189", "Wales: Wales", ""],
        ["espn-uefa_nations_league-401861191", "Hungary: Hungary", "Northern Ireland"],
        ["espn-rugby_world_cup-603499", "Australia: Australia", ""],
      ]) {
        const source = events.find((item: { event_id: string }) => item.event_id === id);
        // Each historical source date is viewed within the rolling window.
        await setup(page, events, { now: `${source.calendar_date}T17:00:00Z` });
        await page.locator(`#day-${source.calendar_date} .day-number`).click();
        await page.locator(`.timeline-events [data-event-id="${id}"]`).click();
        const details = page.locator(".event-details");
        await expect(details.locator("h3")).toContainText(source.title);
        await expect(details.getByRole("img", { name: flag, exact: true })).toBeVisible();
        if (absent) await expect(details.locator(`.country-flag[aria-label^="${absent}:"]`)).toHaveCount(0);
        if (id === "espn-rugby_world_cup-603499") await expect(details.getByRole("img", { name: /^Hong Kong:/ })).toHaveText("🇭🇰");
        await expect(page.getByRole("link", { name: "Schedule source ↗" })).toHaveAttribute("href", source.source_url);
        await page.screenshot({ path: `test-results/national-${id}-${width}-${colorScheme}.png` });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await page.getByRole("button", { name: "Close", exact: true }).click();
      }
    });
  });
}

test("partial rugby appointments retain a centered stage and one known team", async ({ page }) => {
  const australia = { name: "Australia", participant_id: "6", short_name: "Australia", role: "home", entity_type: "national_team", country_code: "AU" };
  // Synthetic future-state regression, not a claimed published RWC appointment.
  await setup(page, [event("Quarterfinal · Australia", "2026-10-28", {
    sport: "rugby", league: "RUGBY_WORLD_CUP", round_or_stage: "Quarterfinal", country: null,
    participants: [australia], home_participant: australia, away_participant: null,
  }), event("Rugby World Cup", "2026-10-28", { sport: "rugby", league: "RUGBY_WORLD_CUP", country: null, venue: null, city: null })]);
  await agendaToggle(page).click();
  const partial = page.locator(".agenda-row").filter({ has: page.locator(".team-name") });
  await expect(partial.locator(".team-name")).toHaveText("Australia");
  await expect(partial.locator(".agenda-round")).toHaveText("Quarterfinal");
  await expect(partial).not.toContainText(/TBD|TBA/);
  await page.getByRole("button", { name: "Rugby World Cup", exact: true }).click();
  await expect(page.locator(".event-details h3")).toContainText("Rugby World Cup");
});
