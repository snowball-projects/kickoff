// Mirror the public exporter allowlist; a schedule cannot supply arbitrary image origins.
export function espnLogoUrl(value: unknown): string | null {
  return typeof value === "string" && /^https:\/\/a\.espncdn\.com\/(?:i\/teamlogos\/[A-Za-z0-9_./-]+|guid\/[0-9a-f-]{36}\/logos\/default)\.(png|svg)$/.test(value) ? value : null;
}
