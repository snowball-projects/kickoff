import { expect, test } from "./test";
import { agendaToggle, chooser, event, setup } from "./fixtures";

const events = [
  ...["EPL", "BUNDESLIGA", "LA_LIGA"].map((league) => event(`${league} match`, undefined, { league })),
  ...["NFL", "NBA", "MLB", "NHL"].map((league, i) => event(`${league} game`, undefined,
    { league, sport: ["football", "basketball", "baseball", "hockey"][i] })),
  event("UFC card", undefined, { league: "UFC", sport: "mma" }),
  event("PGA stop", undefined, { league: "PGA_TOUR", sport: "golf" }),
  event("Masters Tournament", undefined, { league: "PGA_TOUR", sport: "golf", competition_phase: "championship" }),
  event("LPGA stop", undefined, { league: "LPGA_TOUR", sport: "golf" }),
  event("Women's major", undefined, { league: "LPGA_TOUR", sport: "golf", competition_phase: "championship" }),
  ...["practice", "qualifying", "sprint", "race"].map((event_type) => event(`F1 ${event_type}`, undefined, { league: "F1", sport: "motorsport", event_type })),
  event("Sprint qualifying", undefined, { league: "F1", sport: "motorsport", event_type: "qualifying" }),
  ...["NASCAR_CUP", "INDYCAR"].map((league) => event(`${league} race`, undefined, { league, sport: "motorsport", event_type: "race" })),
  event("Men Lead", undefined, { league: "IFSC_WORLD_CUP", sport: "climbing", tags: ["Men", "Lead"] }),
  event("Women Boulder", undefined, { league: "IFSC_WORLD_CUP", sport: "climbing", tags: ["Women", "Boulder"] }),
  event("Combined Lead", undefined, { league: "CLIMBING_EUROPE", sport: "climbing", tags: ["Men", "Women", "Boulder", "Lead"] }),
  event("Unknown Lead", undefined, { league: "CLIMBING_ASIA", sport: "climbing", tags: ["Lead"] }),
  event("Europe Youth Lead", undefined, { league: "CLIMBING_EUROPE", sport: "climbing", tags: ["Youth", "Women", "Lead"] }),
  event("Asia U19 Lead", undefined, { league: "CLIMBING_ASIA", sport: "climbing", tags: ["U19", "Lead"] }),
  event("Europe Para Lead", undefined, { league: "CLIMBING_EUROPE", sport: "climbing", tags: ["Para", "Lead"] }),
  event("Olympic Lead", undefined, { league: "CLIMBING_OLYMPIC_QUALIFIERS", sport: "climbing", tags: ["Lead"] }),
  event("Youth lifting", undefined, { league: "IWF_YOUTH_WORLDS", sport: "weightlifting", tags: ["Women"] }),
  event("Junior lifting", undefined, { league: "IWF_JUNIOR_WORLDS", sport: "weightlifting", tags: ["Men"] }),
  event("Masters lifting", undefined, { league: "MASTERS_WORLDS", sport: "weightlifting", tags: [] }),
  event("Future lifting", undefined, { league: "FUTURE_LIFTING", sport: "weightlifting", tags: [] }),
  event("IWF Worlds", undefined, { league: "IWF_WORLDS", sport: "weightlifting", tags: ["Men"] }),
  event("Continental Europe", undefined, { league: "WEIGHTLIFTING_EUROPE", sport: "weightlifting", tags: ["Men"] }),
  event("Continental Asia", undefined, { league: "WEIGHTLIFTING_ASIA", sport: "weightlifting", tags: ["Women"] }),
];
const pill = (page: Parameters<typeof chooser>[0], name: string) => chooser(page).getByRole("button", { name, exact: true });
const tray = (page: Parameters<typeof chooser>[0], name: string) => chooser(page).getByRole("region", { name: `${name} interests`, exact: true });

