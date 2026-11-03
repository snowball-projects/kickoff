import { expect, test } from "./test";
import { agendaToggle, event, month, setup } from "./fixtures";
import { VIEW_KEY } from "../../src/agenda-state";

for (const width of [320, 1280]) for (const reducedMotion of ["reduce", "no-preference"] as const) {
  test(`day and Agenda retain selection and switch focus at ${width}px with ${reducedMotion} motion`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion });
    await setup(page, [event("Today fixture"), event("Yesterday fixture", "2026-10-27"),
      event("Upcoming fixture", "2026-10-29"), event("Selected fixture", "2026-11-04"),
      event("Next day fixture", "2026-11-05")]);
    await month(page, "November 2026");
    await page.locator("#day-2026-11-04 .day-number").click();
    const toggle = agendaToggle(page);
    const heading = page.getByRole("heading", { name: "Wednesday, November 4, 2026", exact: true });
    await expect(heading).toBeFocused();
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    const geometry = await heading.evaluate((h1) => {
      const rect = h1.getBoundingClientRect(), row = h1.parentElement!.getBoundingClientRect();
      const button = h1.parentElement!.querySelector("button")!.getBoundingClientRect();
      return { center: (rect.left + rect.right) / 2, rowCenter: (row.left + row.right) / 2,
        overlap: rect.right > button.left, height: row.height, font: getComputedStyle(h1).fontSize,
        overflow: document.documentElement.scrollWidth > innerWidth };
    });
    expect(geometry.center).toBeCloseTo(geometry.rowCenter, 0);
    expect(geometry.overlap).toBe(false);
    expect(geometry.height).toBe(54);
    expect(geometry.font).toBe("14px");
    expect(geometry.overflow).toBe(false);
    await toggle.click();
    await expect(toggle).toBeFocused();
    const agenda = page.getByRole("region", { name: "Agenda", exact: true });
    await expect(agenda).toContainText("Today fixture");
    await agenda.getByRole("button", { name: "Upcoming", exact: true }).click();
    await expect(agenda).toContainText("Upcoming fixture");
    // Escape in Agenda must not close the retained calendar day.
    await page.keyboard.press("Escape");
    for (let repeat = 0; repeat < 2; repeat++) {
      await toggle.focus();
      await toggle.press("Space");
      await expect(heading).toBeVisible();
      await expect(toggle).toBeFocused();
      await expect(page.locator('.week-strip [data-date="2026-11-04"] b')).toHaveClass(/selected/);
      await expect(page.locator(".all-day-strip")).toContainText("Selected fixture");
      await toggle.press("Enter");
      await expect(agenda).toBeVisible();
      await expect(toggle).toBeFocused();
      await expect(agenda.getByRole("button", { name: "Upcoming", exact: true })).toHaveAttribute("aria-pressed", "true");
    }
    await toggle.click();
    await expect(heading).toBeVisible();
    await page.getByRole("button", { name: "Thursday, November 5, 2026", exact: true }).click();
    await toggle.click();
    await toggle.click();
    await expect(page.getByRole("heading", { name: "Thursday, November 5, 2026", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Back to November", exact: true }).click();
    await expect(page.locator("#day-2026-11-05 .day-number")).toBeFocused();
    await expect(page.getByRole("heading", { name: "November", exact: true })).toBeVisible();
    await page.getByRole("button", { name: /Show .* year calendar/ }).click();
    await toggle.click();
    await toggle.click();
    await expect(page.getByRole("region", { name: "2026 calendar", exact: true })).toBeVisible();
    await toggle.click();
    expect(await page.evaluate((key) => localStorage.getItem(key), VIEW_KEY)).toBe("agenda");
    await page.reload();
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect(agenda).toBeVisible();
  });
}
