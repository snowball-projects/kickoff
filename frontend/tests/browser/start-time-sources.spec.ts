import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const event = JSON.parse(execFileSync(python, ["-c", `
import json
from pathlib import Path
from kickoff import feeds
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.start_times import fill_missing_start_times
from kickoff.web import _event_payload
record = next(e for e in load_reviewed_schedules(Path('data/reviewed'), 2026)[0]
              if e.event_id == 'pfl-2026-global-08')
feeds.get_json = lambda _: {'events': [{
    'id': '600059277', 'date': '2026-06-28T00:00Z',
    'links': [{'href': 'https://www.espn.com/mma/fightcenter/_/id/600059277'}],
    'competitions': [{'date': '2026-06-28T00:00Z', 'timeValid': True}],
}]}
fill_missing_start_times([record], 2026)
print(json.dumps(_event_payload(record)))
`], { cwd: root, encoding: "utf8" }));

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, hasTouch: width === 320 });
    test("timeline details retain the schedule source and separately credit the ESPN clock", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
      await page.clock.setFixedTime(new Date("2026-06-27T17:00:00Z"));
      await page.addInitScript(() => localStorage.setItem("kickoff.interests.v3", JSON.stringify({
        leagues: ["PFL"], motorsport_events: [], climbing: { genders: [], disciplines: [] }, weightlifting: { genders: [] },
      })));
      await page.route("**/data/*.json", async (route) => {
        const year = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
        await route.fulfill({ json: {
          schema_version: "1", season: year, available_seasons: [2026, 2027], providers: [],
          events: year === 2026 ? [event] : [],
        } });
      });
      await page.goto("/");
      await page.locator("#day-2026-06-27 .day-number").click();
      const panel = page.getByRole("region", { name: "Day events", exact: true });
      await panel.locator(`[data-event-id="${event.event_id}"]`).click();
      const detail = page.getByRole("dialog").getByRole("article", { name: "Event details" });
      await expect(panel.locator(".timeline-hour")).toHaveCount(25);
      await expect(detail).toContainText(event.title);
      await expect(detail).toContainText("7:00 PM");
      const schedule = detail.getByRole("link", { name: "Schedule source" });
      const clock = detail.getByRole("link", { name: "Time source: ESPN" });
      await expect(schedule).toBeVisible();
      await expect(clock).toBeVisible();
      await expect(schedule).toHaveAttribute("href", event.source_url);
      await expect(clock).toHaveAttribute("href", event.start_time_source_url);
      await schedule.focus();
      await page.keyboard.press("Tab");
      await expect(clock).toBeFocused();
      await page.keyboard.press("Shift+Tab");
      await expect(schedule).toBeFocused();
      expect(event.source).toBe("wikipedia");
      expect(event.source_url).toContain("en.wikipedia.org/");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/start-time-sources-${width}-${colorScheme}.png` });
      await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
      await expect(detail).toHaveCount(0);
      await expect(panel.locator(`[data-event-id="${event.event_id}"]`)).toBeFocused();
      expect(errors).toEqual([]);
    });
  });
}
