import { expect, test } from "./test";
import { agendaToggle, event, month, setup } from "./fixtures";

const dense = ["FIFA_WORLD_CUP", "NFL", "NBA", "F1", "EPL", "MLB", "NHL", "UFC", "PGA_TOUR"];
const fixtures = ["2026-09-30", "2026-10-01", "2026-10-28"].flatMap((date) =>
  dense.map((league) => event(`${league} ${date}`, date, { league, country: "JP" })));

for (const width of [320, 390, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`month rows ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: width === 1280 ? 1000 : 844 }, colorScheme, reducedMotion: "reduce" });
    test("split rows, rules, civil-date keys, anchors, return focus and measured overflow", async ({ page }) => {
      await setup(page, fixtures);
      await month(page, "September 2026");
      const oldRow = page.locator(".calendar-week").filter({ has: page.locator("#day-2026-09-30") });
      const newRow = page.locator(".calendar-week").filter({ has: page.locator("#day-2026-10-01") });
      expect(await oldRow.locator('[role="gridcell"]').evaluateAll((cells) => cells.map((cell) => cell.id || null)))
        .toEqual(["day-2026-09-27", "day-2026-09-28", "day-2026-09-29", "day-2026-09-30", null, null, null]);
      expect(await newRow.locator('[role="gridcell"]').evaluateAll((cells) => cells.map((cell) => cell.id || null)))
        .toEqual([null, null, null, null, "day-2026-10-01", "day-2026-10-02", "day-2026-10-03"]);
      await expect(page.locator("#day-2026-10-01 .month-abbreviation")).toHaveText("Oct");
      const cells = await page.locator(".calendar-week > div").evaluateAll((cells) => cells.map((cell) => ({
        blank: cell.classList.contains("empty-day"), text: cell.textContent, buttons: cell.querySelectorAll("button").length,
        rule: getComputedStyle(cell).borderBottomWidth,
      })));
      for (const cell of cells) {
        expect(cell.rule).toBe(cell.blank ? "0px" : "1px");
        if (cell.blank) { expect(cell.text).toBe(""); expect(cell.buttons).toBe(0); }
      }
      expect(await oldRow.evaluate((row) => getComputedStyle(row).borderBottomWidth)).toBe("0px");
      await page.locator("#day-2026-09-30").evaluate((cell) => cell.scrollIntoView({ block: "center" }));
      await oldRow.locator(".empty-day").first().click();
      await expect(page.locator(".day-timeline-stage")).toHaveCount(0);
      await page.screenshot({ path: `test-results/split-${width}-${colorScheme}.png` });
      for (const [from, key, to] of [
        ["2026-09-30", "ArrowRight", "2026-10-01"], ["2026-10-01", "ArrowLeft", "2026-09-30"],
        ["2026-10-01", "ArrowUp", "2026-09-24"], ["2026-09-30", "ArrowDown", "2026-10-07"],
        ["2026-10-04", "ArrowUp", "2026-09-27"], ["2026-12-31", "ArrowRight", "2027-01-01"],
        ["2027-01-01", "ArrowUp", "2026-12-25"], ["2027-01-01", "ArrowLeft", "2026-12-31"],
      ]) {
        await page.locator(`#day-${from} .day-number`).press(key);
        await expect(page.locator(`#day-${to} .day-number`)).toBeFocused();
      }
      for (const date of ["2026-09-30", "2026-10-01"]) {
        await page.locator(`#day-${date} .day-number`).click();
        await expect(page.locator(".week-strip")).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(page.locator(`#day-${date} .day-number`)).toBeFocused();
        await expect(page.locator(".calendar-week").filter({ has: page.locator(`#day-${date}`) }))
          .toHaveCSS("view-transition-name", "selected-week");
      }
      await month(page, "October 2026");
      await expect(page.locator("#day-2026-10-01 .day-number")).toBeFocused();
      await expect(page.getByRole("heading", { name: "October", exact: true, level: 1 })).toBeVisible();
      const offset = await page.locator("#day-2026-10-01").evaluate((cell) =>
        cell.getBoundingClientRect().top - document.querySelector(".month-scroll")!.getBoundingClientRect().top);
      expect(Math.abs(offset)).toBeLessThan(1);
      await page.locator("#day-2026-10-28").evaluate((cell) => cell.scrollIntoView({ block: "center" }));
      for (const date of ["2026-09-30", "2026-10-01", "2026-10-28"]) {
        const cell = page.locator(`#day-${date}`);
        const count = await cell.locator(".event-pill").count();
        expect(count).toBe(width < 700 ? 2 : 4);
        await expect(cell.locator(".more-events")).toHaveText(`+${dense.length - count}`);
        const controls = await cell.evaluate((cell) => {
          const rect = cell.getBoundingClientRect();
          return [...cell.querySelectorAll(".event-pill, .more-events")].map((control) => {
            const box = control.getBoundingClientRect();
            return { top: box.top - rect.top, bottom: box.bottom - rect.top, height: rect.height };
          });
        });
        for (let index = 0; index < controls.length; index++) {
          expect(controls[index].bottom).toBeLessThanOrEqual(controls[index].height);
          if (index) expect(controls[index].top).toBeGreaterThanOrEqual(controls[index - 1].bottom);
        }
        for (const pill of await cell.locator(".event-pill").all()) {
          expect(await pill.locator(":scope > *").first().evaluate((el) => el.matches("svg.sport-icon"))).toBe(true);
          if (await pill.locator(".country-flag").count())
            expect(await pill.locator(".country-flag").isVisible()).toBe(width >= 700);
        }
      }
      const endRow = page.locator(".calendar-week").filter({ has: page.locator("#day-2026-10-31") });
      await expect(endRow.locator(".day-cell")).toHaveCount(7);
      const novemberRow = page.locator(".calendar-week").filter({ has: page.locator("#day-2026-11-01") });
      await expect(novemberRow.locator(".day-cell")).toHaveCount(7);
      await novemberRow.evaluate((row) => row.scrollIntoView({ block: "start" }));
      await expect(page.getByRole("heading", { name: "November", exact: true, level: 1 })).toBeVisible();
      await page.screenshot({ path: `test-results/no-split-${width}-${colorScheme}.png` });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  });
}

