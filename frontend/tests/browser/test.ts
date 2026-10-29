import { test as base, expect } from "@playwright/test";

export { expect };
export const test = base.extend<{ csp: void }>({
  csp: [async ({ page }, use) => {
    const violations: string[] = [];
    page.on("console", (message) => {
      if (/content.security.policy|violat.*directive|refused to (?:load|execute|apply|connect)/i.test(message.text())) {
        violations.push(message.text());
      }
    });
    await use();
    expect(violations, "No Content Security Policy violations").toEqual([]);
  }, { auto: true }],
});
