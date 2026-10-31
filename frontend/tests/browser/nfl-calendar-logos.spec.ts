import { expect, test } from "./test";
import { event, setup } from "./fixtures";

const team = (name: string) => ({ name, entity_type: "team", short_name: name.split(" ").at(-1) });
const game = (id: string, away = "Kansas City Chiefs", home = "Buffalo Bills", date = "2026-10-28", hour = 17) =>
  event(id, date, { title: `${away} at ${home}`, sport: "football", league: "NFL", country: "US",
    start_time_utc: `${date}T${hour}:00:00Z`, home_participant: team(home), away_participant: team(away) });
const games = Array.from({ length: 12 }, (_, index) => game(`game-${index}`, index % 2 ? "Dallas Cowboys" : "Kansas City Chiefs",
  index % 2 ? "New York Giants" : "Buffalo Bills", "2026-10-28", 10 + index));

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`NFL calendar logos ${colorScheme}`, () => {
    test.use({ colorScheme, reducedMotion: "reduce" });
    test("month packs complete matchups, counts omitted games, and responds across 700px", async ({ page }) => {
      await setup(page, [...games, game("singleton", undefined, undefined, "2026-10-29")]);
      const pill = page.locator("#day-2026-10-28 .event-pill");
      await expect(pill).toHaveCount(1);
      await expect(pill).toHaveAccessibleName(/Kansas City Chiefs at Buffalo Bills/);
      await expect(pill).toHaveAccessibleName(/Dallas Cowboys at New York Giants/);
      const visible = pill.locator(".nfl-month-matchups > .nfl-matchup");
      let desktopCount = 0;
      for (const width of [320, 699, 700, 1280, 2400, 700, 699, 1280]) {
        await page.setViewportSize({ width, height: 1000 });
        if (width < 700) {
          await expect(pill.locator(".nfl-phone-label")).toBeVisible();
          await expect(pill.locator(".nfl-phone-label")).toHaveText("NFL");
          await expect(pill.locator(".nfl-month-matchups")).toBeHidden();
          continue;
        }
        await expect(pill.locator(".nfl-phone-label")).toBeHidden();
        await expect(pill.locator(".nfl-month-matchups")).toBeVisible();
        await expect.poll(() => visible.count()).toBeGreaterThan(0);
        await expect.poll(async () => pill.locator(".nfl-month-matchups").evaluate((container) => {
          const pairs = [...container.querySelectorAll<HTMLElement>(":scope > .nfl-matchup")];
          const omitted = container.querySelector<HTMLElement>(":scope > .nfl-more");
          const bounds = container.getBoundingClientRect();
          return pairs.every((pair) => pair.getBoundingClientRect().right <= bounds.right + .5)
            && (!omitted || omitted.getBoundingClientRect().right <= bounds.right + .5)
            && pairs.length + Number(omitted?.textContent?.slice(1) || 0) === 12;
        })).toBe(true);
        const count = await visible.count();
        expect(count).toBeGreaterThan(0);
        await expect(pill.locator(".nfl-month-matchups > .nfl-more")).toHaveText(`+${12 - count}`);
        await expect(pill.locator(".nfl-month-matchups > .nfl-matchup > .nfl-calendar-team > img")).toHaveCount(count * 2);
        // Another complete matchup plus its updated count must exceed the available width.
        await expect.poll(() => pill.locator(".nfl-month-matchups").evaluate((container) => {
          const count = container.querySelectorAll(":scope > .nfl-matchup").length;
          const samples = container.querySelector(".nfl-measurements")!;
          const next = [...samples.querySelectorAll<HTMLElement>(".nfl-matchup")].slice(0, count + 1);
          const omitted = 12 - count - 1;
          const counter = omitted ? samples.querySelectorAll<HTMLElement>(".nfl-more")[omitted - 1].getBoundingClientRect().width : 0;
          return next.reduce((sum, pair) => sum + pair.getBoundingClientRect().width, 0)
            + (next.length - 1 + Number(omitted > 0)) * parseFloat(getComputedStyle(container).columnGap) + counter > container.clientWidth;
        })).toBe(true);
        if (width === 700) expect(count).toBe(1);
        if (width === 1280) desktopCount = count;
        if (width === 2400) expect(count).toBeGreaterThan(desktopCount);
      }
      await page.setViewportSize({ width: 5000, height: 1000 });
      await expect(visible).toHaveCount(12);
      await expect(pill.locator(".nfl-month-matchups > .nfl-more")).toHaveCount(0);
      await page.setViewportSize({ width: 1280, height: 1000 });
      await expect(pill.locator(".nfl-month-matchups > .nfl-more")).toBeVisible();
      const singleton = page.locator("#day-2026-10-29 .event-pill");
      await expect(singleton.locator(".nfl-month-matchups > .nfl-matchup")).toHaveCount(1);
      await expect(singleton.locator(".nfl-month-matchups > .nfl-more")).toHaveCount(0);
      await expect(singleton.locator(".country-flag")).toHaveCount(0);
      await page.screenshot({ path: `test-results/nfl-month-${colorScheme}.png` });
      await pill.click();
      await expect(page.locator(".sheet-event-row")).toHaveCount(12);
      await page.locator(".sheet-event-row").first().click();
      await expect(page.locator(".event-details h3")).toHaveText("Kansas City Chiefs at Buffalo Bills");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });

    for (const width of [320, 1280]) test(`day shows both local logos and team names at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      const requests: string[] = [];
      page.on("request", (request) => { if (request.resourceType() === "image") requests.push(request.url()); });
      await setup(page, [game("day-game"), game("second-game", "Dallas Cowboys", "New York Giants", "2026-10-28", 19),
        event("Other sport", undefined, { league: "UFC", start_time_utc: "2026-10-28T21:00:00Z", country: "JP" })]);
      await page.locator("#day-2026-10-28 .day-number").click();
      const pill = page.locator('[data-event-id="day-game"]');
      await expect(pill.locator(".nfl-logo")).toHaveCount(2);
      await expect(pill.locator(".nfl-team-name")).toHaveText(["Chiefs", "Bills"]);
      await expect(pill).toHaveAccessibleName(/Kansas City Chiefs at Buffalo Bills/);
      for (const logo of await pill.locator(".nfl-logo").all()) {
        await expect(logo).toBeVisible();
        expect(await logo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
      }
      await expect(page.locator('[data-event-id="Other sport"] .pill-text')).toHaveText("Other sport");
      await expect(page.locator('[data-event-id="Other sport"] .country-flag')).toBeVisible();
      await page.screenshot({ path: `test-results/nfl-day-${width}-${colorScheme}.png` });
      await pill.click();
      await expect(page.locator(".event-details h3")).toHaveText("Kansas City Chiefs at Buffalo Bills");
      expect(requests.filter((url) => url.includes("team-logos/")).every((url) => url.startsWith("http://127.0.0.1:"))).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}

test("missing local logos use exact supplied names and leave every matchup accessible", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  await setup(page, [game("unknown", "Supplied Away Team", "Buffalo Bills"),
    game("known", "Dallas Cowboys", "New York Giants", "2026-10-28", 19)]);
  const pill = page.locator("#day-2026-10-28 .event-pill");
  await expect(pill).toHaveAccessibleName(/Supplied Away Team at Buffalo Bills/);
  await expect(pill).toHaveAccessibleName(/Dallas Cowboys at New York Giants/);
  await page.locator("#day-2026-10-28 .day-number").click();
  const unknown = page.locator('[data-event-id="unknown"]');
  await expect(unknown.locator(".nfl-logo")).toHaveCount(1);
  await expect(unknown.locator(".nfl-team-name")).toHaveText(["Supplied Away Team", "Bills"]);
  await expect(unknown.locator("img")).toHaveAttribute("src", /team-logos\/BUF\.png$/);
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
    await expect(pill.locator(".nfl-logo")).toHaveCount(2);
    expect(await pill.evaluate((button) => {
      const bounds = button.getBoundingClientRect();
      return [...button.querySelectorAll(".nfl-logo")].every((logo) => {
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
        if (target.classList.contains("nfl-month-matchups")) active.add(this);
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
  await expect.poll(observerCount).toBe(0);
  await page.getByRole("dialog").getByRole("button", { name: "Football", exact: true }).click();
  await expect.poll(observerCount).toBe(1);
});