test("the 700px breakpoint hides only month flags and pills keep icon, title, country order", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setup(page, [
    event("Domestic one", undefined, { source: "openfootball", country: "Germany" }),
    event("Domestic two", undefined, { source: "openfootball", country: null }),
    event("Timed title", undefined, { league: "UFC", country: "JP", start_time_utc: "2026-10-28T17:00:00Z" }),
    event("All-day title", undefined, { league: "PGA_TOUR", sport: "golf", country: "JP" }),
    event("Another all-day title", undefined, { league: "PGA_TOUR", sport: "golf", country: "JP" }),
  ]);
  for (const width of [699, 700]) {
    await page.setViewportSize({ width, height: 1000 });
    const pill = page.locator("#day-2026-10-28 .event-pill").filter({ hasText: "Premier League" });
    await expect(pill.locator(".country-flag")).toHaveAttribute("aria-label", "England");
    expect(await pill.locator(".country-flag").isVisible()).toBe(width === 700);
    expect(await pill.locator(":scope > *").evaluateAll((elements) => elements.map((element) => element.getAttribute("class"))))
      .toEqual(["sport-icon", "pill-text", "country-flag"]);
  }
  await page.setViewportSize({ width: 320, height: 844 });
  await page.locator("#day-2026-10-28 .day-number").click();
  await expect(page.locator('.timeline-events [data-event-id="Timed title"] .pill-text')).toHaveText("Timed title");
  await expect(page.locator('.timeline-events [data-event-id="Timed title"] .country-flag')).toBeVisible();
  await expect(page.locator(".all-day-strip .event-pill")).toHaveCount(4);
  await expect(page.locator(".all-day-strip .pill-text")).toHaveText(["Domestic one", "Domestic two", "All-day title", "Another all-day title"]);
  for (const pill of await page.locator(".day-timeline-stage .event-pill").all()) {
    expect(await pill.locator(":scope > *").evaluateAll((elements) => elements.map((element) => element.getAttribute("class"))))
      .toEqual(["sport-icon", "pill-text", "country-flag"]);
    await expect(pill.locator(".country-flag")).toBeVisible();
  }
  await page.screenshot({ path: "test-results/pill-day-320.png" });
});

