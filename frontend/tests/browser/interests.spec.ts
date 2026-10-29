import { expect, test } from "@playwright/test";
import { agendaToggle, chooser, event, setup } from "./fixtures";
const events = [
  event("PGA stop", undefined, { league: "PGA_TOUR", sport: "golf" }),
  event("Masters Tournament", undefined, { league: "PGA_TOUR", sport: "golf" }),
  event("LPGA stop", undefined, { league: "LPGA_TOUR", sport: "golf" }),
  event("Women's major", undefined, { league: "GOLF_MAJORS_WOMEN", sport: "golf" }),
  event("Race", undefined, { league: "F1", sport: "motorsport", event_type: "race" }),
  event("Practice", undefined, { league: "F1", sport: "motorsport", event_type: "practice" }),
  event("Men Lead", undefined, { league: "IFSC_WORLD_CUP", sport: "climbing", tags: ["Men", "Lead"] }),
  event("Women Boulder", undefined, { league: "IFSC_WORLD_CUP", sport: "climbing", tags: ["Women", "Boulder"] }),
  event("Continental Europe", undefined, { league: "WEIGHTLIFTING_EUROPE", sport: "weightlifting", tags: ["Men"] }),
  event("Continental Asia", undefined, { league: "WEIGHTLIFTING_ASIA", sport: "weightlifting", tags: ["Women"] }),
];
for (const width of [390, 1280]) for (const pga of ["majors_only", "full_tour"]) for (const lpga of ["majors_only", "full_tour"]) {
  test(`saved golf choices ${pga}/${lpga} preserve save, cancel and reload at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const saved = { leagues: ["PGA_TOUR", "LPGA_TOUR", "F1"], golf_views: { PGA_TOUR: pga, LPGA_TOUR: lpga }, motorsport_view: "full_weekend" };
    await setup(page, events, { saved });
    await page.getByRole("button", { name: "Interests", exact: true }).click();
    const golf = chooser(page).getByRole("region", { name: "Golf interests" });
    await golf.locator("summary").click();
    const checkbox = golf.getByRole("checkbox", { name: "Majors only", exact: true });
    expect(await checkbox.evaluate((element: HTMLInputElement) => element.indeterminate)).toBe(pga !== lpga);
    await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!).golf_views)).toEqual(saved.golf_views);
    await page.getByRole("button", { name: "Interests", exact: true }).click();
    await golf.locator("summary").click();
    await checkbox.click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Interests", exact: true })).toBeFocused();
    await page.reload();
    await page.getByRole("button", { name: "Interests", exact: true }).click();
    await golf.locator("summary").click();
    expect(await checkbox.evaluate((element: HTMLInputElement) => element.indeterminate)).toBe(pga !== lpga);
    await checkbox.setChecked(true);
    await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
    await agendaToggle(page).click();
    const agenda = page.getByRole("region", { name: "Agenda", exact: true });
    await expect(agenda).toContainText("Masters Tournament");
    await expect(agenda).toContainText("Women's major");
    await expect(agenda).not.toContainText("PGA stop");
    await expect(agenda).not.toContainText("LPGA stop");
    await expect(agenda).toContainText("Practice");
  });
}
test("first visit starts in month with every league selected, and session/continental choices work", async ({ page }) => {
  await setup(page, events);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(agendaToggle(page)).toHaveAttribute("aria-checked", "false");
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await expect(chooser(page).getByRole("checkbox", { name: "Select all Climbing", exact: true })).toBeChecked();
  const climbing = chooser(page).getByRole("region", { name: "Climbing interests" });
  await climbing.locator("summary").click();
  await climbing.getByRole("checkbox", { name: "Women", exact: true }).uncheck();
  const lifting = chooser(page).getByRole("region", { name: "Weightlifting interests" });
  await lifting.locator("summary").click();
  await expect(lifting.getByRole("checkbox", { name: "Continental championships", exact: true })).toBeChecked();
  await lifting.getByRole("checkbox", { name: "Women", exact: true }).uncheck();
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
  await agendaToggle(page).click();
  const agenda = page.getByRole("region", { name: "Agenda", exact: true });
  await expect(agenda).toContainText("Men Lead");
  await expect(agenda).not.toContainText("Women Boulder");
  await expect(agenda).toContainText("Continental Europe");
  await expect(agenda).not.toContainText("Continental Asia");
});
test("blocked storage keeps first visit usable and interests active for this visit", async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(window, "localStorage", { get() { throw Error("blocked"); } }));
  await setup(page, events);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Interests", exact: true }).click();
  await chooser(page).getByRole("button", { name: "Clear", exact: true }).click();
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
  await expect(page.locator("#day-2026-10-28 .event-pill")).toHaveCount(0);
  await page.getByRole("button", { name: "About kickoff and schedule coverage" }).click();
  await expect(page.getByRole("dialog")).toContainText("browser storage is unavailable");
});
