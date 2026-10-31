import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { setup } from "./fixtures";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const records = JSON.parse(execFileSync(python, ["-c", `
import json
from pathlib import Path
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.web import _event_payload
rows, sources, _ = load_reviewed_schedules(Path('data/reviewed'), 2026)
selected = [e for e in rows if e.event_id == 'zuffa-boxing-2026-12' or (e.league == 'BOXING_MAJOR' and 'Taduran' in e.title and 'Moreno' in e.title)]
print(json.dumps({'events': [_event_payload(e) for e in selected], 'sources': sources}))
`], { cwd: root, encoding: "utf8" }));

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`reviewed boxing ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("Zuffa and single-title bouts have separate choices, date-only popups, honest coverage and attribution", async ({ page }) => {
      await setup(page, records.events, { now: "2026-11-07T17:00:00Z", metadata: { sources: records.sources } });
      await page.getByRole("button", { name: "Interests", exact: true }).click();
      await page.getByRole("button", { name: "Combat sports", exact: true }).click();
      const tray = page.getByRole("region", { name: "Combat sports interests", exact: true });
      await expect(tray.getByRole("button", { name: "Zuffa Boxing", exact: true })).toHaveAttribute("aria-pressed", "true");
      await expect(tray.getByRole("button", { name: "Boxing", exact: true })).toHaveAttribute("aria-pressed", "true");
      await page.getByRole("button", { name: "Close", exact: true }).click();
      const day = page.locator("#day-2026-11-07");
      await day.locator(".event-pill").filter({ hasText: "Zuffa Boxing" }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.locator("h3")).toContainText("Zuffa Boxing 12: Chris Billam-Smith vs. Cheavon Clarke");
      await expect(dialog.locator(".detail-time")).toHaveCount(0);
      await expect(dialog).toContainText("Saturday, November 7, 2026");
      await expect(dialog.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", /oldid=1382394457/);
      await expect(dialog).not.toContainText(/TBD|not published|missing|undisputed only/);
      expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      await page.screenshot({ path: `test-results/boxing-zuffa-${width}-${colorScheme}.png` });
      await dialog.getByRole("button", { name: "Close", exact: true }).click();
      await day.locator(".event-pill").filter({ hasText: "Boxing", hasNotText: "Zuffa" }).click();
      await expect(dialog.locator("h3")).toContainText("Pedro Taduran");
      await expect(dialog.locator("h3")).toContainText("Brandon Moreno");
      await expect(dialog.locator(".detail-time")).toHaveCount(0);
      await expect(dialog.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", "https://www.ibf-usba-boxing.com/schedule/");
      await dialog.getByRole("button", { name: "Close", exact: true }).click();
      await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
      await expect(dialog).toContainText("full WBA, WBC, IBF and WBO world title bouts");
      await expect(dialog).toContainText("regular/secondary and silver belts");
      const titles = dialog.locator("details").filter({ has: page.locator("summary", { hasText: "IBF" }) });
      await expect(titles).toBeVisible();
      await expect(dialog.locator("summary").filter({ hasText: "WBA" })).toHaveCount(1);
      await expect(dialog.locator("summary").filter({ hasText: "WBC" })).toHaveCount(1);
      await titles.locator("summary").click();
      await expect(titles.getByRole("link", { name: "Schedule facts; no data license granted" }).first()).toBeVisible();
      await expect(dialog).toContainText("CC BY-SA 4.0");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/boxing-about-${width}-${colorScheme}.png` });
    });
  });
}
