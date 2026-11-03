import { expect, test } from "./test";
import { event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";

const leagues = [
  ["NBA", "basketball", "away"], ["NFL", "football", "away"], ["MLB", "baseball", "away"], ["NHL", "hockey", "away"],
  ["EPL", "soccer", "home"], ["SIX_NATIONS", "rugby", "home"], ["IPL", "cricket", "home"],
];
const team = (id: string, role: string | null) => ({ name: `Full ${id} team`, short_name: id, role, entity_type: "team",
  logo_url: teamLogoUrl(`/i/teamlogos/nfl/500/${id}.png`), logo_source_url: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams", logo_checked_date: "2026-11-03" });
const game = (id: string, date = "2026-10-28", league = "NBA", sport = "basketball", fields = {}) => event(id, date, {
  title: `Original source ${id}`, league, sport, participants: [team(`${id}-home`, "home"), team(`${id}-away`, "away")], ...fields,
});

test.beforeEach(async ({ page }) => { await page.emulateMedia({ reducedMotion: "reduce" }); await mockTeamLogos(page); });

for (const [league, sport, first] of leagues) for (const width of [320, 1280]) {
  test(`${league} shares one ordered month pill for one through four games at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page, [1, 2, 3, 4].flatMap((count) => Array.from({ length: count }, (_, index) =>
      game(`${count}-${index}`, `2026-10-${27 + count}`, league, sport))));
    for (const count of [1, 2, 3, 4]) {
      const pill = page.locator(`#day-2026-10-${27 + count} .event-pill`);
      await expect(pill).toHaveCount(1);
      if (count === 1) {
        await expect(pill).toHaveAccessibleName(new RegExp(`Full 1-0-${first} team`));
        if (width < 700) {
          await expect(pill.locator(".sport-icon")).toBeHidden();
          await expect(pill.locator(".pill-text")).toBeHidden();
          await expect(pill.locator(".month-phone-single img")).toHaveCount(2);
          await expect(pill.locator(".month-phone-single .month-team-fallback")).toHaveText(
            [`1-0-${first}`, `1-0-${first === "away" ? "home" : "away"}`]);
        } else {
          await expect(pill.locator(".month-desktop-pairs > .month-pair")).toHaveCount(1);
          await expect(pill.locator(".month-desktop-pairs > .month-pair .month-team-fallback")).toHaveText(
            [`1-0-${first}`, `1-0-${first === "away" ? "home" : "away"}`]);
        }
      } else if (width < 700) {
        await expect(pill.locator(".sport-icon")).toBeVisible();
        await expect(pill.locator(".pill-code")).toBeVisible();
        await expect(pill.locator(".month-phone-single")).toHaveCount(0);
      }
      if (count === 4) {
        await expect(pill.locator(".month-desktop-pairs")).toHaveCount(0);
        await expect(pill).not.toHaveAccessibleName(/Full 4-/);
        await expect(pill).toHaveAccessibleName(/4 events/);
      }
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("measured light pairs and +N change together on resize without fetching hidden measurements", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 1000 });
  const requested: string[] = [];
  page.on("request", request => { if (request.url().startsWith("https://a.espncdn.com/")) requested.push(request.url()); });
  await setup(page, [0, 1, 2].map((index) => game(`fit-${index}`, undefined, "NFL", "football")));
  const pill = page.locator("#day-2026-10-28 .event-pill"), container = pill.locator(".month-desktop-pairs");
  for (const width of [700, 1280, 2400, 700]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect.poll(() => container.evaluate((el) => {
      const pairs = [...el.querySelectorAll<HTMLElement>(":scope > .month-pair")];
      const more = el.querySelector<HTMLElement>(":scope > .month-more");
      const bounds = el.getBoundingClientRect();
      return pairs.length + Number(more?.textContent?.slice(1) || 0) === 3
        && pairs.every(pair => pair.getBoundingClientRect().right <= bounds.right + .5)
        && (!more || more.getBoundingClientRect().right <= bounds.right + .5);
    })).toBe(true);
    const shown = await container.locator(":scope > .month-pair").count();
    if (width === 2400) expect(shown).toBe(3);
    if (shown < 3) expect(await container.evaluate((el) => {
      const count = el.querySelectorAll(":scope > .month-pair").length;
      const samples = el.querySelector(".month-measurements")!;
      const pairs = [...samples.querySelectorAll<HTMLElement>(".month-pair")].slice(0, count + 1);
      const remaining = 3 - pairs.length;
      const counter = remaining ? samples.querySelectorAll<HTMLElement>(".month-more")[remaining - 1].getBoundingClientRect().width : 0;
      return pairs.reduce((sum, pair) => sum + pair.getBoundingClientRect().width, 0)
        + (pairs.length - 1 + Number(remaining > 0)) * parseFloat(getComputedStyle(el).columnGap)
        + counter > el.getBoundingClientRect().width;
    })).toBe(true);
    for (const image of await pill.locator(".month-measurements img").all()) await expect(image).not.toHaveAttribute("src");
  }
  expect(requested.every(url => new URL(url).searchParams.get("w") === "56")).toBe(true);
});

for (const timezoneId of ["America/Chicago", "Asia/Tokyo"]) test.describe(`Sunday viewer date ${timezoneId}`, () => {
  test.use({ timezoneId });
  test("only the unique latest reliable kickoff supplies the NFL pair", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 1000 });
    const utc = timezoneId === "Asia/Tokyo" ? ["2026-10-31T23:00:00Z", "2026-11-01T02:00:00Z"]
      : ["2026-11-01T18:00:00Z", "2026-11-02T01:00:00Z"];
    await setup(page, utc.map((start_time_utc, index) => game(`sunday-${index}`, "2026-11-01", "NFL", "football", { start_time_utc })));
    const pill = page.locator("#day-2026-11-01 .event-pill");
    await pill.scrollIntoViewIfNeeded();
    await expect(pill).toHaveCount(1);
    await expect(pill.locator(".month-desktop-pairs > .month-pair")).toHaveAttribute("data-matchup-id", "sunday-1");
    await expect(pill.locator(".month-desktop-pairs > .month-pair .month-team-fallback")).toHaveText(["sunday-1-away", "sunday-1-home"]);
    await expect(pill).toHaveAccessibleName(/Full sunday-1-away team at Full sunday-1-home team/);
    await expect(pill).not.toHaveAccessibleName(/Full sunday-0-/);
    await pill.press("Enter");
    await expect(page.locator(".sheet-event-row")).toHaveCount(2);
    await page.locator(".sheet-event-row").filter({ hasText: "Original source sunday-0" }).click();
    await expect(page.locator(".event-details h3")).toHaveText("Full sunday-0-away team at Full sunday-0-home team");
  });
});

