import { expect, type Page } from "@playwright/test";
export const event = (id: string, date = "2026-10-28", fields = {}) => ({
  event_id: id, title: id, source: "fixture", sport: "soccer", league: "EPL", season: date.slice(0, 4),
  event_type: "match", subtitle: null, calendar_date: date, end_calendar_date: date,
  start_time_utc: null, start_time_local: null, timezone: null, status: "scheduled",
  venue: "Town Stadium", city: "London", country: "England", competition_phase: "regular_season", tags: [], participants: [],
  source_url: "https://example.com/schedule", ...fields,
});
export async function setup(page: Page, events: ReturnType<typeof event>[], options: { saved?: object; missing?: number; now?: string; hold?: Promise<void>; wait?: boolean } = {}) {
  await page.clock.setFixedTime(new Date(options.now || "2026-10-28T17:00:00Z"));
  if (options.saved) await page.addInitScript((saved) => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify(saved));
  }, options.saved);
  await page.route("**/data/*.json", async (route) => {
    await options.hold;
    const year = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    if (![2025, 2026, 2027].includes(year) || year === options.missing) return route.fulfill({ status: 404, body: "missing" });
    return route.fulfill({ json: {
      schema_version: "1", season: year, available_seasons: [2025, 2026, 2027], providers: [],
      updated_at: "2026-10-27T12:00:00Z", events: events.filter((item) => item.season === String(year)),
    } });
  });
  await page.goto("/");
  if (options.wait !== false) await expect(page.locator(".calendar-status")).not.toContainText("Loading");
}
export async function month(page: Page, label: string) {
  await page.getByRole("button", { name: /Show .* year calendar/ }).click();
  await page.getByRole("button", { name: `Open ${label}`, exact: true }).click();
}
export const agendaToggle = (page: Page) => page.getByRole("switch", { name: "Agenda view" });
export const chooser = (page: Page) => page.getByRole("dialog", { name: "Interests", exact: true });


export async function nativeDayPan(page: Page, distance: number, pauseBeforeRelease = 0) {
  const strip = page.locator(".week-strip");
  const box = (await strip.boundingBox())!;
  const x = box.x + box.width * (distance < 0 ? .8 : .2), y = box.y + box.height / 2;
  const session = await page.context().newCDPSession(page);
  await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y, id: 1 }] });
  for (let step = 1; step <= 8; step++) {
    await session.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x + distance * step / 8, y, id: 1 }] });
    await page.waitForTimeout(16);
  }
  if (pauseBeforeRelease) await page.waitForTimeout(pauseBeforeRelease);
  await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}
