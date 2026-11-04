import { expect, test } from "./test";
import { event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";

const team = (name: string, role: string, logo = true) => ({ name: `${name} full source name`, short_name: name,
  role, entity_type: "team", ...(logo && { logo_url: teamLogoUrl(`/i/teamlogos/nfl/500/${name}.png`) }) });
const fixture = (id: string, sport = "soccer", league = "EPL", fields = {}) => event(id, undefined, {
  title: `${id} source title at neutral venue`, sport, league, country: "England",
  participants: [team("Home", "home"), team("Away", "away")], ...fields,
});
const openDay = async (page: Parameters<typeof setup>[0]) => page.locator("#day-2026-10-28 .day-number").click();

test.use({ reducedMotion: "reduce" });
test.beforeEach(async ({ page }) => mockTeamLogos(page));

test("all seven team sports use source short names, role order, and unchanged popup titles", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  const sports = [["football", "NFL"], ["basketball", "NBA"], ["baseball", "MLB"], ["hockey", "NHL"],
    ["soccer", "EPL"], ["rugby", "TOP_14"], ["cricket", "IPL"]];
  await setup(page, sports.map(([sport, league]) => fixture(league, sport, league)));
  await openDay(page);
  for (const [sport, league] of sports) {
    const pill = page.locator(`.all-day-strip [data-event-id="${league}"]`);
    await expect(pill.locator(".day-pill-name")).toHaveText(["soccer", "rugby", "cricket"].includes(sport) ? ["Home", "Away"] : ["Away", "Home"]);
    await expect(pill.locator(".day-pill-separator")).toHaveText(["soccer", "rugby", "cricket"].includes(sport) ? "vs" : "at");
    await expect(pill.locator(".team-logo")).toHaveCount(2);
    await pill.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".event-details h3")).toContainText(league === "NFL" ? "Away full source name at Home full source name" : `${league} source title at neutral venue`);
    await page.keyboard.press("Escape");
    await expect(pill).toBeFocused();
  }
});

test("roleless cricket, undecided fixtures and individual sessions keep source facts without scores", async ({ page }) => {
  await setup(page, [fixture("roleless", "cricket", "IPL", { participants: [team("Home", ""), team("Away", "")] }),
    fixture("undecided", "football", "COLLEGE_FOOTBALL", { participants: [team("Home", "home")] }),
    event("session", undefined, { sport: "weightlifting", league: "IWF_WORLDS", country: "China",
      title: "IWF Worlds · Women's 69 kg, Group D" }),
    fixture("finished", "soccer", "EPL", { status: "finished", participants: [{ ...team("Home", "home"), final_score: 5 }, { ...team("Away", "away"), final_score: 3 }] })]);
  await openDay(page);
  for (const id of ["roleless", "undecided"]) {
    const pill = page.locator(`[data-event-id="${id}"]`);
    await expect(pill.locator(".pill-text")).toHaveText(`${id} source title at neutral venue`);
    await expect(pill.locator(".day-pill-matchup")).toHaveCount(0);
    await pill.click();
    await expect(page.locator(".event-details h3")).toContainText(`${id} source title at neutral venue`);
    await page.keyboard.press("Escape");
  }
  await expect(page.locator('[data-event-id="session"] .day-pill-line')).toHaveText("IWF Worlds·Women's 69 kg, Group D🇨🇳");
  await expect(page.locator('[data-event-id="finished"]')).not.toContainText("5");
  await expect(page.locator('[data-event-id="finished"]')).not.toContainText("3");
});

