import { expect, test } from "./test";
import { event, setup } from "./fixtures";

// Synthetic policy fixtures only: these are not claims of overseas MLS/NWSL/UFL games.
const cases = [
  { date: "2026-10-20", name: "domestic US", countries: ["US", "United States"], sharedForeignHost: false },
  { date: "2026-10-21", name: "domestic Canada", countries: ["CA", "Canada"], sharedForeignHost: false },
  { date: "2026-10-22", name: "shared foreign host", countries: ["ES", "Spain"], sharedForeignHost: true },
  { date: "2026-10-23", name: "missing host", countries: ["ES", null], sharedForeignHost: false },
  { date: "2026-10-24", name: "unknown host", countries: ["ES", "ZZ"], sharedForeignHost: false },
  { date: "2026-10-25", name: "mixed hosts", countries: ["ES", "FR"], sharedForeignHost: false },
];

for (const league of ["MLS", "NWSL", "UFL"]) for (const width of [375, 1280]) {
  test(`${league} synthetic foreign-host flags agree in month and day at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await setup(page, cases.flatMap(({ date, name, countries }) => countries.map((country, index) =>
      event(`Synthetic ${league} ${name} ${index + 1}`, date, {
        league, sport: league === "UFL" ? "football" : "soccer", country,
        country_source_url: `https://example.com/synthetic-host/${league}/${date}/${index + 1}`,
        country_checked_date: "2026-10-28",
      }))));

    for (const { date, sharedForeignHost } of cases) {
      const pill = page.locator(`#day-${date} .event-pill`);
      await expect(pill).toHaveCount(1);
      const flag = pill.locator(".country-flag");
      await expect(flag).toHaveCount(sharedForeignHost ? 1 : 0);
      if (sharedForeignHost) {
        await expect(flag).toHaveAttribute("aria-label", "Spain");
        await expect(flag).toHaveText("🇪🇸");
        if (width < 700) await expect(flag).toBeHidden();
        else await expect(flag).toBeVisible();
      }
    }

    // Open the same day groups without changing their source facts or opening a popup.
    for (const { date, sharedForeignHost } of cases) {
      await page.locator(`#day-${date} .day-number`).click();
      await expect(page.locator(".day-timeline-stage")).toBeVisible();
      const pill = page.locator(".all-day-strip .event-pill");
      await expect(pill).toHaveCount(1);
      const flag = pill.locator(".country-flag");
      await expect(flag).toHaveCount(sharedForeignHost ? 1 : 0);
      if (sharedForeignHost) {
        await expect(flag).toHaveAttribute("aria-label", "Spain");
        await expect(flag).toBeVisible();
      }
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await page.getByRole("button", { name: "Back to October", exact: true }).click();
    }
  });
}
