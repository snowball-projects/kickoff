import { expect, test } from "@playwright/test";

test("group choices are independent, mixed, collapsible and preserve saved leagues", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-09-11T17:00:00Z"));
  await page.goto("/");
  const chooser = page.getByRole("dialog", { name: "Follow your sports" });
  await expect(chooser).toBeVisible();
  for (const name of ["Soccer", "Motorsports", "American football", "Combat sports", "Golf", "Miscellaneous"])
    await expect(chooser.getByRole("checkbox", { name: `Select all ${name}`, exact: true })).toBeVisible();
  const soccer = chooser.getByRole("region", { name: "Soccer interests" });
  const allSoccer = soccer.getByRole("checkbox", { name: "Select all Soccer", exact: true });
  await allSoccer.check();
  await soccer.locator("summary").click();
  await expect(soccer.getByRole("checkbox", { name: "England Premier League", exact: true })).toBeChecked();
  const championship = soccer.getByRole("checkbox", { name: "England EFL Championship · England", exact: true });
  await expect(championship).toBeChecked();
  await expect(soccer.getByRole("img", { name: "England", exact: true })).toHaveCount(2);
  await page.screenshot({ path: "test-results/soccer-flags-desktop.png" });
  await championship.uncheck();
  await expect(allSoccer).toHaveJSProperty("indeterminate", true);
  await allSoccer.check();
  await expect(championship).toBeChecked();
  await soccer.locator("summary").click();
  await allSoccer.uncheck();
  await chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true }).check();
  await chooser.locator("summary").filter({ hasText: /^Miscellaneous$/ }).click();
  await chooser.getByRole("checkbox", { name: "IWF Worlds", exact: true }).check();
  await chooser.getByRole("button", { name: "Show my calendar" }).click();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("kickoff.interests.v1")!))).toEqual(["F1", "NASCAR_CUP", "INDYCAR", "IWF_WORLDS"]);
  await page.reload();
  await expect(chooser).toHaveCount(0);
  await page.getByRole("button", { name: "Interests · 4", exact: true }).click();
  await expect(chooser.getByRole("checkbox", { name: "Select all Motorsports", exact: true })).toBeChecked();
  await expect(chooser.getByRole("checkbox", { name: "Select all Miscellaneous", exact: true })).toHaveJSProperty("indeterminate", true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await chooser.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: "test-results/grouped-interests-mobile.png" });
});
