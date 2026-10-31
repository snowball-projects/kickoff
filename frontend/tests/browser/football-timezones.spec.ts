import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { publishedFiles } from "../published-fixture.mjs";

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
    ('es.1', '2026-27', '2026-10-25', None, 'Missing clock'),
    ('br.1', '2026', '2026-12-31', '23:30', 'Year boundary'),
    ('es.1', '2026-27', '2026-12-31', None, 'Date-only clock'),
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
    await page.addInitScript(() => localStorage.setItem("kickoff.interests.v4", JSON.stringify({
      leagues: ["EPL", "BRASILEIRAO", "LA_LIGA"],
      motorsport_events: [], climbing: { levels: [], genders: [], disciplines: [] }, weightlifting: { levels: [], genders: [] },
    })));
    const files = publishedFiles([{ season: 2026, events }, { season: 2027, events: [] }]);
    await page.route("**/data/*.json", async (route) => {
      const file = route.request().url().split("/").at(-1)!;
      await (file in files ? route.fulfill({ json: files[file] }) : route.fulfill({ status: 404, body: "missing" }));
    });
    await page.goto("/");
    await page.getByRole("switch", { name: "Agenda view" }).click();
    const agenda = page.getByRole("region", { name: "Agenda", exact: true });
    await expect(agenda).toContainText(scenario.date);
    await expect(agenda.locator(".agenda-row").filter({ hasText: scenario.name })).toContainText(scenario.time);
    if (scenario.name === "Summer clock") {
      for (const name of ["Repeated clock", "Missing clock"])
        await expect(agenda.locator(".agenda-row").filter({ hasText: name }).locator(".agenda-time")).toHaveCount(0);
    }
    if (scenario.name === "Year boundary") {
      await expect(agenda).not.toContainText("Date-only clock");
      await page.getByRole("group", { name: "Agenda days", exact: true }).getByRole("button", { name: "Yesterday", exact: true }).click();
      await expect(agenda).toContainText("Thursday, December 31, 2026");
      await expect(agenda.locator(".agenda-row").filter({ hasText: "Date-only clock" }).locator(".agenda-time")).toHaveCount(0);
    }
  });
}
