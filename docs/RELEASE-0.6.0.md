# 0.6.0 release notes and verification

Release notes dated October 18, 2026, based on main
`cbdd4239319f833b30d11e622f1565e17170f9c9`. Publication is verified separately
through the release tag and Pages deployment after an approved merge.

## Changes

- Normalize aware source timestamps to UTC before writing `Z`. For example,
  `2026-10-17T19:00-06:00` becomes `2026-10-18T01:00:00Z`. Reject naive timestamps
  in both feed timestamp and local-date helpers; the existing per-league refresh
  guard retains the previous events when ingestion fails.
- Share one event/bundle shape validator between publication and browser loading.
  Require titles, statuses, source/season/phase labels, real dates, non-reversed
  spans, string tags and participant arrays before consumers access them. Check known clocks and collection shapes;
  retain source, license and immutable-component checks. A malformed browser year
  uses the existing data error and Retry flow, without caching the bad response.
  Legacy unverified local-only clocks continue to display Time TBD; new public
  clocks require explicit offsets and matching UTC instants.
- Run focused publication and climbing data tests unconditionally in PR CI and
  Pages verification, including changes to published/reviewed data alone.
- Bound wire bodies and gzip expansion to 80,000,000 bytes, including concatenated
  gzip members. Keep `kickoff.http`: six original provider adapters still use it.
  Size-limit and corrupt-gzip failures become `FetchError`, preserving per-club
  provider warnings and recovery instead of aborting an entire provider run.
- Resolve the audited dependency advisories with pypdf 6.19.0 and transitive
  source-map-js 1.2.2. Align Python, frontend and lockfile versions at 0.6.0.
- Reconcile the changelog with already merged agenda, climbing, weekly-feed and
  interface changes since 0.5.0. Correct stale publication/refresh documentation.

## Executed verification

Executed locally on Omarchy using Python 3.14.7 and isolated Node 24.22.0.
These results are from commands run for this change, not historical CI.

| Check | Result |
| --- | --- |
| Locked Python installation and `pip check` | Passed |
| `ruff check src tests scripts` | Passed |
| `ruff format --check src tests scripts` | Passed |
| `pytest` | 146 tests and 11 subtests passed |
| `python -m build --no-isolation` | sdist and wheel built for 0.6.0 |
| Installed wheel import/version/UTC smoke check | Passed |
| Reviewed registry loader | 261 reviewed 2026 events validated |
| Clean `npm ci` with Node 24 | Passed |
| `npm test` and individual test files | 63 unit tests across 10 files passed |
| Publication and climbing tests without npm dependencies | 22 focused tests passed |
| `npx playwright install chromium` | Passed using local cache |
| Complete Chromium suite, two workers | 67 passed, including all five new recovery cases |
| `npm run build` | TypeScript and Vite passed; both year snapshots prepared |
| `pip-audit -r requirements-dev.lock --disable-pip --no-deps` | Zero known vulnerabilities |
| `npm audit` | Zero known vulnerabilities |
| `git diff --check` | Passed |

The five new browser cases remove title, status, date, tags or participants in turn,
check for a visible data error without uncaught page errors, then supply valid
data and recover through Retry. Existing browser checks cover timezone rollover,
climbing shared/withheld clocks, agenda, interests, keyboard/touch navigation,
scrolling, modal focus and layout.

Before dependency fixes the audit reported seven advisories in pypdf 6.17.0 and
one high-severity advisory in source-map-js 1.2.1. The pinned patched versions
clear the current advisory databases. CI also covers Python 3.12 and Node 24;
its exact-head results are recorded on the pull request. Local Python 3.14
results do not substitute for verification of the Python 3.12 floor.

## Today-scroll investigation

The existing “Today interrupts an in-progress smooth keyboard year navigation”
test needed one retry in the first PR CI run. The failure occurred before the
Today click, while waiting to observe a transient animation position at
`frontend/tests/browser/calendar.spec.ts:164`.

Repeating the unchanged test 20 times with two Chromium workers and no retries
on base commit `cbdd423` reproduced the identical failure: 19 passed, one timed
out at line 164. The same 20-repeat run on the PR also produced 19 passes and
one identical timeout. The scrolling component, navigation state helpers and test
are byte-for-byte identical between base and PR. This failure therefore predates
0.6.0's ingestion and validation changes. The final local full suite passed all
67 cases without retries. No navigation redesign is included.

## Data and preservation

All reviewed and published JSON files are byte-for-byte unchanged from the base.
The 16 sourced climbing sessions retain 11 known clocks, four explicitly shared
starts and five withheld clocks. No sources were refreshed or dates inferred.
The weekly workflow remains unchanged and continues committing direct to main.

The work uses a separate checkout. Original checkouts, unique local changes and
migration/recovery bundles remain in place. No repository protection/security
settings, credentials or deployment settings were changed.

## Publication verification

Release tags identify commits verified through the Pages workflow and live
calendar data/assets after an approved merge. The exact pull-request diff, CI
results and regression cases provide the review record. Cloud migration is
outside the 0.6.0 scope.
