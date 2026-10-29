import { expect, type Page } from "@playwright/test";
export const event = (id: string, date = "2026-10-28", fields = {}) => ({
  event_id: id, title: id, source: "fixture", sport: "soccer", league: "EPL", season: date.slice(0, 4),
  event_type: "match", subtitle: null, calendar_date: date, end_calendar_date: date,
  start_time_utc: null, start_time_local: null, timezone: null, status: "scheduled",
  venue: "Town Stadium", city: "London", country: "England", competition_phase: "regular_season", tags: [], participants: [],
  source_url: "https://example.com/schedule", ...fields,
});
export async function setup(page: Page, events: ReturnType<typeof event>[], options: { saved?: object; missing?: number; now?: string } = {}) {
  await page.clock.setFixedTime(new Date(options.now || "2026-10-28T17:00:00Z"));
  if (options.saved) await page.addInitScript((saved) => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify(saved));
  }, options.saved);
  await page.route("**/data/*.json", (route) => {
    const year = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    if (year === options.missing) return route.fulfill({ status: 404, body: "missing" });
    return route.fulfill({ json: {
      schema_version: "1", season: year, available_seasons: [2025, 2026, 2027], providers: [],
      updated_at: "2026-10-27T12:00:00Z", events: events.filter((item) => item.season === String(year)),
    } });
  });
  await page.goto("/");
  await expect(page.locator(".calendar-status")).not.toContainText("Loading");
}
export async function month(page: Page, label: string) {
  await page.getByRole("button", { name: /Show .* year calendar/ }).click();
  await page.getByRole("button", { name: `Open ${label}`, exact: true }).click();
}
export const agendaToggle = (page: Page) => page.getByRole("switch", { name: "Agenda view" });
export const chooser = (page: Page) => page.getByRole("dialog", { name: "Interests", exact: true });