for (const width of [320, 375, 1280]) test(`two visible lanes plus overflow retain clocks and logos at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  const events = [2, 3, 4].flatMap((count, group) => Array.from({ length: count }, (_, index) => fixture(`overlap-${count}-${index}`, "soccer", "EPL", {
    start_time_utc: `2026-10-28T${17 + group}:00:00Z`,
  })));
  await setup(page, events);
  await openDay(page);
  await expect(page.locator(".timeline-events > .event-pill")).toHaveCount(6);
  await expect(page.locator(".timeline-more")).toHaveText(["+1", "+2"]);
  for (const pill of await page.locator(".timeline-events > .event-pill").all()) {
    await expect(pill.locator(".team-logo")).toHaveCount(2);
    expect(await pill.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return [...el.querySelectorAll(".team-logo")].every((logo) => logo.getBoundingClientRect().right <= rect.right);
    })).toBe(true);
  }
  expect(await page.locator('.timeline-events [data-event-id="overlap-3-0"]').evaluate((el: HTMLElement) => el.style.top)).toBe("1040px");
  await page.locator(".timeline-more").first().click();
  await expect(page.locator(".event-details h3")).toContainText("overlap-3-2 source title at neutral venue");
  await page.keyboard.press("Escape");
  await expect(page.locator(".timeline-more").first()).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("measured reductions keep logos, restore failed-logo names, and respond to resize and font loading", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 });
  await setup(page, [fixture("resize", "soccer", "UEFA_WOMENS_CHAMPIONS_LEAGUE", { country: "China", start_time_utc: "2026-10-28T17:00:00Z" })]);
  await openDay(page);
  const pill = page.locator('[data-event-id="resize"]');
  const widths = await pill.evaluate(el => [...el.nextElementSibling!.children].map(sample => Math.ceil(sample.getBoundingClientRect().width) + 8));
  const stages: number[] = [];
  for (const width of widths) {
    await pill.evaluate((el: HTMLElement, width) => { el.style.width = `${width}px`; }, width);
    await expect.poll(() => pill.evaluate((el) => el.clientWidth)).toBe(width);
    // Allow ResizeObserver and React's committed reduction to settle.
    await expect.poll(() => pill.evaluate((el) => {
      const sample = el.nextElementSibling!;
      const stage = Number(el.getAttribute("data-detail"));
      const available = el.clientWidth - 8;
      return stage === 4 || sample.children[stage].getBoundingClientRect().width <= available;
    })).toBe(true);
    stages.push(Number(await pill.getAttribute("data-detail")));
  }
  expect(stages).toEqual([0, 1, 2, 3, 4]);
  expect(await pill.evaluate(el => getComputedStyle(el).fontSize)).toBe("12px");
  await expect(pill.locator(".day-pill-name")).toHaveCount(0);
  await expect(pill.locator(".team-logo")).toHaveCount(2);
  await pill.locator(".team-logo").first().dispatchEvent("error");
  await expect(pill.locator(".day-pill-name")).toHaveText(["Home"]);
  await pill.evaluate((el: HTMLElement) => { el.style.width = "800px"; document.fonts.dispatchEvent(new Event("loadingdone")); });
  await expect(pill).toHaveAttribute("data-detail", "0");
  await expect(pill.locator(".day-pill-name")).toHaveText(["Home", "Away"]);
});

test("measurement clones and offscreen teams never request logos, and large all-day strips stay reachable", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  const requested: string[] = [];
  page.on("request", request => { if (request.url().startsWith("https://a.espncdn.com")) requested.push(request.url()); });
  await setup(page, Array.from({ length: 30 }, (_, index) => fixture(`all-${index}`, "soccer", "EPL", {
    participants: [team(`Home${index}`, "home"), team(`Away${index}`, "away")],
  })));
  await openDay(page);
  await expect(page.locator(".all-day-strip .event-pill")).toHaveCount(30);
  await expect(page.locator('.day-pill-measurements img[src]')).toHaveCount(0);
  expect(requested.some(url => url.includes("Home29") || url.includes("Away29"))).toBe(false);
  const last = page.locator('[data-event-id="all-29"]');
  await last.scrollIntoViewIfNeeded();
  await expect(last).toBeVisible();
  await expect.poll(() => requested.some(url => url.includes("Home29"))).toBe(true);
  await last.press("Enter");
  await expect(page.locator(".event-details h3")).toHaveText("all-29 source title at neutral venue");
  await page.keyboard.press("Escape");
  await expect(last).toBeFocused();
});
