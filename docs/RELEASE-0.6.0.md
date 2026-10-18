# 0.6.0 review and release preparation

Prepared on October 18, 2026 from main
`cbdd4239319f833b30d11e622f1565e17170f9c9`. This is a release candidate for
manual review, with no release tag, merge or publication performed.

## Changes

- Normalize aware source timestamps to UTC before writing `Z`. For example,
  `2026-10-17T19:00-06:00` becomes `2026-10-18T01:00:00Z`. Reject naive timestamps
  in both feed timestamp and local-date helpers; the existing per-league refresh
  guard retains the previous events when ingestion fails.
- Share one event/bundle shape validator between publication and browser loading.
  Require titles, real dates, non-reversed spans, string tags and participant
  arrays before consumers access them. Check known clocks and collection shapes;
  retain source, license and immutable-component checks. A malformed browser year
  uses the existing data error and Retry flow, without caching the bad response.
  Legacy unverified local-only clocks continue to display Time TBD; new public
  clocks require explicit offsets and matching UTC instants.
- Run focused publication and climbing data tests unconditionally in PR CI and
  Pages verification, including changes to published/reviewed data alone.
- Bound wire bodies and gzip expansion to 80,000,000 bytes, including concatenated
  gzip members. Keep `kickoff.http`: six original provider adapters still use it.
- Resolve the audited dependency advisories with pypdf 6.19.0 and transitive
  source-map-js 1.2.2. Align Python, frontend and lockfile versions at 0.6.0.
- Reconcile the changelog with already merged agenda, climbing, weekly-feed and
  interface changes since 0.5.0. Correct stale publication/refresh documentation.

## Executed verification

Executed locally on Omarchy using Python 3.14.7 and isolated Node 24.22.0.
These results are from commands run for this candidate, not historical CI.

| Check | Result |
| --- | --- |
| Locked Python installation and `pip check` | Passed |
| `ruff check src tests scripts` | Passed |
| `ruff format --check src tests scripts` | Passed |
| `pytest` | 140 tests and 11 subtests passed |
| `python -m build --no-isolation` | sdist and wheel built for 0.6.0 |
| Installed wheel import/version/UTC smoke check | Passed |
| Reviewed registry loader | 261 reviewed 2026 events validated |
| Clean `npm ci` with Node 24 | Passed |
| `npm test` and individual test files | 62 unit tests across 10 files passed |
| Publication and climbing tests without npm dependencies | 21 focused tests passed |
| `npx playwright install chromium` | Passed using local cache |
| Complete Chromium suite, two workers | 66 passed, including all four new recovery cases |
| `npm run build` | TypeScript and Vite passed; both year snapshots prepared |
| `pip-audit -r requirements-dev.lock --disable-pip --no-deps` | Zero known vulnerabilities |
| `npm audit` | Zero known vulnerabilities |
| `git diff --check` | Passed |

The four new browser cases remove title, date, tags or participants in turn,
check for a visible data error without uncaught page errors, then supply valid
data and recover through Retry. Existing browser checks cover timezone rollover,
climbing shared/withheld clocks, agenda, interests, keyboard/touch navigation,
scrolling, modal focus and layout.

Before dependency fixes the audit reported seven advisories in pypdf 6.17.0 and
one high-severity advisory in source-map-js 1.2.1. The pinned patched versions
clear the current advisory databases. CI retains Python 3.12 and Node 24 and must be checked on this
PR; the local Python run does not substitute for its Python 3.12 result.

## Data and preservation

All reviewed and published JSON files are byte-for-byte unchanged from the base.
The 16 sourced climbing sessions retain 11 known clocks, four explicitly shared
starts and five withheld clocks. No sources were refreshed or dates inferred.
The weekly workflow remains unchanged and continues committing direct to main.

The work uses a separate checkout. Original checkouts, unique local changes and
migration/recovery bundles remain in place. No repository protection/security
settings, credentials, release tags or deployment settings were changed.

## Manual release review

Review the exact PR diff and new regression cases, confirm CI on the PR head,
then decide whether to merge. After any approved merge, verify the Pages workflow
and live data/assets before tagging or describing 0.6.0 as published. Cloud
migration remains deferred.
