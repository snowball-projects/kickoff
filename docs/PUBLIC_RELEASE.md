# Public schedule boundary

The public launch bundle contains only **openfootball** (CC0 1.0) and **F1DB**
(CC BY 4.0) data. Explicit attribution, source revisions, original file hashes,
retrieval time and changes are preserved. Software is MIT; schedule data retains
its own license. The downloadable JSON carries attribution too.

## Current coverage

Calendar year 2026: Premier League, Bundesliga, La Liga, Serie A, Ligue 1 and
F1 races plus source-provided practice, qualifying and sprint sessions. The UI
starts in Races only mode. Both football seasons overlapping the calendar year
are considered. Records without dates cannot appear in the calendar.

These are community-maintained schedules, not official or live feeds. A successful
refresh says when sportsbro retrieved source data, not when every fixture was
last verified. Check the linked source before making plans. An empty day is an
absence of matching published records, not proof there are no events.

F1DB defines session timestamps as UTC; retain unusual weekdays and supplied
dates. Football JSON time strings do not declare a timezone, so the public
adapter deliberately omits them and the UI shows Time TBD. Do not infer venue
timezones merely to populate a clock. Date-only records remain on source dates.

## Sources and rights review (September 10, 2026)

- [openfootball](https://github.com/openfootball/football.json),
  [CC0 declaration](https://github.com/openfootball/football.json/blob/master/LICENSE.md).
- [F1DB](https://github.com/f1db/f1db),
  [CC BY 4.0 license](https://github.com/f1db/f1db/blob/main/LICENSE),
  [UTC field definitions](https://github.com/f1db/f1db/blob/main/src/schema/current/single/f1db.schema.json).

No public redistribution permission was established for the existing MLB, NBA,
NHL, Formula1.com, NASCAR, IndyCar, UEFA, PGA or IFSC ingestion sources. Their
adapters can remain as private/local tools; access alone does not authorize
republishing downloaded schedules. NFL remains disabled until validated. FIFA's
terms contain a limited noncommercial website-display permission, but it is not
an unrestricted data license and FIFA is outside this launch bundle.

Before adding another public source: verify access, schema/coverage, timezone
meaning, update behavior and reuse terms; document attribution; add offline
parser fixtures; then extend the publishing allowlist. Never relabel old reference
CSV files as verified current schedules. Do not bulk-publish raw payloads.
