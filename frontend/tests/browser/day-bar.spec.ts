import type { Page } from "@playwright/test";
import { expect, test } from "./test";
import { event, month, nativeDayPan, setup } from "./fixtures";

const fixtures = [event("Today fixture")];
const bar = (page: Page) => page.getByRole("group", { name: "Days", exact: true });
const selected = (page: Page) => bar(page).locator('[aria-pressed="true"]');
const scrollLeft = (page: Page) => bar(page).evaluate((element) => element.scrollLeft);
async function visibleSelection(page: Page) {
  await expect.poll(() => selected(page).evaluate((button) => {
    const bounds = button.parentElement!.getBoundingClientRect();
    const box = button.getBoundingClientRect();
    return box.left >= bounds.left - 1 && box.right <= bounds.right + 1;
  })).toBe(true);
}
async function visibleOtherDay(page: Page) {
  return bar(page).evaluate((element) => {
    const box = element.getBoundingClientRect();
    return [...element.querySelectorAll<HTMLButtonElement>('button[aria-pressed="false"]')]
      .filter((button) => { const rect = button.getBoundingClientRect(); return rect.left >= box.left && rect.right <= box.right; })
      .sort((a, b) => Math.abs(a.getBoundingClientRect().x + a.offsetWidth / 2 - box.x - box.width / 2)
        - Math.abs(b.getBoundingClientRect().x + b.offsetWidth / 2 - box.x - box.width / 2))[0].dataset.date!;
  });
}
async function mouseDrag(page: Page, from: number, to: number) {
  const box = (await bar(page).boundingBox())!;
  await page.mouse.move(box.x + box.width * from, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * to, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
}
async function openDay(page: Page) {
  await setup(page, fixtures);
  await page.locator("#day-2026-10-28 .day-number").click();
  await visibleSelection(page);
}
async function expectDate(page: Page, date: string) {
  await expect(selected(page)).toHaveAttribute("data-date", date);
  await visibleSelection(page);
}

for (const width of [320, 1280]) for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`free day bar ${width}px ${colorScheme}`, () => {
    test.use({ viewport: { width, height: 844 }, colorScheme, reducedMotion: "reduce" });
    test("free wheel/trackpad movement and repeated mouse drags preserve selection; clicks and small jitter select", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
      await openDay(page);
      const strip = bar(page);
      await expect(strip.locator("button")).toHaveCount(731);
      await expect(strip.locator('button[tabindex="0"]')).toHaveCount(1);
      await expect(strip.locator('[data-date="2026-10-28"] span')).toHaveText("W");
      await expect(strip.locator('[data-date="2026-11-01"] span')).toHaveText("S");
      await expect(strip.locator('[data-date="2027-01-01"] span')).toHaveText("F");
      const geometry = await strip.evaluate((element) => ({ width: element.clientWidth,
        cell: element.querySelector("button")!.getBoundingClientRect().width, snap: getComputedStyle(element).scrollSnapType }));
      expect(geometry.width / geometry.cell).toBeCloseTo(7, 1);
      expect(geometry.snap).toBe("none");
      const box = (await strip.boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      const initial = await scrollLeft(page);
      await page.mouse.wheel(0, geometry.cell / 3);
      await expect.poll(() => scrollLeft(page)).toBeGreaterThan(initial + geometry.cell / 4);
      const fractional = await scrollLeft(page);
      await page.waitForTimeout(120);
      expect(Math.abs(await scrollLeft(page) - fractional)).toBeLessThan(1);
      expect(Math.abs(fractional / geometry.cell - Math.round(fractional / geometry.cell))).toBeGreaterThan(.1);
      await page.mouse.wheel(geometry.cell * 1.4, 0);
      await expect.poll(() => scrollLeft(page)).toBeGreaterThan(fractional + geometry.cell);
      for (let index = 0; index < 6; index++) {
        const before = await scrollLeft(page);
        const forward = index % 2 === 0;
        await mouseDrag(page, forward ? .8 : .2, forward ? .2 : .8);
        const after = await scrollLeft(page);
        expect(forward ? after - before : before - after).toBeGreaterThan(box.width * .4);
        await expect(selected(page)).toHaveAttribute("data-date", "2026-10-28");
        await expect(page.locator(".long-date")).toHaveText("Wednesday, October 28, 2026");
      }
      const target = await visibleOtherDay(page);
      await strip.locator(`[data-date="${target}"]`).click();
      await expectDate(page, target);
      const jitterDate = await visibleOtherDay(page);
      const jitter = (await strip.locator(`[data-date="${jitterDate}"]`).boundingBox())!;
      await page.mouse.move(jitter.x + jitter.width / 2, jitter.y + jitter.height / 2);
      await page.mouse.down();
      await page.mouse.move(jitter.x + jitter.width / 2 + 2, jitter.y + jitter.height / 2);
      await page.mouse.up();
      await expectDate(page, jitterDate);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect(errors).toEqual([]);
      await page.screenshot({ path: `test-results/day-bar-${width}-${colorScheme}.png` });
    });

    test("keyboard, month selections, Today reselection and resizing reveal the selected day", async ({ page }) => {
      await openDay(page);
      await selected(page).focus();
      for (const [key, date] of [["ArrowRight", "2026-10-29"], ["ArrowLeft", "2026-10-28"],
        ["ArrowUp", "2026-10-21"], ["ArrowDown", "2026-10-28"]]) {
        await page.keyboard.press(key);
        await expectDate(page, date);
        await expect(selected(page)).toBeFocused();
      }
      for (let index = 0; index < 10; index++) await page.keyboard.press("ArrowRight");
      await expectDate(page, "2026-11-07");
      await page.getByRole("button", { name: "Back to November", exact: true }).click();
      await month(page, "June 2026");
      await page.locator("#day-2026-06-17 .day-number").click();
      await expectDate(page, "2026-06-17");
      let box = (await bar(page).boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.wheel(0, 3000);
      await page.locator(".today-button").click();
      await expectDate(page, "2026-10-28");
      box = (await bar(page).boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      const before = await scrollLeft(page);
      await page.mouse.wheel(0, 3000);
      await expect.poll(() => scrollLeft(page)).toBeGreaterThan(before + 2000);
      await expect(selected(page)).toHaveAttribute("data-date", "2026-10-28");
      await page.locator(".today-button").click();
      await expectDate(page, "2026-10-28");
      await page.setViewportSize({ width: width === 320 ? 1280 : 320, height: 844 });
      await visibleSelection(page);
    });

    test("both date bounds clamp wheel, drag and keyboard navigation", async ({ page }) => {
      await openDay(page);
      const strip = bar(page);
      await expect(strip.locator("button").first()).toHaveAttribute("data-date", "2025-10-28");
      await expect(strip.locator("button").last()).toHaveAttribute("data-date", "2027-10-28");
      await expect(strip.locator('[data-date="2025-10-27"], [data-date="2027-10-29"]')).toHaveCount(0);
      await strip.locator("button").first().click();
      await expectDate(page, "2025-10-28");
      for (const key of ["ArrowLeft", "ArrowUp"]) await page.keyboard.press(key);
      await expectDate(page, "2025-10-28");
      await mouseDrag(page, .2, .8);
      expect(await scrollLeft(page)).toBe(0);
      await expectDate(page, "2025-10-28");
      await strip.locator("button").last().click();
      await expectDate(page, "2027-10-28");
      for (const key of ["ArrowRight", "ArrowDown"]) await page.keyboard.press(key);
      await expectDate(page, "2027-10-28");
      const box = (await strip.boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.wheel(0, 1_000_000);
      await mouseDrag(page, .8, .2);
      const remaining = await strip.evaluate((element) => element.scrollWidth - element.clientWidth - element.scrollLeft);
      expect(Math.abs(remaining)).toBeLessThan(1);
      await expectDate(page, "2027-10-28");
    });
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`native phone day bar ${colorScheme}`, () => {
    test.use({ viewport: { width: 320, height: 844 }, colorScheme, hasTouch: true, isMobile: true, reducedMotion: "reduce" });
    test("trusted finger gestures scroll freely without selecting, then a tap selects", async ({ page }) => {
      await setup(page, fixtures);
      await page.locator("#day-2026-10-28 .day-number").tap();
      await visibleSelection(page);
      const strip = bar(page);
      await expect(strip).toHaveCSS("touch-action", "pan-x pinch-zoom");
      const before = await scrollLeft(page);
      await nativeDayPan(page, -190);
      await expect.poll(() => scrollLeft(page)).toBeGreaterThan(before + 100);
      await expect(selected(page)).toHaveAttribute("data-date", "2026-10-28");
      // Hold the second touch before releasing, so the following tap is stationary.
      await nativeDayPan(page, 60, 180);
      await expect(selected(page)).toHaveAttribute("data-date", "2026-10-28");
      const date = await visibleOtherDay(page);
      await strip.locator(`[data-date="${date}"]`).tap();
      await expectDate(page, date);
    });
  });
}
