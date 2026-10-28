import { expect, type Page } from "@playwright/test";

export async function expandDayGroups(page: Page) {
  const panel = page.getByRole("complementary", { name: "Day events" });
  const toggles = panel.locator('.timeline-group-toggle[aria-expanded="false"]');
  while (await toggles.count()) await toggles.first().click();
  return panel;
}

export async function openDayEvent(page: Page, title?: string | RegExp) {
  const panel = await expandDayGroups(page);
  const pills = panel.locator('.timeline-pill[data-event-id]');
  await (title ? pills.filter({ hasText: title }) : pills).first().click();
  await expect(panel.getByRole("region", { name: "Event details" })).toBeVisible();
  return panel;
}
