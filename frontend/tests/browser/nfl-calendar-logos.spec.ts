import { expect, test } from "./test";
import { event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";

const team = (name: string, role: string) => ({ name, role, entity_type: "team", short_name: name.split(" ").at(-1),
  ...(!name.startsWith("Supplied") && { logo_url: teamLogoUrl(`/i/teamlogos/nfl/500/${name.split(" ").at(-1)!.toLowerCase()}.png`),
    logo_source_url: "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/1", logo_checked_date: "2026-11-03" }) });
test.beforeEach(async ({ page }) => { await mockTeamLogos(page); });
const game = (id: string, away = "Kansas City Chiefs", home = "Buffalo Bills", date = "2026-10-28", hour = 17) =>
  event(id, date, { title: `${away} at ${home}`, sport: "football", league: "NFL", country: "US",
    start_time_utc: `${date}T${hour}:00:00Z`, participants: [team(home, "home"), team(away, "away")] });
const games = Array.from({ length: 12 }, (_, index) => game(`game-${index}`, index % 2 ? "Dallas Cowboys" : "Kansas City Chiefs",
  index % 2 ? "New York Giants" : "Buffalo Bills", "2026-10-28", 10 + index));

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`NFL calendar logos ${colorScheme}`, () => {
    test.use({ colorScheme, reducedMotion: "reduce" });
    test("heavy weekdays keep one league label and singleton phones show the actual pair", async ({ page }) => {
      await setup(page, [...games, game("singleton", undefined, undefined, "2026-10-29")]);
      const pill = page.locator("#day-2026-10-28 .event-pill");
      await expect(pill).toHaveCount(1);
      await expect(pill).toHaveAccessibleName("NFL, 12 events, Wednesday, October 28, 2026");
      await expect(pill.locator(".month-desktop-pairs")).toHaveCount(0);
      const singleton = page.locator("#day-2026-10-29 .event-pill");
      for (const width of [320, 699, 700, 1280]) {
        await page.setViewportSize({ width, height: 1000 });
        await expect(pill.locator(width < 700 ? ".pill-code" : ".pill-label")).toHaveText("NFL");
        if (width < 700) {
          await expect(singleton.locator(".sport-icon")).toBeHidden();
          await expect(singleton.locator(".month-phone-single img")).toHaveCount(2);
          await expect(singleton.locator(".month-phone-single")).toBeVisible();
        } else await expect(singleton.locator(".month-phone-single")).toBeHidden();
      }
      await pill.press("Enter");
      await expect(page.locator(".sheet-event-row")).toHaveCount(12);
      await page.locator(".sheet-event-row").first().click();
      await expect(page.locator(".event-details h3")).toHaveText("Kansas City Chiefs at Buffalo Bills");
    });

    for (const width of [320, 1280]) test(`day shows both ESPN logos and team names at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      const requests: string[] = [];
      page.on("request", (request) => { if (request.resourceType() === "image") requests.push(request.url()); });
      await setup(page, [game("day-game"), game("second-game", "Dallas Cowboys", "New York Giants", "2026-10-28", 19),
        event("Other sport", undefined, { league: "UFC", start_time_utc: "2026-10-28T21:00:00Z", country: "JP" })]);
      await page.locator("#day-2026-10-28 .day-number").click();
      const pill = page.locator('[data-event-id="day-game"]');
      await expect(pill.locator(".team-logo")).toHaveCount(2);
      await expect(pill.locator(".day-pill-name")).toHaveText(["Chiefs", "Bills"]);
      await expect(pill).toHaveAccessibleName(/Kansas City Chiefs at Buffalo Bills/);
      for (const logo of await pill.locator(".team-logo").all()) {
        await expect(logo).toBeVisible();
        expect(await logo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
      }
      await expect(page.locator('[data-event-id="Other sport"] .pill-text')).toHaveText("Other sport");
      await expect(page.locator('[data-event-id="Other sport"] .country-flag')).toBeVisible();
      await page.screenshot({ path: `test-results/nfl-day-${width}-${colorScheme}.png` });
      await pill.click();
      await expect(page.locator(".event-details h3")).toHaveText("Kansas City Chiefs at Buffalo Bills");
      expect(requests.filter((url) => url.includes("/combiner/")).every((url) => url.startsWith("https://a.espncdn.com/") && new URL(url).searchParams.get("w") === "56")).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}

test("unmatched teams use exact supplied names and leave every matchup accessible", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  await setup(page, [game("unknown", "Supplied Away Team", "Buffalo Bills"),
    game("known", "Dallas Cowboys", "New York Giants", "2026-10-28", 19)]);
  const pill = page.locator("#day-2026-10-28 .event-pill");
  await expect(pill).toHaveAccessibleName(/Supplied Away Team at Buffalo Bills/);
  await expect(pill).toHaveAccessibleName(/Dallas Cowboys at New York Giants/);
  await page.locator("#day-2026-10-28 .day-number").click();
  const unknown = page.locator('[data-event-id="unknown"]');
  await expect(unknown.locator(".team-logo")).toHaveCount(1);
  await expect(unknown.locator(".day-pill-name")).toHaveText(["Team", "Bills"]);
  await expect(unknown.locator("img")).toHaveAttribute("src", /combiner\/i\?img=.*bills.png&w=56&h=56$/);
  await unknown.click();
  await expect(page.locator(".event-details h3")).toHaveText("Supplied Away Team at Buffalo Bills");
});

test("narrow simultaneous NFL pills preserve both logos and the existing overflow popup", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setup(page, Array.from({ length: 5 }, (_, index) => game(`overlap-${index}`)));
  await page.locator("#day-2026-10-28 .day-number").click();
  await expect(page.locator(".timeline-events > .event-pill")).toHaveCount(2);
  for (const pill of await page.locator(".timeline-events > .event-pill").all()) {
    await expect(pill.locator(".team-logo")).toHaveCount(2);
    expect(await pill.evaluate((button) => {
      const bounds = button.getBoundingClientRect();
      return [...button.querySelectorAll(".team-logo")].every((logo) => {
        const rect = logo.getBoundingClientRect();
        return rect.left >= bounds.left && rect.right <= bounds.right;
      });
    })).toBe(true);
    await expect(pill).toHaveAccessibleName(/Kansas City Chiefs at Buffalo Bills/);
  }
  await expect(page.locator(".timeline-more")).toHaveText("+3");
  await page.locator(".timeline-more").click();
  await expect(page.locator(".sheet-event-row")).toHaveCount(3);
});

test("NFL measurement observers disconnect when the interest removes the pills", async ({ page }) => {
  await page.addInitScript(() => {
    const active = new Set<ResizeObserver>();
    const Native = ResizeObserver;
    Object.assign(window, { nflObservers: active });
    window.ResizeObserver = class extends Native {
      observe(target: Element, options?: ResizeObserverOptions) {
        if (target.classList.contains("month-desktop-pairs")) active.add(this);
        super.observe(target, options);
      }
      disconnect() { active.delete(this); super.disconnect(); }
    };
  });
  await setup(page, [game("cleanup"), event("UFC", undefined, { league: "UFC" })]);
  const observerCount = () => page.evaluate(() => (window as unknown as { nflObservers: Set<ResizeObserver> }).nflObservers.size);
  await expect.poll(observerCount).toBe(1);
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Football", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Show my calendar", exact: true }).click();
  await expect.poll(observerCount).toBe(0);
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Football", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Show my calendar", exact: true }).click();
  await expect.poll(observerCount).toBe(1);
});
