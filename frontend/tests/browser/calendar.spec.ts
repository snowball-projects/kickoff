import { expect, test } from "./test";
import { agendaToggle, event, month, setup } from "./fixtures";

const events = [
  event("Regular World Cup", undefined, { league: "FIFA_WORLD_CUP" }),
  event("NFL fixture", undefined, { league: "NFL", sport: "football" }),
  event("Early match", undefined, { start_time_utc: "2026-10-28T15:00:00Z" }),
  event("Late match", undefined, { start_time_utc: "2026-10-28T19:00:00Z", status: "postponed" }),
  event("Playoff", undefined, { league: "ONE", sport: "mma", competition_phase: "postseason" }),
  event("Next month", "2026-11-02"),
];
for (const width of [390, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("fixed rows, league overflow, year zoom, majority heading, day strip and sources", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await setup(page, events);
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByRole("heading", { name: "October", exact: true, level: 1 })).toBeVisible();
      const cell = page.locator("#day-2026-10-28");
      await expect(cell.locator(".event-pill").first()).toContainText("One");
      await expect(cell.locator(".event-pill")).toHaveCount(2);
      const heights = await page.locator(".calendar-week").evaluateAll((rows) => rows.map((row) => row.getBoundingClientRect().height));
      expect(new Set(heights).size).toBe(1);
      expect(await page.locator(".sport-icon").first().evaluate((element) => getComputedStyle(element).fill)).not.toBe("none");
      expect(await page.locator(".sport-icon").first().evaluate((element) => getComputedStyle(element).stroke)).toBe("none");
      await cell.locator(".event-pill").first().click();
      await expect(page.getByRole("dialog")).toContainText("Playoff");
      await page.keyboard.press("Escape");
      await expect(cell.locator(".event-pill").first()).toBeFocused();
      await cell.locator(".more-events").click();
      await expect(page.getByRole("region", { name: "Day events", exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Wednesday, October 28, 2026", exact: true })).toBeVisible();
      await expect(page.getByRole("switch")).toHaveCount(0);
      await expect(page.locator(".timeline-hour")).toHaveCount(25);
      await page.getByRole("button", { name: "Thursday, October 29, 2026", exact: true }).click();
      await page.getByRole("button", { name: "Thursday, October 29, 2026", exact: true }).press("ArrowLeft");
      await page.locator('[data-event-id="Late match"]').click();
      const sheet = page.getByRole("dialog");
      await expect(sheet).toContainText("2:00 PM");
      await expect(sheet).toContainText("postponed");
      await expect(sheet.getByRole("link", { name: "Schedule source" })).toHaveAttribute("href", "https://example.com/schedule");
      await sheet.getByRole("button", { name: "Close", exact: true }).click();
      await expect(page.locator('[data-event-id="Late match"]')).toBeFocused();
      await page.screenshot({ path: `test-results/day-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Back to October", exact: true }).click();
      await expect(cell.locator(".day-number")).toBeFocused();
      await page.getByRole("button", { name: /Show .* year calendar/ }).click();
      await expect(page.locator(".mini-month")).toHaveCount(12);
      await page.screenshot({ path: `test-results/year-${width}-${colorScheme}.png` });
      await page.getByRole("button", { name: "Open November 2026", exact: true }).click();
      await expect(page.getByRole("heading", { name: "November", level: 1, exact: true })).toBeVisible();
      await expect(page.locator("#day-2026-11-01 .month-abbreviation")).toHaveText("Nov");
      const headerTop = await page.locator(".calendar-header").evaluate((element) => element.getBoundingClientRect().top);
      await page.locator("#day-2026-12-01").evaluate((element) => element.scrollIntoView({ block: "start" }));
      await expect(page.getByRole("heading", { name: "December", level: 1, exact: true })).toBeVisible();
      expect(await page.locator(".calendar-header").evaluate((element) => element.getBoundingClientRect().top)).toBe(headerTop);
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByRole("heading", { name: "October", level: 1, exact: true })).toBeVisible();
      await cell.locator(".day-number").press("ArrowRight");
      await expect(page.locator("#day-2026-10-29 .day-number")).toBeFocused();
      await page.screenshot({ path: `test-results/calendar-${width}-${colorScheme}.png` });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect(errors).toEqual([]);
    });
    test("group sheet details, back, focus trap, backdrop, Info and removed UI", async ({ page }) => {
      await setup(page, events, { saved: { leagues: ["EPL"] } });
      const pill = page.locator("#day-2026-10-28 .event-pill");
      await pill.click();
      const sheet = page.getByRole("dialog");
      await expect(sheet.locator(".sheet-event-row")).toContainText(["Early match", "Late match"]);
      await page.screenshot({ path: `test-results/sheet-${width}-${colorScheme}.png` });
      await sheet.locator(".sheet-event-row").last().click();
      await expect(sheet.getByRole("article")).toContainText("Late match");
      await sheet.getByRole("button", { name: "Back to events" }).click();
      await expect(sheet.locator(".sheet-event-row").last()).toBeFocused();
      await sheet.getByRole("button", { name: "Close", exact: true }).focus();
      await page.keyboard.press("Shift+Tab");
      expect(await page.evaluate(() => document.activeElement?.closest("dialog") !== null)).toBe(true);
      await page.mouse.click(2, 2);
      await expect(sheet).toHaveCount(0);
      await expect(pill).toBeFocused();
      await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
      await expect(sheet).toContainText("America/Chicago");
      await expect(sheet).toContainText("Updated 2026-10-27");
      await expect(sheet.getByRole("link", { name: "Source", exact: false }).first()).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.locator("footer, .day-inspector, .competition-chip, #event-preview")).toHaveCount(0);
      await pill.hover();
      await expect(page.getByRole("tooltip")).toHaveCount(0);
    });
  });
}
test("the View Transitions API is optional and reduced motion never invokes it", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => Object.defineProperty(document, "startViewTransition", { value: () => { throw Error("motion was invoked"); }, configurable: true }));
  await setup(page, events);
  await page.locator("#day-2026-10-28 .day-number").click();
  await expect(page.locator(".day-timeline-stage")).toBeVisible();
  await page.getByRole("button", { name: "Back to October" }).click();
  await page.evaluate(() => Object.defineProperty(document, "startViewTransition", { value: undefined, configurable: true }));
  await month(page, "November 2026");
  await page.locator("#day-2026-11-02 .day-number").click();
  await expect(page.locator(".day-timeline-stage")).toBeVisible();
});
test("transition snapshots share the selected week and year/month zoom", async ({ page }) => {
  await setup(page, events);
  const transitions: string[][] = [];
  const newSnapshots: string[][] = [];
  await page.exposeFunction("recordNames", (names: string[]) => transitions.push(names));
  await page.exposeFunction("recordNewNames", (names: string[]) => newSnapshots.push(names));
  await page.evaluate(() => {
    const native = document.startViewTransition.bind(document);
    document.startViewTransition = (update) => {
      void (window as unknown as { recordNames: (names: string[]) => Promise<void> }).recordNames(
        [...document.querySelectorAll(".calendar-week, .week-strip, .mini-month, .month-stage")]
          .filter((element) => element.getClientRects().length).map((element) => getComputedStyle(element).viewTransitionName).filter((name) => name !== "none"));
      return native(async () => {
        if (typeof update === "function") await update();
        await (window as unknown as { recordNewNames: (names: string[]) => Promise<void> }).recordNewNames(
          [...document.querySelectorAll(".calendar-week, .week-strip, .mini-month, .month-stage")]
            .filter((element) => element.getClientRects().length).map((element) => getComputedStyle(element).viewTransitionName).filter((name) => name !== "none"));
      });
    };
  });
  await page.locator("#day-2026-10-28 .day-number").click();
  await expect(page.locator(".week-strip")).toBeVisible();
  await page.getByRole("button", { name: "Back to October" }).click();
  await month(page, "November 2026");
  expect(transitions.some((names) => names.includes("selected-week"))).toBe(true);
  expect(transitions.some((names) => names.includes("calendar-zoom"))).toBe(true);
  await expect.poll(() => newSnapshots.at(-1)).toEqual(["calendar-zoom"]);
});
test.describe("phone touch", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, reducedMotion: "reduce" });
  test("swiping the week and the sheet works without hover state", async ({ page }) => {
    await setup(page, events);
    await page.locator("#day-2026-10-28 .day-number").tap();
    const strip = page.locator(".week-strip");
    await strip.evaluate((element) => {
      const contact = (clientX: number) => new Touch({ identifier: 1, target: element, clientX, clientY: 100 });
      element.dispatchEvent(new TouchEvent("touchstart", { touches: [contact(320)], bubbles: true }));
      element.dispatchEvent(new TouchEvent("touchend", { changedTouches: [contact(80)], bubbles: true }));
    });
    await expect(page.getByRole("heading", { name: "Wednesday, November 4, 2026", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Interests", exact: true }).tap();
    const header = page.locator(".sheet-header");
    await header.dispatchEvent("pointerdown", { pointerType: "touch", pointerId: 1, clientY: 500 });
    await header.dispatchEvent("pointerup", { pointerType: "touch", pointerId: 1, clientY: 600 });
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("tooltip")).toHaveCount(0);
  });
});
test("nearby starts stay at their true minutes and crowded lanes open every hidden event", async ({ page }) => {
  const crowded = Array.from({ length: 6 }, (_, index) => event(`Game ${index}`, undefined, {
    league: ["NFL", "NBA", "MLB", "NHL", "UFC", "EPL"][index], start_time_utc: "2026-10-28T17:30:00Z",
  }));
  await setup(page, crowded);
  await page.locator("#day-2026-10-28 .day-number").click();
  await expect(page.locator(".timeline-events .event-pill")).toHaveCount(2);
  await expect(page.locator(".timeline-more")).toHaveText("+4");
  const tops = await page.locator(".timeline-events > button").evaluateAll((buttons) => buttons.map((button) => (button as HTMLElement).style.top));
  expect(new Set(tops).size).toBe(1);
  await page.locator(".timeline-more").click();
  await expect(page.getByRole("dialog").locator(".sheet-event-row")).toHaveCount(4);
});

test("Agenda return preserves the scrolled month after a day was previously opened", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setup(page, events);
  await page.locator("#day-2026-10-28 .day-number").click();
  await page.getByRole("button", { name: "Back to October", exact: true }).click();
  await page.locator("#day-2026-11-01").evaluate((element) => element.scrollIntoView({ block: "start" }));
  await expect(page.getByRole("heading", { name: "November", level: 1, exact: true })).toBeVisible();
  const top = await page.locator(".month-scroll").evaluate((element) => element.scrollTop);
  await agendaToggle(page).click();
  await agendaToggle(page).click();
  await expect(page.getByRole("heading", { name: "November", level: 1, exact: true })).toBeVisible();
  expect(await page.locator(".month-scroll").evaluate((element) => element.scrollTop)).toBe(top);
  await expect(agendaToggle(page)).toBeFocused();
});

for (const [width, height] of [[390, 700], [1280, 600]]) {
  test(`pills and overflow remain inside fixed cells at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await setup(page, events);
    const cell = page.locator("#day-2026-10-28");
    await expect(cell.locator(".more-events")).toHaveText("+2");
    const boxes = await cell.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return [...element.querySelectorAll(".event-pill, .more-events")].map((control) => {
        const box = control.getBoundingClientRect();
        return { top: box.top - rect.top, bottom: box.bottom - rect.top, height: rect.height };
      });
    });
    expect(boxes.length).toBe(3);
    for (const box of boxes) { expect(box.top).toBeGreaterThanOrEqual(0); expect(box.bottom).toBeLessThanOrEqual(box.height); }
    for (let index = 1; index < boxes.length; index++) expect(boxes[index].top).toBeGreaterThanOrEqual(boxes[index - 1].bottom);
  });
}
