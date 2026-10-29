import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
const head = html.split("</head>")[0];
const tags = [...head.matchAll(/<(link|meta)\s+([^>]+)>/g)].map(([, tag, attributes]) => ({
  tag,
  ...Object.fromEntries([...attributes.matchAll(/([\w-]+)="([^"]*)"/g)].map(([, key, value]) => [key, value])),
}));
const link = (rel) => tags.find((tag) => tag.tag === "link" && tag.rel === rel);
const meta = (name) => tags.find((tag) => tag.tag === "meta" && tag.name === name)?.content;
const manifestLink = link("manifest");
const manifest = JSON.parse(await readFile(new URL(`../public/${manifestLink?.href}`, import.meta.url), "utf8"));

function appUrl(relative, base) {
  assert(relative.startsWith("./"), `${relative} must be relative to the app`);
  const resolved = new URL(relative, base);
  assert.equal(resolved.origin, base.origin);
  assert(resolved.pathname.startsWith(new URL("./", base).pathname), `${resolved} must stay inside the app`);
  return resolved;
}

test("home-screen metadata keeps kickoff's identity and standalone launch mode", () => {
  assert.equal(meta("apple-mobile-web-app-title"), "kickoff");
  assert.equal(meta("apple-mobile-web-app-capable"), "yes");
  assert.equal(meta("mobile-web-app-capable"), "yes");
  assert.equal(link("apple-touch-icon")?.sizes, "180x180");
  assert.equal(manifest.name, "kickoff");
  assert.equal(manifest.short_name, "kickoff");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.start_url, "./");
  assert.equal(manifest.scope, "./");
  assert.equal(manifest.theme_color, meta("theme-color"));
  assert.equal(manifest.background_color, meta("theme-color"));
});

test("home-screen URLs resolve inside the app on GitHub Pages and nested previews", () => {
  for (const pathname of ["/kickoff/", "/preview/kickoff/"]) {
    const page = new URL(pathname, "https://snowball-projects.github.io");
    const manifestUrl = appUrl(manifestLink.href, page);
    appUrl(link("apple-touch-icon").href, page);
    assert.equal(appUrl(manifest.start_url, manifestUrl).href, page.href);
    assert.equal(appUrl(manifest.scope, manifestUrl).href, page.href);
    for (const icon of manifest.icons) appUrl(icon.src, manifestUrl);
  }
});

test("the Apple and manifest icons are real PNGs with their declared dimensions", async () => {
  assert.deepEqual(manifest.icons.map((icon) => icon.sizes).sort(), ["192x192", "512x512"]);
  const icons = [
    { src: link("apple-touch-icon").href, sizes: "180x180", type: "image/png" },
    ...manifest.icons,
  ];
  for (const icon of icons) {
    assert.equal(icon.type, "image/png");
    const png = await readFile(new URL(`../public/${icon.src}`, import.meta.url));
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.equal(png.toString("ascii", 12, 16), "IHDR");
    assert.equal(`${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`, icon.sizes);
  }
});
