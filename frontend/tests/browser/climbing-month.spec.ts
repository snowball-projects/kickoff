import { openDayEvent } from "./timeline-helpers";
import { expect, test, type Page } from "@playwright/test";

async function filters(page: Page, discipline: string) {
  await page.getByRole("button", { name: /^Interests ·/ }).click();
  const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
  const climbing = chooser.getByRole("region", { name: "Climbing interests" });
  await climbing.locator("summary").click();
  await climbing.getByRole("checkbox", { name: "Women", exact: true }).uncheck();
  for (const name of ["Boulder", "Lead", "Speed"]) {
    await climbing.getByRole("checkbox", { name, exact: true }).setChecked(name === discipline);
  }
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
}

for (const fixture of [
  { zone: "Europe/London", allFirst: "09:30", first: "09:30", clock: "9:30 AM" },
  { zone: "Asia/Tokyo", allFirst: "02:30", first: "17:30", clock: "5:30 PM" },
]) {
  test.describe(`reviewed World Cup rounds in ${fixture.zone}`, () => {
    test.use({ timezoneId: fixture.zone });
    test("month grouping follows filters and local days; day timeline shares grouping while the list stays flat", async ({ page }) => {
      await page.clock.setFixedTime(new Date("2026-06-07T08:00:00Z"));
      await page.addInitScript(() => {
        if (!localStorage.getItem("kickoff.interests.v2")) {
          localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["IFSC_WORLD_CUP"] }));
        }
      });
      await page.goto("/");
      const day = page.locator("#day-2026-06-07");
      await expect(day.locator(".competition-chip")).toContainText(`Prague · 4 sessions · from ${fixture.allFirst}`);
      await expect(day.locator(".hidden-events")).toHaveCount(0);
      await filters(page, "Lead");
      const chip = day.locator(".competition-chip");
      await expect(chip).toContainText(`Prague · 2 sessions · from ${fixture.first}`);
      await expect(day.locator(".hidden-events")).toHaveCount(0);
      await chip.click();
      await expect(day.locator(".competition-event")).toHaveCount(2);
      await expect(day.locator(".competition-event")).toContainText(["Men's Lead Semi-final", "Men's Lead Final"]);
      await expect(day.locator(".competition-event-time")).toHaveText([`Session starts ${fixture.clock}`, "Time TBD"]);
      await expect(day.locator(".competition-events [aria-expanded]")).toHaveCount(0);
      await expect(day.locator(".hidden-events")).toHaveText("2 more events hidden by your filters");
      await day.locator(".hidden-events").click();
      await expect(chip).toHaveAttribute("aria-expanded", "true");
      await expect(page.getByRole("complementary", { name: "Day events" })).toHaveCount(0);
      await day.locator(".competition-event").first().click();
      const detail = page.getByRole("complementary", { name: "Day events" });
      await openDayEvent(page, "Men's Lead Semi-final");
      await expect(detail.locator("article")).toHaveCount(1);
      await expect(detail.locator(".timeline-pill[data-event-id]")).toHaveCount(2);
      await expect(detail.locator(".competition-chip")).toHaveCount(0);
      await expect(detail).not.toContainText("Women's");
      await page.getByRole("button", { name: "Close day" }).click();
      await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Agenda", exact: true }).click();
      const agenda = page.getByRole("region", { name: "Agenda", exact: true });
      await expect(agenda.locator(".agenda-row")).toHaveCount(2);
      await expect(agenda.locator(".competition-chip")).toHaveCount(0);
      await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Calendar", exact: true }).click();
      await filters(page, "Boulder");
      await expect(day.locator(".event-pill")).toHaveCount(0);
      await expect(page.locator("#day-2026-06-04 .event-pill")).toHaveCount(0);
      await expect(page.locator("#day-2026-06-03 .competition-chip")).toHaveCount(0);
      await expect(page.locator("#day-2026-06-03 .month-single")).toContainText("Men's Boulder Qualification");
      if (fixture.zone === "Europe/London") {
        await expect(page.locator("#day-2026-06-05 .competition-chip")).toContainText("Prague · 2 sessions · from 11:00");
      } else {
        await expect(page.locator("#day-2026-06-05 .month-single")).toContainText("Men's Boulder Semi-final");
        await expect(page.locator("#day-2026-06-06 .month-single")).toContainText("Men's Boulder Final");
        await expect(page.locator("#day-2026-06-05 .competition-chip")).toHaveCount(0);
      }
      await page.screenshot({ path: `test-results/climbing-month-${fixture.zone.replace("/", "-")}.png` });
    });
  });
}
