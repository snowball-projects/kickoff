import { build } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { expect, test } from "./test";
import { teamLogoUrl } from "./fixtures";

// Exercise the real component with changing props; this harness stays in memory
// and never becomes a production entry point or public asset.
test("URL and loading changes reset visibility before any offscreen request", async ({ page }) => {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const component = fileURLToPath(new URL("../../src/TeamLogo.tsx", import.meta.url));
  const result = await build({ root, configFile: false, publicDir: false, logLevel: "silent", plugins: [react(), {
    name: "team-logo-test-harness",
    resolveId(id) { if (id === "virtual:team-logo-test") return id; },
    load(id) { if (id === "virtual:team-logo-test") return `
      import React from 'react';
      import { createRoot } from 'react-dom/client';
      import { flushSync } from 'react-dom';
      import TeamLogo from ${JSON.stringify(component)};
      const root = createRoot(document.getElementById('root'));
      window.renderLogo = (url, load = true) => flushSync(() => root.render(React.createElement(TeamLogo,
        { participant: { name: 'Source team', participant_id: '1', short_name: null, role: 'home', entity_type: 'team', logo_url: url }, load })));
    `; },
  }], build: { write: false, minify: false, rollupOptions: { input: "virtual:team-logo-test", output: { format: "iife" } } } });
  const output = Array.isArray(result) ? result[0].output : result.output;
  const code = output.find(item => item.type === "chunk")!.code;
  const requests: string[] = [];
  const session = await page.context().newCDPSession(page);
  await session.send("Network.enable");
  await session.send("Network.setCacheDisabled", { cacheDisabled: true });
  await page.route("https://a.espncdn.com/**", route => {
    requests.push(route.request().url());
    return route.fulfill({ contentType: "image/svg+xml", headers: { "Cache-Control": "no-store" },
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" />' });
  });
  await page.setContent('<div id="root"></div>');
  await page.addScriptTag({ content: code });
  const render = (url: string, load: boolean) => page.evaluate(({ url, load }) => {
    (window as unknown as { renderLogo: (url: string, load: boolean) => void }).renderLogo(url, load);
  }, { url, load });
  const frames = () => page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const a = teamLogoUrl("/i/teamlogos/nfl/500/a.png"), b = teamLogoUrl("/i/teamlogos/nfl/500/b.png");
  const image = page.locator(".team-logo");
  await render(a, true);
  await expect(image).toHaveJSProperty("naturalWidth", 56);
  expect(requests).toEqual([a]);
  await page.locator("#root").evaluate(element => { element.style.marginTop = "5000px"; });
  await render(b, true);
  await frames();
  await expect(image).not.toHaveAttribute("src");
  await render(a, true);
  await frames();
  await expect(image).not.toHaveAttribute("src");
  expect(requests).toEqual([a]);
  await render(a, false);
  await frames();
  await expect(image).not.toHaveAttribute("src");
  await render(a, true);
  await frames();
  await expect(image).not.toHaveAttribute("src");
  expect(requests).toEqual([a]);
  await page.locator("#root").evaluate(element => { element.style.marginTop = "0"; });
  await expect(image).toHaveAttribute("src", a);
  await expect(image).toHaveJSProperty("naturalWidth", 56);
  // Chromium may retain decoded images even with HTTP cache disabled.
  expect(requests.every(url => url === a)).toBe(true);
});