for (const uncertainty of ["unknown", "tie"]) test(`Sunday ${uncertainty} keeps generic NFL rather than guessing`, async ({ page }) => {
  await setup(page, [game("known", "2026-11-01", "NFL", "football", { start_time_utc: "2026-11-01T18:00:00Z" }),
    game("uncertain", "2026-11-01", "NFL", "football", { start_time_utc: uncertainty === "tie" ? "2026-11-01T18:00:00Z" : null })]);
  const pill = page.locator("#day-2026-11-01 .event-pill");
  await pill.scrollIntoViewIfNeeded();
  await expect(pill.locator(".pill-label")).toHaveText("NFL");
  await expect(pill.locator(".month-desktop-pairs")).toHaveCount(0);
});

test("phone singleton fits 50px and actual320px cells, roleless pairs and missing opponents stay truthful", async ({ page }) => {
  await setup(page, [game("roles", undefined, "IPL", "cricket", { title: "Source abbreviations only", participants: [team("First full source", null), team("Second full source", null)] }),
    game("appointment", "2026-10-29", "COLLEGE_FOOTBALL", "football", { participants: [team("Only home", "home")] })]);
  const pill = page.locator("#day-2026-10-28 .event-pill");
  for (const width of [350, 320, 699, 700]) {
    await page.setViewportSize({ width, height: 1000 });
    if (width < 700) {
      const bounds = await pill.boundingBox();
      await expect(pill.locator(".month-phone-single img")).toHaveCount(2);
      for (const image of await pill.locator(".month-phone-single img").all()) {
        const rect = (await image.boundingBox())!;
        expect(rect.width).toBe(14);
        expect(rect.x).toBeGreaterThanOrEqual(bounds!.x);
        expect(rect.x + rect.width).toBeLessThanOrEqual(bounds!.x + bounds!.width);
      }
      await expect(pill.locator(".sport-icon")).toBeHidden();
      await expect(page.locator("#day-2026-10-29 .sport-icon")).toBeVisible();
      await expect(page.locator("#day-2026-10-29 .pill-code")).toHaveText("CFB");
    } else await expect(pill.locator(".sport-icon")).toBeVisible();
    await expect(pill).toHaveAccessibleName(/Source abbreviations only; Full First full source team; Full Second full source team/);
  }
});

