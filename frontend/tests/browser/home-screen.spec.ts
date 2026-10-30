import { expect, test } from "./test";

test("the served home-screen metadata and PNG icons load without CSP errors", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.locator('meta[http-equiv="Content-Security-Policy"]')).toHaveAttribute("content",
    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' https://site.web.api.espn.com; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'");
  await expect(page.locator('meta[name="apple-mobile-web-app-title"]')).toHaveAttribute("content", "kickoff");
  await expect(page.locator('meta[name="apple-mobile-web-app-capable"]')).toHaveAttribute("content", "yes");
  const manifestUrl = await page.locator('link[rel="manifest"]').evaluate((element: HTMLLinkElement) => element.href);
  const manifestResponse = await request.get(manifestUrl);
  expect(manifestResponse.status()).toBe(200);
  const manifest = await manifestResponse.json();
  expect(manifest.display).toBe("standalone");
  const appleIconUrl = await page.locator('link[rel="apple-touch-icon"]').evaluate((element: HTMLLinkElement) => element.href);
  for (const [url, size] of [
    [appleIconUrl, 180],
    ...manifest.icons.map((icon: { src: string; sizes: string }) => [new URL(icon.src, manifestUrl).href, Number(icon.sizes.split("x")[0])]),
  ] as [string, number][]) {
    const response = await request.get(url);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("image/png");
    const dimensions = await page.evaluate(async (src) => {
      const image = new Image();
      image.src = src;
      await image.decode();
      return [image.naturalWidth, image.naturalHeight];
    }, url);
    expect(dimensions).toEqual([size, size]);
  }
});
