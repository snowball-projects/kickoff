import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

// Exercise the real importer and confirmed league mappings with synthetic clocks.
const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const events = JSON.parse(execFileSync(python, ["-c", `
import json
from kickoff.open_schedules import football_events
from kickoff.web import _event_payload
events = []
for key, season, day, clock, name in [
    ('en.1', '2026-27', '2026-10-24', '20:00', 'Summer clock'),
    ('en.1', '2026-27', '2026-10-25', '20:00', 'Winter clock'),
    ('en.1', '2026-27', '2026-10-25', '01:30', 'Repeated clock'),
    ('es.1', '2026-27', '2026-10-25', '20:00', 'Unconfirmed league'),
    ('br.1', '2026', '2026-12-31', '23:30', 'Year boundary'),
    ('es.1', '2026-27', '2026-12-31', '23:30', 'Date-only clock'),
]:
    row = dict(date=day, time=clock, team1=name, team2='Away')
    events.extend(_event_payload(e) for e in football_events(
        {'matches': [row]}, key, season, 'https://example.org/synthetic'))
print(json.dumps(events))
`], { cwd: root, encoding: "utf8" }));

test.use({ timezoneId: "Asia/Tokyo" });
for (const scenario of [
  { now: "2026-10-25T00:00:00Z", name: "Summer clock", time: "4:00 AM", date: "Sunday, October 25, 2026" },
  { now: "2026-10-26T00:00:00Z", name: "Winter clock", time: "5:00 AM", date: "Monday, October 26, 2026" },
  { now: "2027-01-01T00:00:00Z", name: "Year boundary", time: "11:30 AM", date: "Friday, January 1, 2027" },
]) {
  test(`imported ${scenario.name} uses the visitor's date and clock`, async ({ page }) => {
    await page.clock.setFixedTime(new Date(scenario.now));
    await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({
      leagues: ["EPL", "BRASILEIRAO", "LA_LIGA"],
      golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" }, motorsport_view: "race_only",
    })));
    await page.route("**/data/*.json", async (route) => {
      const year = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
      await route.fulfill({ json: {
        schema_version: "1", season: year, available_seasons: [2026, 2027], providers: [],
        events: year === 2026 ? events : [],
      } });
    });
    await page.goto("/");
    await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Agenda", exact: true }).click();
    const agenda = page.getByRole("region", { name: "Agenda", exact: true });
    await expect(agenda).toContainText(scenario.date);
    await expect(agenda.getByRole("button").filter({ hasText: `${scenario.name} vs Away` })).toContainText(scenario.time);
    if (scenario.name === "Summer clock") {
      for (const name of ["Repeated clock", "Unconfirmed league"])
        await expect(agenda.getByRole("button").filter({ hasText: `${name} vs Away` })).toContainText("Time TBD");
    }
    if (scenario.name === "Year boundary") {
      await expect(agenda).not.toContainText("Date-only clock");
      await page.getByRole("group", { name: "Agenda days", exact: true }).getByRole("button", { name: "Yesterday", exact: true }).click();
      await expect(agenda).toContainText("Thursday, December 31, 2026");
      await expect(agenda.getByRole("button").filter({ hasText: "Date-only clock vs Away" })).toContainText("Time TBD");
    }
  });
}
