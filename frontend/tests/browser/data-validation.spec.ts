import { expect, test } from "@playwright/test";

for (const field of ["title", "calendar_date", "tags", "participants", "status"]) {
  test(`missing ${field} shows a data error and Retry recovers`, async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-09-10T17:00:00Z"));
    await page.addInitScript(() => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues: ["EPL"], golf_views: { PGA_TOUR: "full_tour", LPGA_TOUR: "full_tour" }, motorsport_view: "race_only" })));
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let broken = true;
    await page.route("**/data/*.json", (route) => {
      if (!route.request().url().endsWith("/2026.json")) return route.fulfill({ status: 404, body: "missing" });
      const event: Record<string, unknown> = {
        event_id: "schema-retry", source: "fixture", season: "2026", status: "scheduled", competition_phase: "regular_season", title: "Recovered fixture", sport: "soccer", league: "EPL", event_type: "match",
        calendar_date: "2026-09-10", end_calendar_date: "2026-09-10", tags: [], participants: [],
        start_time_utc: null,
      };
      if (broken) delete event[field];
      return route.fulfill({ json: {
        schema_version: "1", season: 2026, available_seasons: [2026], providers: [], events: [event],
      } });
    });
    await page.goto("/");
    await expect(page.getByText(/2026 is unavailable: invalid snapshot/).first()).toBeVisible();
    await expect(page.locator("#day-2026-09-10 .event-pill")).toHaveCount(0);
    broken = false;
    await page.getByRole("button", { name: /Retry/ }).first().click();
    await expect(page.locator("#day-2026-09-10 .event-pill")).toContainText("Recovered fixture");
    await expect(page.getByText(/2026 is unavailable: invalid snapshot/)).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}
