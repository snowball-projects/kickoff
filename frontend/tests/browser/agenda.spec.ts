import { expect, test } from "./test";
import { agendaToggle, chooser, event, setup } from "./fixtures";
const events = [
  event("Yesterday fixture", "2026-12-30"), event("Date-only fixture", "2026-12-31"),
  event("Morning fixture", "2026-12-31", { start_time_utc: "2026-12-31T18:00:00Z" }),
  event("Evening fixture", "2026-12-31", { start_time_utc: "2027-01-01T00:00:00Z" }),
  event("Unverified clock", "2026-12-31", { start_time_local: "2026-12-31T09:00:00" }),
  event("Tournament span", "2026-12-30", { end_calendar_date: "2027-01-02" }),
  event("Postponed fixture", "2027-01-01", { status: "postponed" }),
  event("Last day fixture", "2027-01-07"), event("Outside next week", "2027-01-08"),
  event("Later fixture", "2027-04-12"), event("Other interest", "2027-05-20", { league: "NBA", sport: "basketball" }),
];
const options = { saved: { leagues: ["EPL"] }, now: "2027-01-01T02:00:00Z" };
for (const width of [390, 1280]) {
  test(`agenda content, local times, date spans, periods, sheet focus and saved slider at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await setup(page, events, options);
    await agendaToggle(page).click();
    const agenda = page.getByRole("region", { name: "Agenda", exact: true });
    await expect(agenda).toContainText("Thursday, December 31, 2026");
    await expect(agenda.locator(".agenda-title")).toHaveText(["Morning fixture", "Evening fixture", "Date-only fixture", "Tournament span", "Unverified clock"]);
    await expect(agenda.locator(".agenda-row", { hasText: "Morning fixture" })).toContainText("12:00 PM");
    await expect(agenda.locator(".agenda-row", { hasText: "Date-only fixture" })).toContainText("Time TBD");
    await expect(agenda.locator(".agenda-row", { hasText: "Tournament span" })).toContainText("Through Jan 2");
    const row = agenda.locator(".agenda-row", { hasText: "Morning fixture" });
    await row.click();
    await expect(page.getByRole("dialog")).toContainText("Morning fixture");
    await page.keyboard.press("Escape");
    await expect(row).toBeFocused();
    await agenda.getByRole("button", { name: "Yesterday", exact: true }).click();
    await expect(agenda).toContainText("Yesterday fixture");
    await agenda.getByRole("button", { name: "Upcoming", exact: true }).click();
    await expect(agenda).toContainText("Jan 1 – Jan 7 · Next 7 days");
    await expect(agenda.locator(".agenda-row", { hasText: "Postponed fixture" })).toContainText("postponed");
    await expect(agenda.locator(".agenda-row", { hasText: "Outside next week" })).toHaveCount(0);
    await agenda.getByRole("button", { name: "Show more", exact: true }).click();
    await expect(agenda.locator(".agenda-row", { hasText: "Later fixture" })).toHaveCount(1);
    await expect(agenda.getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
    await expect(agenda).toContainText("No later published events match your interests.");
    await page.locator(".today-button").click();
    await expect(agenda.getByRole("button", { name: "Today", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.reload();
    await expect(agendaToggle(page)).toHaveAttribute("aria-checked", "true");
    await expect(agenda.locator(".agenda-row", { hasText: "Morning fixture" })).toBeVisible();
  });
}
test.describe("Tokyo boundary", () => {
  test.use({ timezoneId: "Asia/Tokyo" });
  test("timed events move across years and date-only events stay on their source dates", async ({ page }) => {
    await setup(page, events, options);
    await agendaToggle(page).click();
    const agenda = page.getByRole("region", { name: "Agenda", exact: true });
    await expect(agenda).toContainText("Friday, January 1, 2027");
    await expect(agenda.locator(".agenda-row", { hasText: "Evening fixture" })).toContainText("9:00 AM");
    await expect(agenda.locator(".agenda-row", { hasText: "Date-only fixture" })).toHaveCount(0);
    await agenda.getByRole("button", { name: "Yesterday", exact: true }).click();
    await expect(agenda.locator(".agenda-row", { hasText: "Date-only fixture" })).toContainText("Time TBD");
  });
});
test("Show more filter changes retain scope, reveal sparse dates, and empty choices end immediately", async ({ page }) => {
  await setup(page, events, options);
  await agendaToggle(page).click();
  const agenda = page.getByRole("region", { name: "Agenda", exact: true });
  await agenda.getByRole("button", { name: "Upcoming", exact: true }).click();
  await agenda.getByRole("button", { name: "Show more", exact: true }).click();
  await expect(agenda).toContainText("Later fixture");
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await chooser(page).getByRole("button", { name: "Clear", exact: true }).click();
  await chooser(page).getByRole("checkbox", { name: "Select all Basketball", exact: true }).check();
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
  await expect(agenda.locator(".agenda-row")).toHaveCount(0);
  await agenda.getByRole("button", { name: "Show more", exact: true }).click();
  await expect(agenda).toContainText("Other interest");
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await chooser(page).getByRole("button", { name: "Clear", exact: true }).click();
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
  await expect(agenda.getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
});
test("midnight advances the local day without reloading", async ({ page }) => {
  await setup(page, events, options);
  await page.clock.install({ time: new Date("2027-01-01T05:59:30Z") });
  await agendaToggle(page).click();
  await page.clock.fastForward(60_000);
  await expect(page.getByRole("region", { name: "Agenda", exact: true })).toContainText("Friday, January 1, 2027");
});
test("missing upcoming snapshots show a recoverable coverage notice", async ({ page }) => {
  const config = { ...options, missing: 2027 as number | undefined };
  await setup(page, events, config);
  await agendaToggle(page).click();
  const agenda = page.getByRole("region", { name: "Agenda", exact: true });
  await agenda.getByRole("button", { name: "Upcoming", exact: true }).click();
  await expect(agenda).toContainText("No published schedule for 2027.");
  config.missing = undefined;
  await agenda.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(agenda).toContainText("Postponed fixture");
  await expect(agenda).not.toContainText("No published schedule for 2027.");
});
