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
print(json.dumps([_event_payload(event) for event in load_reviewed_schedules(Path('data/reviewed'), 2026)[0]
                  if event.league == 'LPGA_TOUR']))
`], { cwd: root, encoding: "utf8" }));

for (const width of [320, 390, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`LPGA country flags ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("reviewed state locations show US after titles and retain their source", async ({ page }) => {
      expect(events.filter((event: { country: string }) => event.country === "US")).toHaveLength(16);
      await setup(page, events, { now: "2026-02-01T17:00:00Z" });
      const cell = page.locator("#day-2026-02-01");
      const flag = cell.locator(".event-pill .country-flag");
      await expect(flag).toHaveAttribute("aria-label", "United States");
      await expect(flag).toHaveText("🇺🇸");
      expect(await flag.isVisible()).toBe(width >= 700);
      await cell.locator(".day-number").click();
      const pill = page.locator(".all-day-strip .event-pill");
      await expect(pill.locator(".pill-text")).toHaveText("Hilton Grand Vacations Tournament of Champions");
      await expect(pill.locator(".country-flag")).toBeVisible();
      await expect(pill.locator(".country-flag")).toHaveText("🇺🇸");
      await pill.click();
      const sheet = page.getByRole("dialog");
      await expect(sheet.getByRole("img", { name: "Host country: United States", exact: true })).toBeVisible();
      await expect(sheet.getByRole("link", { name: "Schedule source", exact: false }))
        .toHaveAttribute("href", "https://en.wikipedia.org/w/index.php?title=2026_LPGA_Tour&oldid=1372529225");
      await page.screenshot({ path: `test-results/lpga-us-${width}-${colorScheme}.png` });
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Back to February", exact: true }).click();
      await agendaToggle(page).click();
      const title = page.locator(".agenda-title");
      await expect(title).toContainText("Hilton Grand Vacations Tournament of Champions");
      await expect(title.locator(".country-flag")).toHaveText("🇺🇸");
      expect(await title.evaluate((element) => element.firstChild?.textContent)).toBe("Hilton Grand Vacations Tournament of Champions");
    });
  });
}
