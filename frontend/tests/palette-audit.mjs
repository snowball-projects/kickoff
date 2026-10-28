import { readFile } from "node:fs/promises";

// WCAG relative luminance, and Machado et al. (2009), severity 1.0 matrices.
// Simulate linear sRGB, clip to gamut, then compare D65 CIELAB (Delta E 1976).
// This is a regression diagnostic, not a clinical or WCAG colour-distance threshold.
export const simulations = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protan: [[.152286, 1.052583, -.204868], [.114503, .786281, .099216], [-.003882, -.048116, 1.051998]],
  deutan: [[.367322, .860646, -.227968], [.280085, .672501, .047413], [-.01182, .04294, .968881]],
  tritan: [[1.255528, -.076749, -.178779], [-.078411, .930809, .147602], [.004733, .691367, .3039]],
};
const rgb = (hex) => [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255);
const linear = (value) => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
const luminance = (hex) => dot(rgb(hex).map(linear), [.2126, .7152, .0722]);
export function simulatedContrast(a, b, matrix) {
  const [low, high] = [a, b].map((hex) => dot(simulate(hex, matrix), [.2126, .7152, .0722])).sort((a, b) => a - b);
  return (high + .05) / (low + .05);
}
export function contrast(a, b) {
  const [low, high] = [luminance(a), luminance(b)].sort((a, b) => a - b);
  return (high + .05) / (low + .05);
}
export function simulate(hex, matrix) {
  const channels = rgb(hex).map(linear);
  return matrix.map((row) => Math.max(0, Math.min(1, dot(row, channels))));
}
export function lab(channels) {
  const f = (value) => value > (6 / 29) ** 3 ? value ** (1 / 3) : value / (3 * (6 / 29) ** 2) + 4 / 29;
  const x = f(dot(channels, [.4124564, .3575761, .1804375]) / .95047);
  const y = f(dot(channels, [.2126729, .7151522, .0721750]));
  const z = f(dot(channels, [.0193339, .1191920, .9503041]) / 1.08883);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}
export async function readPalette() {
  const css = await readFile(new URL("../src/category-palette.css", import.meta.url), "utf8");
  return [...css.matchAll(/\.category-([\w-]+) \{([^}]+)\}/g)].map(([, key, body]) => ({
    key, ...Object.fromEntries([...body.matchAll(/--category-([\w-]+): (#[\da-f]{6});/g)].map(([, key, value]) => [key, value])),
  }));
}
// Distances compare chip fills, not standalone label/accent shades.
export function pairwise(palette, mode, matrix) {
  const pairs = [];
  for (const [index, a] of palette.entries()) for (const b of palette.slice(index + 1)) {
    const left = lab(simulate(a[`${mode}-bg`], matrix));
    const right = lab(simulate(b[`${mode}-bg`], matrix));
    pairs.push({ a: a.key, b: b.key, distance: Math.hypot(...left.map((value, i) => value - right[i])) });
  }
  return pairs.sort((a, b) => a.distance - b.distance);
}
export async function paletteReport() {
  const palette = (await readPalette()).filter((entry) => entry.base);
  return {
    contrast: palette.map((entry) => ({ key: entry.key,
      light: contrast(entry["light-bg"], entry["light-ink"]),
      dark: contrast(entry["dark-bg"], entry["dark-ink"]),
      lightAccent: contrast(entry["light-accent"], "#eaf2e5"),
      darkAccent: contrast(entry["dark-accent"], "#2c3d4b"),
    })),
    minimumPairwise: Object.fromEntries(["light", "dark"].map((mode) => [mode,
      Object.fromEntries(Object.entries(simulations).map(([name, matrix]) => [name, pairwise(palette, mode, matrix)[0]])),
    ])),
  };
}
