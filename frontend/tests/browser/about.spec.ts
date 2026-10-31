import { expect, test } from "./test";
import { event, setup } from "./fixtures";
import type { SourceNotice } from "../../src/types";

const notice = "Schedule facts keep their source terms. Software is MIT.";
const source = (kind: string, name: string, url: string, license = "Schedule facts; no data license granted", license_url = "https://example.com/terms"): SourceNotice => ({ kind, name, url, license, license_url });
const sources = [
  source("openfootball", "openfootball contributors", "https://github.com/openfootball/football.json", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
  source("f1db", "F1DB and contributors", "https://github.com/f1db/f1db", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
  source("espn", "ESPN", "https://www.espn.com/"),
  ...Array.from({ length: 52 }, (_, i) => source("world_climbing", `World Climbing: event ${i}`, `https://www.worldclimbing.com/events/${i}`)),
  source("weightlifting", "Worlds", "https://iwf.sport/events/calendar/"),
  source("weightlifting", "Europe", "https://iwf.sport/events/calendar/"),
  source("weightlifting", "Junior", "https://ewf.sport/junior/", "Schedule facts", "https://ewf.sport/terms/"),
  source("wikipedia", "Wikipedia contributors: boxing", "https://en.wikipedia.org/w/index.php?title=Boxing&oldid=1", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
  source("wikipedia", "Wikipedia contributors: combat", "https://en.wikipedia.org/w/index.php?title=Combat&oldid=2", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
];
for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`About ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("requested order, publisher rows, exact page counts, full lists and licenses", async ({ page }) => {
      await setup(page, [event("Match")], { metadata: { sources, data_license_notice: notice } });
      await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
      const sheet = page.getByRole("dialog"), about = sheet.locator(".about");
      await expect(about.locator(":scope > p")).toHaveText(["A sports calendar by snowball.", "Updated 2026-10-27 · Local time · Chicago"]);
      await expect(about.locator("h3")).toHaveText(["Coverage", "Sources", "Privacy"]);
      const coverage = sheet.getByRole("region", { name: "Coverage", exact: true });
      await expect(coverage.locator("p")).toHaveCount(4);
      await expect(coverage).toContainText("Dates and times can change.");
      await expect(coverage).toContainText("Rounds are all-day; past rounds show final tournament results");
      await expect(coverage).toContainText("full WBA, WBC, IBF and WBO world title bouts");
      await expect(coverage.getByRole("link", { name: "Coverage details ↗" })).toHaveAttribute("href", "https://github.com/snowball-projects/kickoff/tree/main/data/reviewed");
      const publishers = sheet.getByRole("region", { name: "Sources", exact: true });
      await expect(publishers.locator(".about-source")).toHaveCount(6);
      await expect(publishers.locator("summary")).toHaveText(["World Climbing · 52 event pages", "Weightlifting federations · 2 event pages", "Wikipedia · 2 event pages"]);
      await expect(publishers.getByRole("link", { name: "CC0 1.0" })).toHaveAttribute("href", "https://creativecommons.org/publicdomain/zero/1.0/");
      await expect(publishers.getByRole("link", { name: "CC BY 4.0", exact: true })).toHaveAttribute("href", "https://creativecommons.org/licenses/by/4.0/");
      for (const summary of await publishers.locator("summary").all()) {
        await summary.focus(); await summary.press("Enter");
      }
      const climbing = publishers.locator("details").filter({ has: page.locator("summary", { hasText: "World Climbing" }) });
      await expect(climbing.locator("li")).toHaveCount(52);
      await expect(climbing.getByRole("link", { name: "World Climbing: event 51", exact: true })).toHaveAttribute("href", sources[54].url);
      const lifting = publishers.locator("details").filter({ has: page.locator("summary", { hasText: "Weightlifting" }) });
      await expect(lifting.locator("li")).toHaveCount(2);
      await expect(lifting.getByRole("link", { name: "Worlds · Europe", exact: true })).toHaveAttribute("href", "https://iwf.sport/events/calendar/");
      await expect(lifting.getByRole("link", { name: "Schedule facts", exact: true })).toHaveAttribute("href", "https://ewf.sport/terms/");
      const wiki = publishers.locator("details").filter({ has: page.locator("summary", { hasText: "Wikipedia" }) });
      await expect(wiki.locator("li")).toHaveCount(2);
      await expect(wiki.getByRole("link", { name: "CC BY-SA 4.0", exact: true })).toHaveCount(2);
      await expect(publishers.locator(":scope > :last-child")).toHaveText(notice);
      await expect(publishers.locator(".about-license-notice")).toHaveCSS("font-size", "11px");
      await expect(sheet.getByRole("region", { name: "Privacy", exact: true }).locator("p")).toHaveCount(2);
      await expect(about.getByRole("navigation", { name: "Project links" }).getByRole("link")).toHaveText(["Source", "Licenses", "Operations"]);
      await expect(about).not.toContainText(/unavailable|incomplete|empty day|America\/Chicago/);
      await expect.poll(() => sheet.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      for (const details of await publishers.locator("details").all()) await details.locator("summary").click();
      await about.scrollIntoViewIfNeeded();
      await sheet.locator(".sheet-body").evaluate((el) => { el.scrollTop = 0; });
      await page.screenshot({ path: `test-results/about-${width}-${colorScheme}.png` });
    });
  });
}

test("an unknown update date contributes no missing-data sentence", async ({ page }) => {
  await setup(page, [event("Match")], { metadata: { updated_at: undefined } });
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  await expect(page.locator(".about-updated")).toHaveText("Local time · Chicago");
  await expect(page.getByRole("dialog")).not.toContainText(/unavailable|undefined|Updated/);
});
