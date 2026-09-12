# September 2026 merge repair

Reviewed all 14 reachable commits through `9ac2279b6e38e2e9f0cc0689958ff1057eefa2e8`.
The September 8 merge combines Windows parent `7e5eb48` with reviewed parent
`9f7e0bd` (v0.1.2). Both parents parse; the merged F1 module did not.

| Area             | What happened                                                                                                              | Resolution                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| F1               | New session loop combined with old race-only construction, dangling `race_event`, missing closing parenthesis              | Restore the reviewed session-aware logic; keep Windows `end_calendar_date` on each session  |
| Parser tests     | Imports lost; qualifying regression test dropped                                                                           | Restore imports and qualifying test, retain the new static-CSV test                         |
| Event semantics  | New group/league/knockout phases displaced the full-weekend qualifying exception                                           | Keep both tournament phase classification and the qualifying exception                      |
| Multi-day events | End dates reached the model/storage but not the static export or browser grouping                                          | Export end dates and show every inclusive date; test day/month grouping                     |
| Runtime          | Incomplete FastAPI server returned although dependencies and results module had been intentionally removed                 | Remove the resurrected server/test; retain Python ingestion and static React presentation   |
| Generated data   | 15 MB/531,463-line cache and stale egg-info returned                                                                       | Remove from tracked source; original cache remains locally and in private history           |
| Calendar         | Dataset endpoints incorrectly inferred season starts/finishes; search could reopen the wrong day after timezone conversion | Use factual event-day markers; preserve display-zone dates through search and day selection |

Also retained: gzip response decoding, clearer PDF dependency errors, static CSV
provider and tournament registrations, inclusive end-date validation and the
Windows reference schedules in private historical storage. Invalid dates now
produce validation errors instead of crashing validation.

The published calendar consumes a separate allowlisted snapshot from openfootball
and F1DB. The old official-source adapters remain local ingestion tools; none of
those adapters is claimed as an approved public feed. Historical reference CSVs
and caches are not included in the public source snapshot.

No pre-repair commits were rewritten or force-pushed. After preservation checks,
the owner approved deletion of the original `adelevski/sportsbro` GitHub
repository, and that remote has been deleted. Original and repaired Git history
and old release artifacts were retained in `retirement-review/sportsbro/`,
including `original-checkout.git`, `repaired-private-history.bundle` and
`releases/`. The separately authorized September 11 local cleanup moved that
collection into the private preservation archive after verification and removed
the old folders. Its private index owns restore paths. Preserve these archives.

The public source snapshot starts from reviewed repaired source in the
owner-approved `snowball-projects/sportsbro` repository. It is not an assertion
that old scraped data is MIT. Use preserved history as a reference; do not restore
the old merge errors, raw caches, removed server or inferred season markers.

Verification includes provider/CLI tests, F1 UTC/Saturday/session cases, unchanged
IDs after fixture rescheduling, export privacy/end dates, browser-data timezone
placement, multi-day coverage, multiple interests, motorsport filters, retry,
year boundaries and leap years. Automated tests use offline fixtures.
