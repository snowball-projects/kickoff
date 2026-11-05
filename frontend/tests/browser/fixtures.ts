import { expect, type Page } from "@playwright/test";
import type { ManifestResponse } from "../../src/types";
import { allPreferences, INTERESTS_KEY } from "../../src/interest-preferences";
import { publishedFiles } from "../published-fixture.mjs";
export const event = (id: string, date = "2026-10-28", fields = {}) => ({
  event_id: id, title: id, source: "fixture", sport: "soccer", league: "EPL",
  event_type: "match", subtitle: null, calendar_date: date, end_calendar_date: date,
  start_time_utc: null, start_time_local: null, status: "scheduled",
  venue: "Town Stadium", city: "London", country: "England", competition_phase: "regular_season", tags: [], participants: [],
  source_url: "https://example.com/schedule", ...fields,
});
export const teamLogoUrl = (path: string) => `https://a.espncdn.com/combiner/i?img=${encodeURIComponent(path)}&w=56&h=56`;
export async function mockTeamLogos(page: Page) {
  await page.route("https://a.espncdn.com/**", route => route.fulfill({ contentType: "image/svg+xml",
    headers: { "Cache-Control": "public, max-age=86400" }, body: '<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" />' }));
}
export async function setup(page: Page, events: ReturnType<typeof event>[], options: {
  saved?: object; firstVisit?: boolean; missing?: number; now?: string; hold?: Promise<void>; wait?: boolean;
  metadata?: Pick<ManifestResponse, "sources" | "updated_at" | "data_license_notice">;
  requests?: string[]; holdFiles?: Record<string, Promise<void>>; failedFiles?: string[];
} = {}) {
  await page.clock.setFixedTime(new Date(options.now || "2026-10-28T17:00:00Z"));
  if (!options.firstVisit) await page.addInitScript(({ saved, key }) => {
    if (!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify(saved));
  }, { saved: { ...allPreferences([...new Set(events.map((item) => item.league))]), ...options.saved }, key: INTERESTS_KEY });
  await page.route("**/data/*.json", async (route) => {
    const file = route.request().url().split("/").at(-1)!;
    options.requests?.push(file);
    await options.hold;
    await options.holdFiles?.[file];
    if (options.failedFiles?.includes(file)) return route.fulfill({ status: 503, body: "unavailable" });
    const files = publishedFiles([2025, 2026, 2027].filter((year) => year !== options.missing).map((year) => ({
      season: year, ...options.metadata, events: events.filter((item) => item.calendar_date?.slice(0, 4) === String(year)),
    })));
    return file in files ? route.fulfill({ json: files[file] }) : route.fulfill({ status: 404, body: "missing" });
  });
  await page.goto("/");
  if (options.wait !== false) await expect(page.locator(".calendar-status")).not.toContainText("Loading");
}
// Open the same source event through its visible day control, including the
// unreadable-pill fallback, without changing the desktop direct-pill flow.
export async function openDayEvent(page: Page, source: { event_id: string; title: string }) {
  const pill = page.locator(`.day-timeline-stage [data-event-id="${source.event_id}"]`);
  await expect(pill).toBeAttached();
  const hidden = await pill.getAttribute("aria-hidden") === "true";
  const control = hidden ? page.locator(`[id="${await pill.getAttribute("data-focus-return")}"]`) : pill;
  await expect(control).toBeVisible();
  await expect(control).toBeEnabled();
  if (hidden) await expect(control).toHaveText(/^\+\d+$/);
  await control.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const row = page.locator(`[id="sheet-${source.event_id}"]`);
  if (await row.count()) {
    // Flags follow the source title in <b>; compare the literal title itself.
    expect(await row.locator("b").evaluate(element => [...element.childNodes]
      .filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent).join(""))).toBe(source.title);
    await row.click();
  }
  await expect(page.locator(".event-details h3")).toContainText(source.title);
  return control;
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
