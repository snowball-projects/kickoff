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
  test(`${league} synthetic foreign-host flags group in month and stay per event in day at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await setup(page, cases.flatMap(({ date, name, countries }) => countries.map((country, index) =>
      event(`Synthetic ${league} ${name} ${index + 1}`, date, {
        title: `Synthetic ${index + 1}`, league, sport: league === "UFL" ? "football" : "soccer", country,
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

    // Day pills show each fixture's known host, including on mixed/unknown-host days.
    for (const { date, countries } of cases) {
      await page.locator(`#day-${date} .day-number`).click();
      await expect(page.locator(".day-timeline-stage")).toBeVisible();
      await expect(page.locator(".all-day-strip .event-pill")).toHaveCount(2);
      for (const [index, country] of countries.entries()) {
        const pill = page.locator(".all-day-strip").getByRole("button", { name: `Synthetic ${index + 1}`, exact: true });
        const flag = pill.locator(".country-flag");
        const foreign = country === "ES" || country === "Spain" ? { name: "Spain", flag: "🇪🇸" }
          : country === "FR" ? { name: "France", flag: "🇫🇷" } : null;
        await expect(flag).toHaveCount(foreign ? 1 : 0);
        if (foreign) {
          await expect(flag).toHaveAttribute("aria-label", foreign.name);
          await expect(flag).toHaveText(foreign.flag);
          await expect(flag).toBeVisible();
        }
      }
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await page.getByRole("button", { name: "Back to October", exact: true }).click();
    }
  });
}
