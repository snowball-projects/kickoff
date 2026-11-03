import { expect, test } from "./test";
import { agendaToggle, event, setup } from "./fixtures";
import type { Locator, Page } from "@playwright/test";

const infoName = "About kickoff and schedule coverage";
const today = "2026-10-28";
const fixtures = [
  ...Array.from({ length: 24 }, (_, index) => event(`Match ${index + 1}`)),
  event("Last minute match", today, { start_time_utc: "2026-10-29T04:59:00Z" }),
  event("Upcoming match", "2026-10-29"),
];

async function clearOfButtons(page: Page, content: Locator) {
  await expect(content).toBeInViewport();
  await expect.poll(async () => {
    const rect = (await content.boundingBox())!;
    const today = (await page.locator(".today-button").boundingBox())!;
    const info = (await page.getByRole("button", { name: infoName }).boundingBox())!;
    return Math.min(today.y, info.y) - rect.y - rect.height;
  }).toBeGreaterThanOrEqual(12);
}

async function scrollToEnd(scroller: Locator) {
  await scroller.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect.poll(() => scroller.evaluate((element) => element.scrollHeight - element.clientHeight - element.scrollTop)).toBeLessThanOrEqual(1);
}

for (const width of [320, 375, 1280]) {
  test(`top bar stays centered and stable in every view at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await setup(page, fixtures);
    const toggle = agendaToggle(page);
    const interests = page.getByRole("button", { name: "Interests", exact: true });
    const info = page.getByRole("button", { name: infoName });
    const initial = (await toggle.boundingBox())!;
    async function layout(agenda = false) {
      await expect(toggle).toHaveAttribute("aria-checked", String(agenda));
      const state = await page.locator(".topbar").evaluate((bar) => {
        const brand = bar.querySelector(".brand")!.getBoundingClientRect();
        const toggle = bar.querySelector(".view-slider")!.getBoundingClientRect();
        const interests = bar.querySelector(".interests-button")!.getBoundingClientRect();
        const lines = [...bar.querySelectorAll(".hamburger i")].map((line) => {
          const rect = line.getBoundingClientRect();
          return { center: (rect.left + rect.right) / 2, width: rect.width };
        });
        return { brandCenter: (brand.left + brand.right) / 2, brandRight: brand.right,
          toggleLeft: toggle.left, toggleRight: toggle.right, interestsLeft: interests.left,
          right: interests.right, lines, overflow: document.documentElement.scrollWidth > innerWidth };
      });
      expect(state.brandCenter).toBeCloseTo(width / 2, 1);
      expect(state.toggleLeft).toBeGreaterThanOrEqual(state.brandRight);
      expect(state.interestsLeft).toBeGreaterThanOrEqual(state.toggleRight);
      expect(state.right).toBeLessThanOrEqual(width - 8);
      expect(state.overflow).toBe(false);
      expect(state.lines[0].center).toBe(state.lines[1].center);
      expect(state.lines[1].center).toBe(state.lines[2].center);
      expect(state.lines[0].width).toBeGreaterThan(state.lines[1].width);
      expect(state.lines[1].width).toBeGreaterThan(state.lines[2].width);
      expect(await toggle.boundingBox()).toEqual(initial);
      const label = page.locator(".view-label");
      await expect(label).toHaveText(agenda ? "Agenda view" : "Calendar view");
      if (width < 700) await expect(label).toBeHidden();
      else await expect(label).toBeVisible();
      await expect(page.locator(".topbar").getByRole("button", { name: infoName })).toHaveCount(0);
    }
    await layout();
    await page.locator(`#day-${today} .day-number`).click();
    await layout();
    await expect(page.getByRole("heading", { name: "Wednesday, October 28, 2026", exact: true })).toBeVisible();
    await toggle.click();
    await expect(toggle).toBeFocused();
    await layout(true);
    await expect(page.getByRole("heading", { name: "Agenda", exact: true })).toHaveCount(0);
    await toggle.press("Enter");
    await expect(toggle).toBeFocused();
    await layout();
    await expect(page.getByRole("heading", { name: "Wednesday, October 28, 2026", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Back to October", exact: true }).click();
    await page.getByRole("button", { name: /Show .* year calendar/ }).click();
    await layout();
    await toggle.click(); await layout(true);
    await toggle.click(); await layout();
    await expect(page.getByRole("heading", { name: "2026", exact: true })).toBeVisible();
    await info.click();
    await expect(page.getByRole("dialog", { name: "About kickoff", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(info).toBeFocused();
    await interests.click();
    await expect(page.getByRole("dialog", { name: "Interests", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.screenshot({ path: testInfo.outputPath(`topbar-${width}.png`) });
  });

  for (const safeInset of [18, 34]) test(`floating buttons leave final content clear at ${width}px with ${safeInset}px bottom inset`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await setup(page, fixtures);
    // Override the value supplied by env(safe-area-inset-bottom) on a device with a home indicator.
    await page.evaluate((bottom) => document.documentElement.style.setProperty("--floating-bottom", `${bottom}px`), safeInset);
    const info = (await page.getByRole("button", { name: infoName }).boundingBox())!;
    const todayButton = (await page.locator(".today-button").boundingBox())!;
    expect(info.y).toBe(todayButton.y);
    expect(info.height).toBe(todayButton.height);
    expect(info.x + info.width).toBe(width - todayButton.x);
    expect(info.y + info.height).toBe(844 - safeInset);
    await scrollToEnd(page.locator(".month-scroll"));
    await clearOfButtons(page, page.locator(".calendar-week").last());
    await page.locator(".today-button").click();
    await page.locator(`#day-${today} .day-number`).click();
    await scrollToEnd(page.locator(".timeline-scroll"));
    await clearOfButtons(page, page.locator('[data-event-id="Last minute match"]'));
    await page.screenshot({ path: testInfo.outputPath(`day-end-${width}-${safeInset}.png`) });
    await agendaToggle(page).click();
    await scrollToEnd(page.locator(".agenda-scroll"));
    await clearOfButtons(page, page.locator(".agenda-row").last());
    await page.getByRole("button", { name: "Upcoming", exact: true }).click();
    await scrollToEnd(page.locator(".agenda-scroll"));
    await clearOfButtons(page, page.locator(".agenda-row").last());
    await clearOfButtons(page, page.getByRole("button", { name: "Show more", exact: true }));
    await page.screenshot({ path: testInfo.outputPath(`agenda-end-${width}-${safeInset}.png`) });
  });
}