async function rowEnd(page: Parameters<typeof chooser>[0], name: string) {
  return chooser(page).locator(".sport-pill").evaluateAll((buttons, name) => {
    const top = buttons.find((b) => b.getAttribute("aria-label") === name)!.getBoundingClientRect().top;
    return buttons.filter((b) => Math.abs(b.getBoundingClientRect().top - top) < 1).at(-1)!.getAttribute("aria-label");
  }, name);
}
async function expectTrayRow(page: Parameters<typeof chooser>[0], name: string, last: string | null) {
  await expect(tray(page, name)).toBeVisible();
  expect(await tray(page, name).evaluate((element) => element.previousElementSibling?.getAttribute("aria-label"))).toBe(last);
  const active = (await pill(page, name).boundingBox())!, box = (await tray(page, name).boundingBox())!;
  expect(box.y).toBeCloseTo(active.y + active.height + 8, 0);
  expect(box.width).toBeCloseTo(await chooser(page).locator(".sport-pills").evaluate((el) => el.clientWidth), 0);
}

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`sport pills ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("first visit, ten pills, row trays, partial counts, single-league toggles, all and clear", async ({ page }) => {
      await setup(page, events, { firstVisit: true });
      await expect(chooser(page)).toBeVisible();
      await expect(chooser(page).locator(".sport-pill")).toHaveCount(10);
      await expect(chooser(page).locator('.sport-pill[aria-pressed="false"]')).toHaveCount(10);
      await expect(chooser(page).getByRole("button", { name: "Show my calendar" })).toBeDisabled();
      await expect(chooser(page).locator("input, details, summary")).toHaveCount(0);
      const golfRow = await rowEnd(page, "Golf");
      await pill(page, "Golf").click();
      await expectTrayRow(page, "Golf", golfRow);
      await expect(tray(page, "Golf").getByRole("button")).toHaveText(["All", "PGA Tour", "LPGA Tour"]);
      await tray(page, "Golf").getByRole("button", { name: "LPGA Tour", exact: true }).click();
      await expect(pill(page, "Golf")).toHaveAttribute("aria-pressed", "mixed");
      await expect(pill(page, "Golf")).toContainText("1/2");
      await pill(page, "Golf").click();
      await expect(chooser(page).locator(".interest-tray")).toHaveCount(0);
      await page.setViewportSize({ width: width === 320 ? 1280 : 320, height: 844 });
      const resizedRow = await rowEnd(page, "Golf");
      await pill(page, "Golf").click();
      await expectTrayRow(page, "Golf", resizedRow);
      await tray(page, "Golf").getByRole("button", { name: "PGA Tour", exact: true }).focus();
      await page.setViewportSize({ width, height: 844 });
      await expect.poll(async () => {
        const a = (await pill(page, "Golf").boundingBox())!;
        const b = (await tray(page, "Golf").boundingBox())!;
        return Math.round(b.y - a.y - a.height);
      }).toBe(8);
      await expect(tray(page, "Golf").getByRole("button", { name: "PGA Tour", exact: true })).toBeFocused();
      const afterResize = await tray(page, "Golf").evaluate((el) => el.previousElementSibling?.getAttribute("aria-label"));
      await pill(page, "Golf").click();
      expect(afterResize).toBe(await rowEnd(page, "Golf"));
      await pill(page, "Soccer").click();
      await expect(chooser(page).locator(".interest-tray")).toHaveCount(1);
      await expect(tray(page, "Soccer").getByRole("img", { name: "Germany", exact: true })).toBeVisible();
      await expect(tray(page, "Soccer").locator(".interest-swatch")).toHaveCount(0);
      await tray(page, "Soccer").getByRole("button", { name: "Bundesliga", exact: false }).click();
      await expect(pill(page, "Soccer")).toContainText("2/3");
      for (const name of ["Football", "Basketball", "Baseball", "Hockey"]) {
        await pill(page, name).click();
        await expect(pill(page, name)).toHaveAttribute("aria-pressed", "true");
        await expect(pill(page, name)).not.toHaveAttribute("aria-expanded");
        await expect(chooser(page).locator(".interest-tray")).toHaveCount(0);
        await pill(page, name).click();
        await expect(pill(page, name)).toHaveAttribute("aria-pressed", "false");
      }
      await chooser(page).getByRole("button", { name: "Select all", exact: true }).click();
      await expect(chooser(page).locator('.sport-pill[aria-pressed="true"]')).toHaveCount(10);
      await page.screenshot({ path: `test-results/interests-all-${width}-${colorScheme}.png` });
      await chooser(page).getByRole("button", { name: "Clear", exact: true }).click();
      await expect(chooser(page).locator('.sport-pill[aria-pressed="false"]')).toHaveCount(10);
      await expect(chooser(page).getByRole("button", { name: "Show my calendar" })).toBeDisabled();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
    test("session sports expose only level, gender and discipline, with every competition on", async ({ page }) => {
      await setup(page, events, { firstVisit: true });
      await pill(page, "Climbing").click();
      const climbing = tray(page, "Climbing");
      await expect(climbing.getByRole("button")).toHaveText(["Senior", "Youth", "Para", "Men", "Women", "Boulder", "Lead", "Speed"]);
      await expect(climbing.locator('button[aria-pressed="true"]')).toHaveCount(8);
      await expect(climbing.locator("legend")).toHaveText(["Level", "Gender", "Discipline"]);
      await climbing.getByRole("button", { name: "Senior", exact: true }).click();
      await climbing.getByRole("button", { name: "Para", exact: true }).click();
      await page.screenshot({ path: `test-results/climbing-levels-${width}-${colorScheme}.png` });
      await pill(page, "Weightlifting").click();
      const lifting = tray(page, "Weightlifting");
      await expect(lifting.getByRole("button")).toHaveText(["Youth", "Junior", "Senior", "Masters", "Men", "Women"]);
      await expect(lifting.locator('button[aria-pressed="true"]')).toHaveCount(6);
      await expect(lifting.locator("legend")).toHaveText(["Level", "Gender"]);
      await lifting.getByRole("button", { name: "Senior", exact: true }).click();
      await page.screenshot({ path: `test-results/weightlifting-levels-${width}-${colorScheme}.png` });
      await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
      await agendaToggle(page).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      for (const text of ["Europe Youth Lead", "Asia U19 Lead", "Youth lifting", "Junior lifting", "Masters lifting"])
        await expect(agenda).toContainText(text);
      for (const text of ["Men Lead", "Women Boulder", "Combined Lead", "Unknown Lead", "Europe Para Lead", "Olympic Lead", "IWF Worlds", "Continental Europe", "Continental Asia", "Future lifting"])
        await expect(agenda).not.toContainText(text);
      await page.reload();
      await page.getByRole("button", { name: "Interests", exact: true }).click();
      await pill(page, "Climbing").click();
      await expect(climbing.getByRole("button", { name: "Youth", exact: true })).toHaveAttribute("aria-pressed", "true");
      await expect(climbing.getByRole("button", { name: "Senior", exact: true })).toHaveAttribute("aria-pressed", "false");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
    test("options filter exact event types and session facets, save, cancel and reload", async ({ page }) => {
      await setup(page, events, { firstVisit: true });
      await pill(page, "Motorsports").click();
      const motor = tray(page, "Motorsports");
      await expect(motor.getByRole("group", { name: "Sessions", exact: true })).toBeVisible();
      await expect(motor.locator(".interest-swatch")).toHaveCount(0);
      for (const name of ["Practice", "Qualifying", "Sprint", "Race"])
        await expect(motor.getByRole("button", { name, exact: true })).toHaveAttribute("aria-pressed", "true");
      for (const name of ["Practice", "Sprint", "Race"]) await motor.getByRole("button", { name, exact: true }).click();
      await page.screenshot({ path: `test-results/interests-tray-${width}-${colorScheme}.png` });
      await pill(page, "Climbing").click();
      await tray(page, "Climbing").getByRole("button", { name: "Men", exact: true }).click();
      await tray(page, "Climbing").getByRole("button", { name: "Boulder", exact: true }).click();
      await tray(page, "Climbing").getByRole("button", { name: "Speed", exact: true }).click();
      await pill(page, "Weightlifting").click();
      await tray(page, "Weightlifting").getByRole("button", { name: "Women", exact: true }).click();
      await pill(page, "Golf").click();
      await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
      await agendaToggle(page).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      for (const text of ["F1 qualifying", "Sprint qualifying", "Combined Lead", "Unknown Lead", "IWF Worlds", "Continental Europe", "PGA stop", "Masters Tournament", "LPGA stop", "Women's major"])
        await expect(agenda).toContainText(text);
      for (const text of ["F1 practice", "F1 race", "F1 sprint", "NASCAR_CUP race", "INDYCAR race", "Men Lead", "Women Boulder", "Continental Asia"])
        await expect(agenda).not.toContainText(text);
      await page.getByRole("button", { name: "Interests", exact: true }).click();
      await pill(page, "Motorsports").click();
      await motor.getByRole("button", { name: "Race", exact: true }).click();
      await page.keyboard.press("Escape");
      await page.reload();
      await expect(chooser(page)).toHaveCount(0);
      await page.getByRole("button", { name: "Interests", exact: true }).click();
      await pill(page, "Motorsports").click();
      await expect(motor.getByRole("button", { name: "Race", exact: true })).toHaveAttribute("aria-pressed", "false");
      await motor.getByRole("button", { name: "All", exact: true }).click();
      await expect(pill(page, "Motorsports")).toHaveAttribute("aria-pressed", "false");
      await pill(page, "Motorsports").click();
      await expect(motor).toBeVisible();
      await expect(pill(page, "Motorsports")).toHaveAttribute("aria-pressed", "true");
      await motor.getByRole("button", { name: "All", exact: true }).click();
      await motor.getByRole("button", { name: "All", exact: true }).click();
      for (const name of ["Practice", "Qualifying", "Sprint", "Race"])
        await expect(motor.getByRole("button", { name, exact: true })).toHaveAttribute("aria-pressed", "true");
    });
  });
}

test("old storage is ignored and delayed choices leave the first visit empty", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("kickoff.interests.v3", JSON.stringify({ leagues: ["NFL"] })));
  let release!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  await setup(page, events, { firstVisit: true, hold, wait: false });
  await expect(chooser(page)).toBeVisible();
  await expect(chooser(page).getByRole("button", { name: "Show my calendar" })).toBeDisabled();
  await expect(chooser(page).getByRole("button", { name: "Select all", exact: true })).toBeDisabled();
  release();
  await expect(chooser(page).locator('.sport-pill[aria-pressed="false"]')).toHaveCount(10);
  await expect(chooser(page).getByRole("button", { name: "Show my calendar" })).toBeDisabled();
  await pill(page, "Football").press("Space");
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v4")!).leagues)).toEqual(["NFL"]);
});

test("blocked storage keeps picked interests active for the visit", async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(window, "localStorage", { get() { throw Error("blocked"); } }));
  await setup(page, events, { firstVisit: true });
  await pill(page, "Football").click();
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
  await expect(page.locator("#day-2026-10-28 .event-pill")).toHaveCount(1);
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  await expect(page.getByRole("dialog")).toContainText("browser storage is unavailable");
});

for (const value of [{}, { leagues: null }, { leagues: ["F1"] }]) {
  test(`wrong-shaped current storage ${JSON.stringify(value)} reopens empty Interests`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript((value) => localStorage.setItem("kickoff.interests.v4", JSON.stringify(value)), value);
    await setup(page, events, { firstVisit: true });
    await expect(chooser(page)).toBeVisible();
    await expect(chooser(page).locator('.sport-pill[aria-pressed="false"]')).toHaveCount(10);
    await expect(chooser(page).getByRole("button", { name: "Show my calendar" })).toBeDisabled();
    await pill(page, "Motorsports").click();
    await expect(tray(page, "Motorsports").getByRole("button", { name: "Race", exact: true })).toHaveAttribute("aria-pressed", "true");
    expect(errors).toEqual([]);
  });
}
