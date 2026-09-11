# Operation

The website is static React/Vite on GitHub Pages. No application server, API key,
paid feed or database is configured. GitHub hosting limits apply. Preferences use
one local-storage key, `sportsbro.interests.v1`; schedule queries run entirely in
the browser against same-origin JSON files, one per published year.

`frontend/public/data` is generated from reviewed `data/published` snapshots.
Never copy a private normalized directory or cache into public assets. Snapshots
are portable JSON; other software can read the same contract without operating
the interface. Provider adapters, normalization, validation, export and UI remain
separate parts of one repository.

## Calendar behavior

The month view uses native vertical scrolling with a sliding window of nine
months in the DOM. It preserves the visible month's offset when replacing
months near the window edges, and the header follows the visible month. Date
navigation is bounded to January 1900–December 2100. Rendering a calendar year
does not claim that its schedule is published.

Each requested year's schedule loads independently, so an unavailable year does
not hide neighboring years that have data. Each affected month shows its loading
or failure status; failures offer a retry action. The bundle cache retains at most
three years, evicting the least recently used; the month view derives its
current window and retains the selected day's month while its panel is open.
The year overview and search use the year in the heading.
Missing schedules and empty filtered results remain distinct.

Today stays at the bottom left. Nearby navigation scrolls smoothly through
rendered months; a distant return replaces the window around the current month
and glides into position. Reduced-motion preferences make these moves immediate.
Touch, trackpad and wheel input use the browser's scrolling. With a day focused,
arrow keys move by day or week, Page Up/Down changes month, and Shift + Page
Up/Down changes year; month jumps clamp to a valid day. Current-day highlighting,
event pills, interests, search, year overview and the day detail panel remain
available across navigation.

## Deploy or revive

1. Install locked Python/frontend dependencies and run the commands in README.
2. Build `frontend/dist/`. The pinned-source snapshot works without refreshing
   upstream data, including during dormancy.
3. GitHub Pages uses Actions. The Pages workflow runs Python, frontend unit and
   Chromium browser checks before building, uploading only `frontend/dist/` and
   deploying. Browser checks cover navigation and scroll behavior using offline
   schedule fixtures. Locally, install Chromium with
   `npx playwright install chromium` and run `npm run test:browser` from
   `frontend`; `PLAYWRIGHT_CHROME=1` can use installed Google Chrome instead.
   Check the workflow conclusion and live data, JavaScript, CSS and icons before
   calling a release published. Release tags identify verified commits.
4. Revert a bad code/data commit to roll back through the same workflow. Another
   static host can serve the build under any path; no vendor-specific backend.

The public snapshot is refreshed deliberately, not advertised as live. Run the
refresh command, inspect changes in fixtures/counts/coverage and provenance, then
commit. Unknown/cancelled dates should be explicit; do not silently fabricate
missing events or infer season milestones from partial data. Before each new
calendar year, add and verify its snapshot. Years without a published snapshot
show an honest unavailable state and allow returning to the current month.

## Reviewed registry maintenance

`data/reviewed/2026-*.json` holds deliberately reviewed event selections. The
public refresh fetches only the openfootball/F1DB sources; it reads these
registries locally. Updating the snapshot timestamp does not refresh a pinned
Wikimedia review. Check upcoming cards/stops periodically and near the event,
especially boxing title eligibility. A dormant calendar should be treated as
an archive until its sources are reviewed again.

For a registry change, inspect its pinned source and the candidate revision,
verify scope, dates and rights against `docs/sources/`, keep stable IDs through
moves or renaming, and record the input URL, raw-byte SHA-256, retrieval time,
revision, contributor attribution, license and changes together. Retain raw
responses in local ignored storage. Do not turn date-only or month-precision
values into timestamps. Add a new year explicitly; do not extrapolate dates.

Refresh with `scripts/refresh-public.py --year 2026`. It validates registries and
all normalized events before publishing. Wikimedia components use immutable
content-hash filenames and are written before the year bundle is atomically
replaced. A failed fetch, parse or final write leaves the previous year bundle
and its referenced downloads intact. Unreferenced component files from an
interrupted attempt can remain; the build copies only referenced components.
Keep the previous snapshot in Git for rollback.

Run Python checks, frontend data tests/build and browser tests. Review counts,
exclusions, timezone behavior and source/component license notices in the diff.
The build validates each public source and requires attributed licensed
components to match the combined calendar exactly. It never copies raw caches.

## Next

- Broaden partial NFL/combat coverage only after reviewing suitable sources;
  the automated nflverse upstream provenance remains unresolved.
- Verify football kickoff timezone conventions before displaying times.
- Consider a scheduled refresh only after source stability and review needs are
  understood. Preserve the previous snapshot on failure and show retrieval time.
- Team-level interests and calendar subscriptions are possible later additions;
  the first release deliberately selects leagues.

## Historical preservation

The owner approved deletion of the original `adelevski/sportsbro` GitHub
repository after preservation checks, and that remote has been deleted.
Original and repaired Git history and old release artifacts remain locally in
the collection's `retirement-review/sportsbro/`, including
`original-checkout.git`, `repaired-private-history.bundle` and `releases/`.
Private historical material includes reference CSVs and raw caches that are not
cleared for public redistribution. Preserve these local backups; remote
retirement did not authorize deleting them.

The canonical public repository is `snowball-projects/sportsbro`, which starts
from reviewed repaired source. The local history is a reference for recovery,
not a public deployment input; do not restore old merge errors, caches, the
removed server or inferred season markers.
