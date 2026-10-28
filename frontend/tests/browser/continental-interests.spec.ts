import { expandDayGroups } from "./timeline-helpers";
import { expect, test, type Page } from "@playwright/test";

test.use({ timezoneId: "UTC" });

const continents = ["WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE",
  "WEIGHTLIFTING_OCEANIA", "WEIGHTLIFTING_PAN_AMERICA"];
const climbingContinents = ["CLIMBING_EUROPE", "CLIMBING_ASIA", "CLIMBING_AFRICA", "CLIMBING_OCEANIA", "CLIMBING_PAN_AMERICA"];
const savedLeagues = ["WEIGHTLIFTING_EUROPE", "CLIMBING_EUROPE", "IFSC_WORLD_CUP", "IWF_WORLDS", "OLD_SAVED_LEAGUE"];
const climbingFamilies = {
  IFSC_WORLDS: "World Championships", IFSC_YOUTH_WORLDS: "Youth World Championships",
  IFSC_PARA_WORLD_CUP: "Para World Cups", IFSC_PARA_WORLDS: "Para World Championships",
  CLIMBING_OLYMPIC_QUALIFIERS: "Olympic qualifiers", CLIMBING_CONTINENTAL_CUP: "Continental Cups",
  CLIMBING_YOUTH_CONTINENTAL_CUP: "Youth Continental Cups", CLIMBING_CHALLENGER: "Challenger",
  CLIMBING_NATIONS_GRAND_FINALE: "Nations Grand Finale", CLIMBING_ASIAN_GAMES: "Asian Games",
  CLIMBING_ASIAN_BEACH_GAMES: "Asian Beach Games", CLIMBING_EUROPEAN_GAMES: "European Games",
  CLIMBING_PAN_AM_GAMES: "Pan Am Games",
};
const event = (id: string, fields = {}) => ({
  event_id: id, source: "offline-browser-fixture", season: "2026", status: "scheduled",
  competition_phase: "regular_season", league: "IFSC_WORLD_CUP", sport: "climbing", event_type: "session", title: id,
  calendar_date: "2026-09-10", end_calendar_date: "2026-09-10", start_time_utc: "2026-09-10T09:00:00Z",
  start_time_local: null, timezone: null, subtitle: null, venue: null, city: null, region: null,
  country: null, round_or_stage: null, tags: [], participants: [], home_participant: null,
  away_participant: null, home_participant_name: null, away_participant_name: null, week_label: null,
  is_regular_season: true, is_postseason: false, is_exhibition: false, is_support_event: false, ...fields,
});
const events = [
  ...["Men", "Women"].flatMap((gender) => ["Boulder", "Lead", "Speed"].flatMap((discipline) =>
    ["qualification", "semifinal", "final"].map((round, index) => event(`${gender}-${discipline}-${round}`, {
      title: `Fixture World Cup · ${gender}'s ${discipline} ${round}`, tags: [gender, discipline],
      start_time_utc: `2026-09-10T${["09", "12", "18"][index]}:00:00Z`,
    })))),
  ...continents.flatMap((league) => ["Men", "Women"].map((gender) => event(`${league}-${gender}`, {
    league, sport: "weightlifting", title: `${league === "WEIGHTLIFTING_EUROPE" ? "European Championships" : league} · ${gender}'s 60 kg, Group A`,
    tags: [gender],
  }))),
  ...climbingContinents.flatMap((league) => ["Men", "Women"].map((gender) => event(`${league}-${gender}`, {
    league, title: `${league === "CLIMBING_EUROPE" ? "European Championships" : league} · ${gender}'s Boulder final`,
    tags: [gender, "Boulder"],
  }))),
  ...Object.keys(climbingFamilies).map((league) => event(league, {
    league, calendar_date: "2026-09-11", end_calendar_date: "2026-09-11", start_time_utc: null,
  })),
  event("worlds", { league: "IWF_WORLDS", sport: "weightlifting", title: "IWF World Championships · Men's 60 kg, Group A", tags: ["Men"] }),
];
const chooser = (page: Page) => page.getByRole("dialog", { name: "Interests", exact: true });
const lifting = (page: Page) => chooser(page).getByRole("region", { name: "Weightlifting interests" });
const climbing = (page: Page) => chooser(page).getByRole("region", { name: "Climbing interests" });
const continental = (region: ReturnType<typeof lifting>) => region.getByRole("checkbox", { name: "Continental championships", exact: true });
async function edit(page: Page) {
  await page.getByRole("button", { name: /^Interests ·/ }).click();
  await lifting(page).locator("summary").click();
  await climbing(page).locator("summary").click();
}
async function save(page: Page) {
  await chooser(page).getByRole("button", { name: "Show my calendar" }).click();
}
async function saved(page: Page) {
  return page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v2")!));
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-10T08:00:00Z"));
  await page.addInitScript((leagues) => {
    if (!localStorage.getItem("kickoff.interests.v2")) localStorage.setItem("kickoff.interests.v2", JSON.stringify({
      leagues, climbing: { genders: ["Men"], disciplines: ["Boulder"] }, weightlifting: { genders: ["Men"] },
    }));
  }, savedLeagues);
  await page.route("**/data/*.json", async (route) => {
    const season = Number(route.request().url().match(/(\d{4})\.json$/)?.[1]);
    await route.fulfill({ json: { schema_version: "1", season, providers: [], available_seasons: [2026], events: season === 2026 ? events : [] } });
  });
  await page.goto("/");
});