test("shared country requires every event and excluded leagues never get pill flags", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1800 });
  await setup(page, [
    ...["NBA", "NFL", "NHL", "MLB", "NASCAR_CUP", "INDYCAR"].map((league) => event(league, undefined, { league, country: "US" })),
    event("Shared one", undefined, { league: "UFC", country: "JP" }),
    event("Shared two", undefined, { league: "UFC", country: "Japan" }),
    event("Missing one", undefined, { league: "PFL", country: "JP" }),
    event("Missing two", undefined, { league: "PFL", country: null }),
    event("Mixed one", undefined, { league: "ONE", country: "JP" }),
    event("Mixed two", undefined, { league: "ONE", country: "US" }),
  ]);
  const cell = page.locator("#day-2026-10-28");
  await expect(cell.locator(".event-pill")).toHaveCount(9);
  await expect(cell.locator(".country-flag")).toHaveCount(1);
  await expect(cell.locator(".event-pill").filter({ hasText: "UFC" }).locator(".country-flag")).toHaveAttribute("aria-label", "Japan");
});

test("sheet details, grouped rows and agenda place host and national-team flags after titles", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const participants = [
    { name: "Japan", entity_type: "national_team", country_code: "JP" },
    { name: "USA", entity_type: "national_team", country_code: "US" },
  ];
  await setup(page, [event("National match", undefined, { league: "FIFA_WORLD_CUP", country: "CA", participants }),
    event("Other match", undefined, { league: "FIFA_WORLD_CUP", country: "CA" })]);
  await page.locator("#day-2026-10-28 .event-pill").click();
  const row = page.locator(".sheet-event-row").filter({ hasText: "National match" });
  expect(await row.locator("b").evaluate((el) => el.firstChild?.textContent)).toBe("National match");
  await expect(row.locator(".country-flag")).toHaveCount(3);
  await row.click();
  const heading = page.locator(".event-details h3");
  expect(await heading.evaluate((el) => el.firstChild?.textContent)).toBe("National match");
  expect(await heading.locator(".country-flag").evaluateAll((flags) => flags.map((flag) => flag.getAttribute("aria-label"))))
    .toEqual(["Host country: Canada", "Japan: Japan", "USA: United States"]);
  await page.keyboard.press("Escape");
  await agendaToggle(page).click();
  const title = page.locator(".agenda-title").filter({ hasText: "National match" });
  expect(await title.evaluate((el) => el.firstChild?.textContent)).toBe("National match");
  await expect(title.locator(".country-flag")).toHaveCount(3);
  await page.screenshot({ path: "test-results/flags-agenda.png" });
});

test("both halves of a split week have one selected-week transition and survive switching halves", async ({ page }) => {
  const snapshots: { phase: string; dates: string[]; names: string[] }[] = [];
  await setup(page, fixtures);
  await month(page, "September 2026");
  await page.exposeFunction("recordSplit", (snapshot: typeof snapshots[number]) => snapshots.push(snapshot));
  await page.evaluate(() => {
    const record = (phase: string) => {
      const elements = [...document.querySelectorAll<HTMLElement>(".calendar-week, .week-strip")]
        .filter((el) => el.getClientRects().length && getComputedStyle(el).viewTransitionName === "selected-week");
      return (window as unknown as { recordSplit: (value: object) => Promise<void> }).recordSplit({
        phase, dates: elements.map((el) => el.dataset.dates || "day strip"),
        names: elements.map((el) => getComputedStyle(el).viewTransitionName),
      });
    };
    const native = document.startViewTransition.bind(document);
    document.startViewTransition = (update) => {
      void record("old");
      return native(async () => {
        if (typeof update === "function") await update();
        await record("new");
      });
    };
  });
  await page.locator("#day-2026-09-30 .day-number").click();
  await expect(page.locator(".week-strip")).toBeVisible();
  await page.locator('.week-strip [data-date="2026-10-01"]').click();
  await page.getByRole("button", { name: "Back to October", exact: true }).click();
  await expect(page.locator("#day-2026-10-01 .day-number")).toBeFocused();
  await page.locator("#day-2026-10-01 .day-number").click();
  await page.keyboard.press("Escape");
  await expect(page.locator("#day-2026-10-01 .day-number")).toBeFocused();
  await expect.poll(() => snapshots.length).toBe(8);
  for (const snapshot of snapshots) expect(snapshot.names).toEqual(["selected-week"]);
  expect(snapshots[0].dates).toEqual(["2026-09-27,2026-09-28,2026-09-29,2026-09-30"]);
  expect(snapshots[3].dates).toEqual(["2026-10-01,2026-10-02,2026-10-03"]);
  expect(snapshots[4].dates).toEqual(snapshots[3].dates);
});
