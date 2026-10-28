import { expect, test, type Page } from "@playwright/test";

const categories = [
  ["EPL", "soccer", "Arsenal v Everton"], ["F1", "motorsport", "Monaco Grand Prix"],
  ["NFL", "football", "Ravens at Chiefs"], ["NBA", "basketball", "Celtics at Knicks"],
  ["MLB", "baseball", "Mets at Cubs"], ["NHL", "hockey", "Canadiens at Maple Leafs"],
  ["UFC", "mma", "Fighter A v Fighter B"], ["PGA_TOUR", "golf", "Masters Tournament"],
  ["IFSC_WORLD_CUP", "climbing", "Men's Boulder Qualification"], ["IWF_WORLDS", "weightlifting", "Men's 79kg Group A"],
];
const events = categories.map(([league, sport, title], index) => ({
  event_id: `identity-${league}`, source: "offline-browser-fixture", season: "2026", league, sport,
  title, event_type: sport === "motorsport" ? "race" : "game",
  subtitle: null, calendar_date: "2026-06-07", end_calendar_date: "2026-06-07",
  start_time_utc: null, start_time_local: null, timezone: null, status: "scheduled",
  venue: null, city: null, region: null, round_or_stage: null, competition_phase: "regular_season",
  country: index === 1 ? "MC" : index === 8 ? "Czechia" : index === 9 ? "Georgia" : null,
  tags: [], participants: [], home_participant: null, away_participant: null,
}));
const international = {
  ...events[0], event_id: "national-teams", league: "FIFA_WORLD_CUP", title: "Japan v France",
  participants: [{ name: "Japan", entity_type: "national_team", country_code: "JP" },
    { name: "France", entity_type: "national_team", country_code: "FR" }],
};
const clubs = { ...international, event_id: "clubs", league: "UEFA_CHAMPIONS_LEAGUE", title: "Club Japan v Club France",
  participants: international.participants.map((participant) => ({ ...participant, entity_type: "team" })),
};
const group = [0, 1].map((index) => ({ ...events[8], event_id: `climbing-${index}`, event_type: "session",
  title: `Prague · ${index ? "Men's Lead Final" : "Women's Lead Final"}`, tags: ["Lead", index ? "Men" : "Women"],
}));
const mixed = [0, 1].map((index) => ({ ...events[9], event_id: `mixed-${index}`, league: "IWF_JUNIOR_WORLDS",
  country: index ? "Japan" : "China", title: `Mixed fixture ${index}`,
}));
const fixture = [...events, international, clubs, ...group, ...mixed,
  { ...events[9], event_id: "multinational", league: "IWF_YOUTH_WORLDS", country: "US/Canada", title: "Multinational fixture" },
];

async function open(page: Page) {
  await page.clock.setFixedTime(new Date("2026-06-07T12:00:00Z"));
  await page.addInitScript((leagues) => localStorage.setItem("kickoff.interests.v2", JSON.stringify({ leagues })),
    [...new Set(fixture.map((event) => event.league))]);
  await page.route("**/data/*.json", async (route) => {
    const year = route.request().url().match(/(\d{4})\.json/)?.[1];
    if (!year) return route.continue();
    await route.fulfill({ json: { schema_version: "1", season: Number(year), available_seasons: [2025, 2026, 2027], providers: [],
      events: year === "2026" ? fixture : [],
    } });
  });
  await page.goto("/");
}

test("host and national-team flags describe facts in calendar, detail and agenda", async ({ page }) => {
  const external: string[] = [];
  page.on("request", (request) => { if (!request.url().startsWith("http://127.0.0.1:")) external.push(request.url()); });
  await open(page);
  const day = page.locator("#day-2026-06-07");
  const f1 = day.locator(".month-single").filter({ hasText: "Monaco Grand Prix" });
  await expect(f1.getByRole("img", { name: "Host country: Monaco" })).toHaveText("🇲🇨");
  await expect(day.locator(".competition-chip").filter({ hasText: "Prague" }).getByRole("img", { name: "Host country: Czechia" })).toBeVisible();
  await expect(day.locator(".competition-chip").filter({ hasText: "Junior Worlds" }).getByRole("img")).toHaveCount(0);
  const national = day.locator(".month-single").filter({ hasText: "Japan v France" }).filter({ hasNotText: "Club" });
  await expect(national.getByRole("img", { name: "Japan: Japan" })).toHaveText("🇯🇵");
  await expect(national.getByRole("img", { name: "France: France" })).toHaveText("🇫🇷");
  for (const title of ["Club Japan v Club France", "Ravens at Chiefs", "Multinational fixture"])
    await expect(day.locator(".month-single").filter({ hasText: title }).getByRole("img")).toHaveCount(0);
  await f1.click();
  const details = page.locator("#details-identity-F1");
  await expect(details.getByRole("img", { name: "Host country: Monaco" })).toBeVisible();
  await expect(details.locator(".sport-icon")).toHaveAttribute("aria-hidden", "true");
  await page.getByRole("button", { name: "Close day" }).click();
  await page.getByRole("group", { name: "Schedule view", exact: true }).getByRole("button", { name: "Agenda", exact: true }).click();
  const agenda = page.getByRole("region", { name: "Agenda", exact: true });
  await expect(agenda.locator(".agenda-row").filter({ hasText: "Monaco Grand Prix" }).getByRole("img", { name: "Host country: Monaco" })).toBeVisible();
  await expect(agenda.locator(".agenda-row").filter({ hasText: "Japan v France" }).filter({ hasNotText: "Club" }).getByRole("img", { name: "Japan: Japan" })).toBeVisible();
  expect(external).toEqual([]);
});

for (const colorScheme of ["light", "dark"] as const) {
  test(`bundled category icons inherit text colour, stay decorative and fit narrow ${colorScheme} screens`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page);
    const icons = page.locator("#day-2026-06-07 .sport-icon");
    await expect(icons.first()).toBeVisible();
    expect(await icons.evaluateAll((nodes) => [...new Set(nodes.map((node) => node.getAttribute("data-sport")))].length)).toBe(10);
    expect(await icons.evaluateAll((nodes) => nodes.every((node) => node.getAttribute("aria-hidden") === "true"
      && node.getAttribute("focusable") === "false" && getComputedStyle(node).fill === getComputedStyle(node).color))).toBe(true);
    for (const event of events) {
      const row = page.locator("#day-2026-06-07 .month-single").filter({ hasText: event.title });
      await expect(row.locator("b")).toBeHidden();
      await expect(row.locator(".sport-icon")).toBeVisible();
      await expect(row).toHaveAccessibleName(new RegExp(event.league === "IFSC_WORLD_CUP" ? "World Climbing" : event.league === "IWF_WORLDS" ? "IWF Worlds" : event.league === "PGA_TOUR" ? "PGA Tour" : event.league === "EPL" ? "Premier League" : event.league));
    }
    await page.screenshot({ path: `test-results/event-identity-${colorScheme}-calendar-mobile.png` });
    await page.getByRole("button", { name: /^Interests ·/ }).click();
    const chooser = page.getByRole("dialog", { name: "Interests", exact: true });
    await expect(chooser.locator("summary .sport-icon")).toHaveCount(10);
    await chooser.getByRole("region", { name: "Climbing interests" }).locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(chooser.getByRole("checkbox", { name: "World Cups", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/event-identity-${colorScheme}-mobile.png` });
  });
}
