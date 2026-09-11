# Operation

The website is static React/Vite on GitHub Pages. No application server, API key,
paid feed or database is configured. GitHub hosting limits apply. Preferences use
one local-storage key, `sportsbro.interests.v1`; schedule queries run entirely in
the browser against a same-origin JSON file.

`frontend/public/data` is generated from reviewed `data/published` snapshots.
Never copy a private normalized directory or cache into public assets. Snapshots
are portable JSON; other software can read the same contract without operating
the interface. Provider adapters, normalization, validation, export and UI remain
separate parts of one repository.

## Deploy or revive

1. Install locked Python/frontend dependencies and run the commands in README.
2. Build `frontend/dist/`. The pinned-source snapshot works without refreshing
   upstream data, including during dormancy.
3. GitHub Pages uses Actions. The Pages workflow tests both data paths, builds,
   uploads only `frontend/dist/` and deploys. Check its conclusion and live data,
   JavaScript, CSS and icons. Release tags identify verified commits.
4. Revert a bad code/data commit to roll back through the same workflow. Another
   static host can serve the build under any path; no vendor-specific backend.

The public snapshot is refreshed deliberately, not advertised as live. Run the
refresh command, inspect changes in fixtures/counts/coverage and provenance, then
commit. Unknown/cancelled dates should be explicit; do not silently fabricate
missing events or infer season milestones from partial data. Before each new
calendar year, add and verify its snapshot. Years without a published snapshot
show an honest unavailable state and allow returning to the current month.

## Next

- Add the owner's priority sports when a reusable source and its date/time
  semantics are verified. Existing local adapters are starting points, not
  evidence of public launch readiness.
- Verify football kickoff timezone conventions before displaying times.
- Consider a scheduled refresh only after source stability and review needs are
  understood. Preserve the previous snapshot on failure and show retrieval time.
- Team-level interests and calendar subscriptions are possible later additions;
  the first release deliberately selects leagues.

## Historical preservation

The private original repository retains its complete history, including old
reference CSVs and raw caches that are not cleared for public redistribution.
The repaired public source starts from a reviewed snapshot. Do not delete that
private history without a separate owner decision.