for (const missing of ["both-missing", "partial", "one-fails", "all-fail"]) test(`${missing} singleton restores the league pill and keeps full source names`, async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 1000 });
  await page.route("https://a.espncdn.com/**", route => {
    const bad = missing === "all-fail" || (missing === "one-fails" && new URL(route.request().url()).searchParams.get("img")!.includes("away"));
    return bad ? route.fulfill({ status: 404, body: "image unavailable" }) : route.fulfill({ contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" />' });
  });
  const home = team("home", "home"), away = team("away", "away");
  const participants = [home, away].map((p, index) => ({ ...p,
    ...(missing === "both-missing" || (missing === "partial" && index === 0) ? { logo_url: undefined } : {}) }));
  const sourceTitle = "Source: Full away team at Full home team";
  await setup(page, [game("Source title stays intact", undefined, "NBA", "basketball", { participants, title: sourceTitle })]);
  const pill = page.locator("#day-2026-10-28 .event-pill");
  await expect(pill).toHaveAccessibleName(/Full away team at Full home team/);
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(pill).not.toHaveClass(/\bmonth-single\b/);
    await expect(pill.locator(".month-phone-single")).toHaveCount(0);
    await expect(pill.locator(".sport-icon")).toBeVisible();
    await expect(pill.locator(".pill-code")).toBeVisible();
    await expect(pill.locator(".pill-code")).toHaveText("NBA");
    await expect(pill).toHaveAccessibleName(/Full away team at Full home team/);
    expect(await pill.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await pill.click();
    await expect(page.locator(".event-details h3")).toHaveText(sourceTitle);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  if (missing === "both-missing") await expect(pill.locator(".month-desktop-pairs")).toHaveCount(0);
  else {
    await expect(pill.locator(".month-desktop-pairs > .month-pair")).toHaveCount(1);
    for (const image of await pill.locator(".month-measurements img").all()) await expect(image).not.toHaveAttribute("src");
  }
  await pill.click();
  await expect(page.locator(".event-details h3")).toHaveText(sourceTitle);
});

test("offscreen month pairs request nothing before intersection and measurement clones never acquire src", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  const requested: string[] = [];
  page.on("request", request => { if (request.url().startsWith("https://a.espncdn.com/")) requested.push(request.url()); });
  await setup(page, [game("near"), game("far", "2027-02-10")]);
  const future = page.locator("#day-2027-02-10 .event-pill");
  await expect(future.locator(".month-desktop-pairs > .month-pair")).toHaveCount(1);
  for (const image of await future.locator("img").all()) await expect(image).not.toHaveAttribute("src");
  expect(requested.some(url => new URL(url).searchParams.get("img")!.includes("far-"))).toBe(false);
  await future.scrollIntoViewIfNeeded();
  for (const image of await future.locator(".month-desktop-pairs > .month-pair img").all()) await expect(image).toHaveJSProperty("naturalWidth", 56);
  for (const image of await future.locator(".month-measurements img").all()) await expect(image).not.toHaveAttribute("src");
  expect(requested.filter(url => new URL(url).searchParams.get("img")!.includes("far-"))).toHaveLength(2);
});
