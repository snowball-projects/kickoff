import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { agendaToggle, chooser, setup } from "./fixtures";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const events = JSON.parse(execFileSync(python, ["-c", `
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
from kickoff import feeds
from kickoff.web import _event_payload
fixture=json.loads(Path('tests/fixtures/espn-tournaments.json').read_text())['feeds']
golf=json.loads(Path('tests/fixtures/espn-golf.json').read_text())['feeds']
def read(url):
    parsed=urlparse(url)
    sport,tour,_=parsed.path.split('/sports/')[1].split('/')
    year=parse_qs(parsed.query)['dates'][0]
    return golf[tour] if tour in ('pga','lpga') else fixture[f'{sport}/{tour}/{year}']
wanted={'espn-atp-154-2026','espn-wta-154-2026','espn-dp_world_tour-401822677',
        'espn-liv_golf-401807532','espn-six_nations-602502','espn-top_14-604452'}
result=[]
with patch('kickoff.feeds.get_json',read):
    for league,year in [('ATP',2026),('WTA',2026),('DP_WORLD_TOUR',2026),('LIV_GOLF',2026),
                        ('SIX_NATIONS',2026),('TOP_14',2027),('PGA_TOUR',2026),('LPGA_TOUR',2026)]:
        selected=feeds.FEEDS[league][1](year)
        if league in ('PGA_TOUR','LPGA_TOUR'): selected=selected[:1]
        else: selected=[event for event in selected if event.event_id in wanted]
        result.extend(_event_payload(event) for event in selected)
print(json.dumps(result))
`], { cwd: root, env: { ...process.env, PYTHONPATH: `${root}src` } }).toString());
const boards = JSON.parse(readFileSync(new URL("../fixtures/golf-tours.json", import.meta.url), "utf8")).payloads;
const endpoint = /^https:\/\/site\.web\.api\.espn\.com\/apis\/site\/v2\/sports\/golf\/leaderboard\?/;
const source = (id: string) => events.find((event: { event_id: string }) => event.event_id === id);

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`tournament sports ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("tour choices, source-backed tennis spans, DP/LIV top fives and rugby clocks/results", async ({ page }) => {
      const requests: string[] = [];
      await page.route(endpoint, async route => {
        const request = route.request(), id = new URL(request.url()).searchParams.get("event");
        expect(request.method()).toBe("GET");
        expect(request.postData()).toBeNull();
        expect(request.headers().authorization).toBeUndefined();
        expect(request.headers()["content-type"]).toBeUndefined();
        expect(Object.keys(request.headers()).some(key => key.startsWith("x-"))).toBe(false);
        expect(["401822677", "401807532"]).toContain(id);
        requests.push(id!);
        await route.fulfill({ json: id === "401822677" ? boards.dp_world : boards.liv,
          headers: { "access-control-allow-origin": "*" } });
      });
      await setup(page, events, { firstVisit: true, now: "2026-02-05T17:00:00Z" });
      await chooser(page).getByRole("button", { name: "Tennis", exact: true }).click();
      const tennis = chooser(page).getByRole("region", { name: "Tennis interests" });
      await expect(tennis.getByRole("button")).toHaveText(["All", "ATP", "WTA"]);
      await tennis.getByRole("button", { name: "WTA", exact: true }).click();
      await expect(chooser(page).getByRole("button", { name: "Tennis", exact: true })).toHaveAttribute("aria-pressed", "mixed");
      await chooser(page).getByRole("button", { name: "Golf", exact: true }).click();
      await expect(chooser(page).getByRole("region", { name: "Golf interests" }).getByRole("button"))
        .toHaveText(["All", "PGA Tour", "LPGA Tour", "DP World Tour", "LIV Golf"]);
      await chooser(page).getByRole("button", { name: "Rugby", exact: true }).click();
      await expect(chooser(page).locator('svg[data-sport="tennis"], svg[data-sport="rugby"]')).toHaveCount(2);
      await page.screenshot({ path: `test-results/tournament-choices-${width}-${colorScheme}.png` });
      await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
      await page.locator("#day-2026-01-15 .day-number").click();
      const australian = source("espn-atp-154-2026");
      await expect(page.locator(".all-day-strip .event-pill").filter({ hasText: "Australian Open" })).toHaveCount(1);
      await page.locator(".all-day-strip .event-pill").filter({ hasText: "Australian Open" }).click();
      await expect(page.locator(".event-details h3")).toContainText(australian.title);
      await expect(page.getByRole("dialog")).toContainText("Sunday, January 11, 2026 through Sunday, February 1, 2026");
      await expect(page.locator(".detail-time")).toHaveCount(0);
      await expect(page.getByRole("link", { name: "Schedule source ↗" })).toHaveAttribute("href", australian.source_url);
      await page.screenshot({ path: `test-results/tournament-tennis-span-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      const dubai = source("espn-dp_world_tour-401822677");
      await page.locator(".all-day-strip .event-pill").filter({ hasText: dubai.title }).click();
      await expect(page.locator(".event-details h3")).toContainText(`${dubai.title}, Round 1`);
      await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(5);
      await expect(page.getByRole("table").locator("tbody tr").first().locator("td")).toHaveText(["1", "Nacho Elvira", "-10", "-2", "18"]);
      await expect(page.getByRole("link", { name: "Schedule source ↗" })).toHaveAttribute("href", dubai.source_url);
      await page.screenshot({ path: `test-results/tournament-dp-top-five-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.locator(".today-button").click();
      const liv = source("espn-liv_golf-401807532");
      await page.locator(".all-day-strip .event-pill").filter({ hasText: liv.title }).click();
      await expect(page.locator(".event-details h3")).toContainText(`${liv.title}, Round 2`);
      await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(5);
      await expect(page.getByRole("table").locator("tbody tr").first().locator("td").nth(1)).toHaveText("Elvis Smylie");
      await page.screenshot({ path: `test-results/tournament-liv-top-five-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      const rugby = source("espn-six_nations-602502");
      await page.locator(`.timeline-events [data-event-id="${rugby.event_id}"]`).click();
      await expect(page.locator(".event-details h3")).toContainText(rugby.title);
      await expect(page.locator(".detail-time")).toHaveText("2:10 PM");
      await expect(page.getByRole("link", { name: "Schedule source ↗" })).toHaveAttribute("href", rugby.source_url);
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.locator('.week-strip [data-date="2027-01-02"]').click();
      await page.locator(".all-day-strip .event-pill").filter({ hasText: "Bayonne" }).click();
      await expect(page.getByRole("dialog")).toContainText("Saturday, January 2, 2027");
      await expect(page.locator(".detail-time")).toHaveCount(0);
      await page.screenshot({ path: `test-results/tournament-rugby-date-only-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.locator(".today-button").click();
      await page.getByRole("button", { name: "Back to February", exact: true }).click();
      await agendaToggle(page).click();
      const sixNations = page.getByRole("region", { name: "Six Nations", exact: true });
      await expect(sixNations.locator(".team-name")).toHaveText(["Ireland", "France"]);
      await expect(sixNations.locator(".agenda-result")).toHaveText("14–36");
      await expect(sixNations.locator(".team-record")).toHaveCount(0);
      await page.screenshot({ path: `test-results/tournament-rugby-agenda-${width}-${colorScheme}.png` });
      expect(requests).toContain("401822677");
      expect(requests).toContain("401807532");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}
