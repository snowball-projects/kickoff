// Test-only transport fixtures. Inputs stay convenient annual event collections;
// mocks serve the same manifest and independent sport files as the publisher.
export function publishedFiles(bundles) {
  const files = {};
  const available_seasons = bundles.map(({ season }) => season).sort((a, b) => a - b);
  const index = { schema_version: "1", available_seasons, seasons: {} };
  for (const bundle of bundles) {
    const { events = [], ...metadata } = bundle;
    const season = Number(bundle.season);
    const counts = (values) => {
      const totals = new Map();
      for (const value of values) totals.set(value, (totals.get(value) || 0) + 1);
      return [...totals].map(([value, count]) => ({ value, count })).sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
    };
    const sports = counts(events.map(({ sport }) => sport)).sort((a, b) => a.value.localeCompare(b.value))
      .map((item) => ({ ...item, file: `${season}-${item.value}.json` }));
    const leagues = counts(events.map(({ league }) => league))
      .map((item) => ({ ...item, sport: events.find(({ league }) => league === item.value).sport }));
    index.seasons[String(season)] = { providers: [], sources: [], updated_at: "2026-10-27T12:00:00Z", ...metadata,
      season, available_seasons, all_events: events.length, sports, leagues };
    for (const { value: sport, file } of sports) files[file] = {
      schema_version: "1", season, sport, updated_at: index.seasons[String(season)].updated_at,
      sources: metadata.sources || [], data_license_notice: metadata.data_license_notice,
      data_licenses: metadata.data_licenses || {}, input_evidence: metadata.input_evidence || [],
      events: events.filter((event) => event.sport === sport),
    };
  }
  files["manifest.json"] = index;
  return files;
}
