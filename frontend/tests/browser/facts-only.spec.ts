import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { agendaToggle, setup } from "./fixtures";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const events = JSON.parse(execFileSync(python, ["-c", `
import json
from pathlib import Path
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.web import _event_payload
records = load_reviewed_schedules(Path('data/reviewed'), 2026)[0]
gunsan = next(e for e in records if e.event_id.endswith('gunsan-2026-boulder-qualification'))
unknown = [e for e in records if e.event_id.startswith('world-climbing-series-2026-salt-lake-city-') and not e.start_time_utc]
print(json.dumps([_event_payload(e) for e in [gunsan, *unknown]]))
`], { cwd: root, encoding: "utf8" }));

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`facts-only cards ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, timezoneId: "Asia/Seoul", reducedMotion: "reduce" });
    test("reviewed Gunsan location and known clock appear once; unknown clocks stay blank", async ({ page }) => {
      await setup(page, [events[0]], { now: "2026-10-31T03:00:00Z", saved: { leagues: ["CLIMBING_CONTINENTAL_CUP", "IFSC_WORLD_CUP"] } });
      await page.locator("#day-2026-10-31 .event-pill").click();
      const sheet = page.getByRole("dialog");
      const details = sheet.getByRole("article");
      await expect(details.locator("h3")).toContainText("World Climbing Asia Series Gunsan · Boulder Qualification");
      await expect(details.locator("p")).toHaveText(["8:30 AM", "Saturday, October 31, 2026", "Gunsan · South Korea"]);
      await expect(details.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", events[0].source_url);
      await page.screenshot({ path: `test-results/facts-gunsan-${width}-${colorScheme}.png` });
      await page.keyboard.press("Escape");
      const unknown = events.slice(1);
      await setup(page, unknown, { now: `${unknown[0].calendar_date}T03:00:00Z` });
      await agendaToggle(page).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      await expect(agenda.locator(".agenda-time")).toHaveCount(0);
      await agenda.locator(".agenda-row").first().click();
      await expect(sheet.locator(".detail-time")).toHaveCount(0);
      await expect(sheet).not.toContainText(/TBD|withheld|not published|past schedule|finished/);
      await page.screenshot({ path: `test-results/facts-unknown-${width}-${colorScheme}.png` });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}

test("date-only sheet rows have blank clocks and keep factual feed subtitles", async ({ page }) => {
  const { event } = await import("./fixtures");
  await setup(page, [
    event("Date-only match", undefined, { subtitle: "Matchday 1", status: "finished" }),
    event("Another date-only match"),
  ], { saved: { leagues: ["EPL"] } });
  await page.locator("#day-2026-10-28 .event-pill").click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.locator(".sheet-event-row > span:first-child")).toHaveText(["", ""]);
  await sheet.getByRole("button", { name: "Date-only match", exact: false }).filter({ hasText: "Date-only match" }).last().click();
  await expect(sheet.locator(".detail-time")).toHaveCount(0);
  await expect(sheet).toContainText("Matchday 1");
  await expect(sheet).not.toContainText(/TBD|finished/);
});
