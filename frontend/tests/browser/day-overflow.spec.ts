import { expect, test } from "./test";
import { event, mockTeamLogos, setup, teamLogoUrl } from "./fixtures";

const team = (name: string, role: string, logo = false) => ({ name: `${name} full source name`, short_name: name,
  role, entity_type: "team", ...(logo && { logo_url: teamLogoUrl(`/i/teamlogos/nfl/500/${name}.png`) }) });
const game = (id: string, fields = {}) => event(id, undefined, { sport: "soccer", league: "EPL",
  title: `${id}, original source context`, start_time_utc: "2026-10-28T17:00:00Z",
  participants: [team("SuppliedHomeIdentifier", "home"), team("SuppliedAwayIdentifier", "away")], ...fields });
const openDay = async (page: Parameters<typeof setup>[0]) => page.locator("#day-2026-10-28 .day-number").click();
const source = (page: Parameters<typeof setup>[0], id = "resize") => page.locator(`.timeline-events [data-event-id="${id}"]`);

test.use({ reducedMotion: "reduce" });
test.beforeEach(async ({ page }) => mockTeamLogos(page));

for (const width of [320, 375]) test(`missing-logo matchups merge into existing same-clock overflow without duplicates at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  const requests: string[] = [];
  page.on("request", request => { if (new URL(request.url()).origin === "https://a.espncdn.com") requests.push(request.url()); });
  await setup(page, [game("a-missing-both"), game("b-missing-one", { participants: [team("LongMissingClubName", "home"), team("LogoInHiddenPill", "away", true)] }),
    game("c-existing-overflow-one", { participants: [team("ExistingHome", "home", true), team("ExistingAway", "away", true)] }), game("d-existing-overflow-two")]);
  await openDay(page);
  const more = page.locator(".timeline-more");
  await expect(more).toHaveText("+4");
  await expect(more).toHaveAccessibleName(/SuppliedHomeIdentifier full source name vs SuppliedAwayIdentifier full source name/);
  await expect(more).toHaveAccessibleName(/LongMissingClubName full source name vs LogoInHiddenPill full source name/);
  await expect(more).not.toHaveAccessibleName(/ExistingHome/);
  await expect(page.locator(".timeline-events > .event-pill:visible")).toHaveCount(0);
  for (const id of ["a-missing-both", "b-missing-one"]) {
    await expect(source(page, id)).toBeHidden();
    await expect(source(page, id)).toBeDisabled();
    await expect(source(page, id)).toHaveAttribute("aria-hidden", "true");
    await expect(source(page, id)).toHaveAttribute("tabindex", "-1");
    await expect(source(page, id).locator("img[src]")).toHaveCount(0);
  }
  expect(requests.some(url => url.includes("LogoInHiddenPill"))).toBe(false);
  expect(await more.evaluate((el: HTMLElement) => [el.style.top, el.style.left, el.getBoundingClientRect().height])).toEqual(["960px", "66.6667%", 28]);
  await more.press("Enter");
  await expect(page.locator(".sheet-event-row")).toHaveCount(4);
  await expect(page.locator(".sheet-event-row b")).toHaveText(["a-missing-both, original source context", "b-missing-one, original source context",
    "c-existing-overflow-one, original source context", "d-existing-overflow-two, original source context"]);
  await page.locator(".sheet-event-row").filter({ hasText: "missing-both" }).press("Enter");
  await expect(page.locator(".event-details h3")).toHaveText("a-missing-both, original source context");
  await page.keyboard.press("Escape");
  await expect(more).toBeFocused();
});

test("nearby missing-logo starts retain their exact times and separate non-overlapping controls", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await setup(page, [game("first"), game("nearby", { start_time_utc: "2026-10-28T17:10:00Z" })]);
  await openDay(page);
  await expect(page.locator(".timeline-more")).toHaveText(["+1", "+1"]);
  expect(await page.locator(".timeline-more").evaluateAll(nodes => nodes.map((el: HTMLElement) => [el.style.top, el.style.left, el.style.width]))).toEqual([
    ["960px", "0%", "calc(50% - 4px)"], ["973.333px", "50%", "calc(50% - 4px)"],
  ]);
  await page.locator(".timeline-more").last().press("Enter");
  await expect(page.locator(".event-details h3")).toHaveText("nearby, original source context");
  await expect(page.locator(".detail-time")).toHaveText("12:10 PM");
});

test("image failure moves a focused source to overflow and widening restores it without retrying the failed logo", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  const requests: string[] = [];
  page.on("request", request => { if (new URL(request.url()).origin === "https://a.espncdn.com") requests.push(request.url()); });
  await setup(page, [game("resize", { participants: [team("SuppliedHomeIdentifier", "home", true), team("SuppliedAwayIdentifier", "away", true)] }),
    game("other", { participants: [team("H", "home", true), team("A", "away", true)] })]);
  await openDay(page);
  const pill = source(page);
  await expect(page.locator(".timeline-more")).toHaveCount(0);
  await expect(pill).toBeVisible();
  await expect(pill.locator("img").first()).toHaveAttribute("src", /SuppliedHomeIdentifier/);
  await pill.focus();
  await pill.locator("img").first().dispatchEvent("error");
  const more = page.locator(".timeline-more");
  await expect(more).toHaveText("+1");
  await expect(more).toBeFocused();
  await expect(pill).toBeHidden();
  const attempts = requests.filter(url => url.includes("SuppliedHomeIdentifier")).length;
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(more).toHaveCount(0);
  await expect(pill).toBeVisible();
  await expect(pill).toBeFocused();
  await expect(pill.locator("img")).toHaveCount(1);
  expect(requests.filter(url => url.includes("SuppliedHomeIdentifier")).length).toBe(attempts);
});

for (const cycle of ["narrow-wide", "wide-narrow", "narrow-wide-narrow"] as const) test(`popup focus returns to a current source or overflow after ${cycle}`, async ({ page }) => {
  await page.setViewportSize({ width: cycle === "wide-narrow" ? 1280 : 375, height: 900 });
  await setup(page, [game("resize"), game("other", { participants: [team("H", "home", true), team("A", "away", true)] })]);
  await openDay(page);
  const opener = cycle === "wide-narrow" ? source(page) : page.locator(".timeline-more");
  await opener.press("Enter");
  await expect(page.locator(".event-details h3")).toHaveText("resize, original source context");
  if (cycle !== "wide-narrow") {
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(page.locator(".timeline-more")).toHaveCount(0);
    await expect(source(page)).toBeVisible();
  }
  if (cycle !== "narrow-wide") {
    await page.setViewportSize({ width: 375, height: 900 });
    await expect(page.locator(".timeline-more")).toHaveText("+1");
    await expect(source(page)).toBeHidden();
  }
  await page.keyboard.press("Escape");
  await expect(cycle === "narrow-wide" ? source(page) : page.locator(".timeline-more")).toBeFocused();
});

test("font metrics remeasure without geometry changes and all-day/individual source titles stay in place", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  const thinNames = [team("Milliiiiiiiiiiiiiiiiiiiiii", "home"), team("Williiiiiiiiiiiiiiiiiiiiii", "away")];
  await setup(page, [game("font", { participants: thinNames }),
    game("all-day", { start_time_utc: null, title: "A long unchanged all-day title with supplied opponents and undecided source context" }),
    event("individual", undefined, { sport: "weightlifting", league: "IWF_WORLDS", title: "IWF Worlds · A long supplied session name that remains on its pill", start_time_utc: "2026-10-28T19:00:00Z" })]);
  await openDay(page);
  const pill = source(page, "font");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(pill).toBeVisible();
  const geometry = await pill.evaluate((el: HTMLElement) => [el.style.top, el.style.left, el.style.width, el.getBoundingClientRect().height]);
  await page.evaluate(() => { document.documentElement.style.fontFamily = "monospace"; });
  await expect(page.locator(".timeline-more")).toHaveText("+1");
  await expect(pill).toBeHidden();
  const changes = await pill.evaluate(async (el) => {
    let changes = 0;
    const observer = new MutationObserver(records => { changes += records.length; });
    observer.observe(el, { attributes: true, attributeFilter: ["style", "disabled", "aria-hidden"] });
    await new Promise<void>(resolve => {
      let frames = 0;
      const next = () => { if (++frames === 8) resolve(); else requestAnimationFrame(next); };
      requestAnimationFrame(next);
    });
    observer.disconnect();
    return changes;
  });
  expect(changes, "unchanged measurement geometry must not toggle the fallback repeatedly").toBe(0);
  expect(await pill.evaluate((el: HTMLElement) => [el.style.top, el.style.left, el.style.width, el.getBoundingClientRect().height])).toEqual(geometry);
  await expect(page.locator('.all-day-strip [data-event-id="all-day"]')).toBeVisible();
  await expect(source(page, "individual")).toBeVisible();
  await page.evaluate(() => { document.documentElement.style.fontFamily = ""; document.fonts.dispatchEvent(new Event("loadingdone")); });
  await expect(page.locator(".timeline-more")).toHaveCount(0);
  await expect(pill).toBeVisible();
  expect(errors).toEqual([]);
});

for (const role of ["roleless", "home-only"]) test(`${role} team titles use the same truthful overflow path`, async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  const title = "Published long source title with the known opponent, undecided side and neutral-site context";
  await setup(page, [game("source", { title, sport: "cricket", league: "IPL", participants: role === "roleless"
    ? [team("KnownOne", ""), team("KnownTwo", "")] : [team("KnownHome", "home")] }),
    game("other", { participants: [team("H", "home", true), team("A", "away", true)] })]);
  await openDay(page);
  await expect(source(page, "source")).toBeHidden();
  const more = page.locator(".timeline-more");
  await expect(more).toHaveText("+1");
  await expect(more).toHaveAccessibleName(new RegExp(title));
  await expect(more).toHaveAccessibleName(role === "roleless" ? /KnownOne full source name; KnownTwo full source name/
    : /KnownHome full source name/);
  await more.press("Enter");
  await expect(page.locator(".event-details h3")).toHaveText(title);
});


test("overflow keeps chronological Tab order and a focused same-clock +2 survives becoming +1", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await setup(page, [game("a-first", { participants: [team("MediumHomeClub", "home"), team("MediumAwayClub", "away")] }),
    game("b-second", { participants: [team("LengthySuppliedHomeClub", "home"), team("LengthySuppliedAwayClub", "away")] }),
    game("c-later", { start_time_utc: "2026-10-28T19:00:00Z", participants: [team("H", "home", true), team("A", "away", true)] })]);
  await openDay(page);
  const more = page.locator(".timeline-more");
  await expect(more).toHaveText("+2");
  await more.focus();
  await page.keyboard.press("Tab");
  await expect(source(page, "c-later")).toBeFocused();
  await more.focus();
  const minimums = await page.locator('.timeline-events .day-pill-measurements').evaluateAll(samples => samples.slice(0, 2).map(sample => sample.children[4].getBoundingClientRect().width));
  expect(minimums[1]).toBeGreaterThan(minimums[0]);
  const middleViewport = Math.ceil((minimums[0] + minimums[1] + 24) + 65);
  expect(middleViewport).toBeLessThan(900);
  await page.setViewportSize({ width: middleViewport, height: 900 });
  await expect(more).toHaveText("+1");
  await expect(more).toBeFocused();
  await expect(source(page, "a-first")).toBeVisible();
  await expect(source(page, "b-second")).toBeHidden();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(more).toHaveCount(0);
  await expect(source(page, "b-second")).toBeFocused();
});


test("an existing overflow clock stays anchored before a later higher-priority postseason game", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  const participants = [team("Home", "home", true), team("Away", "away", true)];
  await setup(page, [game("a", { participants }), game("b", { participants }), game("c", { participants }),
    game("later-postseason", { participants, competition_phase: "postseason", start_time_utc: "2026-10-28T17:10:00Z" })]);
  await openDay(page);
  const more = page.locator(".timeline-more");
  await expect(more).toHaveText("+2");
  await expect(more).toHaveAccessibleName("2 more events at 12:00 PM");
  expect(await more.evaluate((el: HTMLElement) => el.style.top)).toBe("960px");
  await more.press("Enter");
  // The popup retains its existing priority order; the timeline clock stays earlier.
  await expect(page.locator(".sheet-event-row b")).toHaveText(["later-postseason, original source context", "c, original source context"]);
});

test("overflow shows full source team names visually and retains neutral-site context", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  // Synthetic source-title pattern, not a claim of an actual neutral-site fixture.
  const title = "Auburn Tigers vs Nebraska Cornhuskers, neutral-site fixture";
  const participants = [
    { name: "Auburn Tigers", short_name: "Auburn", role: "home", entity_type: "team" },
    { name: "Nebraska Cornhuskers", short_name: "Nebraska", role: "away", entity_type: "team" },
  ];
  const fields = { sport: "football", league: "COLLEGE_FOOTBALL" };
  await setup(page, [game("full-names", { ...fields, title, participants }),
    game("Other fixture", { ...fields, participants: [team("H", "home", true), team("A", "away", true)] }),
    game("Z baseline overflow", { ...fields, participants: [team("H", "home", true), team("A", "away", true)] })]);
  await openDay(page);
  const more = page.locator(".timeline-more");
  await expect(more).toHaveText("+2");
  await more.press("Enter");
  const row = page.locator(".sheet-event-row").filter({ hasText: title });
  await expect(row.locator("b")).toHaveText(title);
  await expect(row).toContainText("Auburn Tigers");
  await expect(row).toContainText("Nebraska Cornhuskers");
  await row.press("Enter");
  await expect(page.locator(".event-details h3")).toHaveText(title);
  await page.screenshot({ path: "test-results/day-overflow-full-names.png" });
});