test("saved continental subsets stay mixed and unchanged until the combined checkbox is toggled", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await edit(page);
  for (const region of [lifting(page), climbing(page)]) {
    await expect(continental(region)).toHaveCount(1);
    await expect(continental(region)).toHaveJSProperty("indeterminate", true);
    await expect(region.getByRole("checkbox", { name: /African Championships|Asian Championships|European Championships|Oceania Championships|Pan-American Championships/ })).toHaveCount(0);
  }
  for (const name of Object.values(climbingFamilies))
    await expect(climbing(page).getByRole("checkbox", { name, exact: true })).not.toBeChecked();
  await expect(chooser(page).getByRole("region", { name: "Miscellaneous interests" })).toHaveCount(0);
  await expect(lifting(page).getByRole("checkbox", { name: "IWF Worlds", exact: true })).toBeChecked();
  expect(await chooser(page).evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  await save(page);
  expect((await saved(page)).leagues).toEqual(savedLeagues);
  await page.reload();
  const day = page.locator("#day-2026-09-10");
  await expect(day).toContainText("European Championships · Men's 60 kg, Group A");
  await expect(day).toContainText("European Championships · Men's Boulder final");
  await expect(day).not.toContainText("WEIGHTLIFTING_AFRICA");
  await expect(day).not.toContainText("CLIMBING_AFRICA");
  await expect(day).not.toContainText("Women's");
  await edit(page);
  for (const region of [lifting(page), climbing(page)]) {
    await expect(continental(region)).toHaveJSProperty("indeterminate", true);
    await continental(region).focus();
    await page.keyboard.press(" ");
    await expect(continental(region)).toBeChecked();
    await expect(continental(region)).toHaveJSProperty("indeterminate", false);
  }
  await expect(climbing(page).getByRole("checkbox", { name: "Continental Cups", exact: true })).not.toBeChecked();
  await expect(climbing(page).getByRole("checkbox", { name: "Youth Continental Cups", exact: true })).not.toBeChecked();
  await save(page);
  expect((await saved(page)).leagues).toEqual([...savedLeagues,
    ...continents.filter((league) => !savedLeagues.includes(league)), ...climbingContinents.slice(1)]);
  await edit(page);
  for (const region of [lifting(page), climbing(page)]) await continental(region).uncheck();
  await save(page);
  expect((await saved(page)).leagues).toEqual(savedLeagues.filter((league) => ![...continents, ...climbingContinents].includes(league)));
  await expect(day).not.toContainText("European Championships");
  await expect(day).toContainText("IWF World Championships");
  await edit(page);
  for (const region of [lifting(page), climbing(page)]) await expect(continental(region)).not.toBeChecked();
  await chooser(page).getByRole("button", { name: "Select all", exact: true }).click();
  for (const region of [lifting(page), climbing(page)]) await expect(continental(region)).toBeChecked();
  await expect(climbing(page).getByRole("checkbox", { name: "Women", exact: true })).toBeChecked();
  await chooser(page).getByRole("button", { name: "Clear", exact: true }).click();
  for (const region of [lifting(page), climbing(page)]) {
    await expect(continental(region)).not.toBeChecked();
    await expect(continental(region)).toHaveJSProperty("indeterminate", false);
  }
  await save(page);
  expect((await saved(page)).leagues).toEqual([]);
  await expect(day.locator(".event-pill")).toHaveCount(0);
});

test("men's boulder intersects grouped interests without changing month counts or hidden rows", async ({ page }) => {
  const day = page.locator("#day-2026-09-10");
  const cup = day.getByRole("button", { name: "Fixture World Cup · 3 sessions · from 09:00", exact: true });
  await expect(cup).toHaveAttribute("aria-expanded", "false");
  await expect(day.locator(".hidden-events")).toHaveCount(0);
  await cup.click();
  await expect(day.locator(".competition-event")).toHaveCount(3);
  await expect(day.locator(".competition-event")).toContainText(["Men's Boulder qualification", "Men's Boulder semifinal", "Men's Boulder final"]);
  await expect(day.locator(".hidden-events")).toHaveText("15 more events hidden by your filters");
  await day.locator(".hidden-events").click();
  await expect(cup).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("complementary", { name: "Day events" })).toHaveCount(0);
  await day.locator(".day-number").click();
  const detail = page.getByRole("complementary", { name: "Day events" });
  await expandDayGroups(page);
  await expect(detail.locator(".timeline-pill[data-event-id]")).toHaveCount(6);
  await expect(detail).toContainText("European Championships · Men's 60 kg, Group A");
  await expect(detail).not.toContainText("Women's");
  await expect(detail).not.toContainText("Men's Lead");
  await expect(detail.locator(".competition-chip")).toHaveCount(0);
  await page.getByRole("button", { name: "Close day" }).click();
  await page.getByRole("button", { name: "Agenda", exact: true }).click();
  const agenda = page.getByRole("region", { name: "Agenda", exact: true });
  await expect(agenda.locator(".agenda-row")).toHaveCount(6);
  await expect(agenda.locator(".competition-chip")).toHaveCount(0);
  await expect(agenda).not.toContainText("Women's");
  await expect(agenda).not.toContainText("Men's Speed");
});
