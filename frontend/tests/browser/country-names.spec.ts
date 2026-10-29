import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { setup } from "./fixtures";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = existsSync(`${root}.venv/bin/python`) ? `${root}.venv/bin/python` : "python";
const events = JSON.parse(execFileSync(python, ["-c", `
import json
from kickoff import feeds
from kickoff.web import _event_payload
feeds.get_json = lambda *_args, **_kwargs: {'events': [{
    'id': str(index), 'date': f'2026-10-{day}T17:00Z', 'name': country + ' card',
    'competitions': [{'venue': {'address': {'country': country}}}],
} for index, (day, country) in enumerate([(28, 'Croatia'), (29, 'Rwanda')])]}
print(json.dumps([_event_payload(event) for event in feeds.FEEDS['UFC'][1](2026)]))
`], { cwd: root, encoding: "utf8" }));

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`source country names ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("new producer country names render through the existing country identity path", async ({ page }) => {
      expect(events.map((event: { country: string }) => event.country)).toEqual(["Croatia", "Rwanda"]);
      await setup(page, events);
      for (const [day, country, flag] of [[28, "Croatia", "🇭🇷"], [29, "Rwanda", "🇷🇼"]]) {
        const cell = page.locator(`#day-2026-10-${day}`);
        const monthFlag = cell.locator(".event-pill .country-flag");
        await expect(monthFlag).toHaveAttribute("aria-label", country as string);
        await expect(monthFlag).toHaveText(flag as string);
        expect(await monthFlag.isVisible()).toBe(width >= 700);
        await cell.locator(".day-number").click();
        const pill = page.locator(".timeline-events .event-pill");
        await expect(pill.locator(".country-flag")).toBeVisible();
        await expect(pill.locator(".country-flag")).toHaveText(flag as string);
        await expect(pill.locator(".pill-text")).toHaveText(`${country} card`);
        await pill.click();
        await expect(page.getByRole("dialog").getByRole("img", { name: `Host country: ${country}`, exact: true })).toBeVisible();
        await page.screenshot({ path: `test-results/country-${country}-${width}-${colorScheme}.png` });
        await page.keyboard.press("Escape");
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await page.getByRole("button", { name: "Back to October", exact: true }).click();
      }
    });
  });
}
