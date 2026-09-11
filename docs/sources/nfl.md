# NFL source decision and reviewed alternative

Checked September 11, 2026. This follow-up implements the owner's authorization for useful zero-service-cost coverage while keeping code and data licenses separate. No contact was sent. The implementation uses an isolated checkout and preserves the scrolling release.

## Ready to publish: 19 selected games from Wikipedia

[`data/reviewed/2026-nfl-community.json`](../../data/reviewed/2026-nfl-community.json) is a reviewed, deliberately partial 2026 NFL calendar:

- One season opener.
- Nine International Series games.
- Five Thanksgiving-week games, including Thanksgiving Eve and Black Friday.
- Four Christmas-week games, including Christmas Eve.

Seventeen dates are later than September 11. There is no full regular-season, preseason, postseason, 2025-season tail, or 2027 coverage. The visible coverage label must say **NFL: selected opener, international and holiday games**. The registry also carries per-event partial-coverage notes and explicit exclusions.

The input is the [2026 NFL season article, revision 1374361050](https://en.wikipedia.org/w/index.php?title=2026_NFL_season&oldid=1374361050), specifically the dated highlights in the Regular season section. Its [exact Action API response](https://en.wikipedia.org/w/api.php?action=parse&oldid=1374361050&prop=wikitext%7Crevid&format=json) is retained locally as `nfl-season-1374361050.json` (177,309 bytes), SHA-256 `dda9868faab4d3e0082d93ad5e950c9fa9e7413c2eaa73c6db07c76515c3c2b1`. The source declaration records the retrieval timestamp from that file's creation. `build_nfl_community.py` reconstructs the reviewed selection offline and checks the revision, critical source date assertions, unique IDs, total count, and future count.

[Wikimedia's terms, section 7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content), supply the reuse path: attribute Wikipedia contributors and the revision, mark transformations, link CC BY-SA 4.0, and preserve applicable share-alike terms on adapted data. This registry and its normalized records are an identified CC BY-SA 4.0 data component. The software remains MIT. Official sources below validate facts; they are not claimed to grant an open feed license. No article narrative, images, logos, broadcast information, or results are included in the output. The full retained article response is research evidence, not an instruction to distribute the article with sportsbro.

### Calendar semantics

Every event is date-only. `start_date == end_date` and no kickoff string, timezone, or synthetic midnight UTC instant is emitted. Event IDs use the season, selection group, and away/home identity, so a date correction does not change an ID. A future change in the selection group should preserve existing IDs.

The Melbourne game is **September 11 at the venue**, as stated in the community article; the article explicitly notes September 10 in U.S. time zones. Its event note preserves that distinction. A date-only record must remain on its supplied calendar date instead of undergoing browser timezone conversion. This is an honest venue-date selection, not the Eastern-time NFL feed proposed in the earlier memo.

No Week 18 record is included: its uncertain date and time cannot place a matchup honestly on a daily calendar. The article also identifies unresolved Saturday/Sunday flex candidates in Weeks 16 and 17; those are outside the selection. No unreviewed matchup is generated from team pairings or a season date range.

### Independent verification

All future selected dates and matchups were reviewed against primary announcements available September 11:

- International selection checked against the [official nine-game announcement](https://www.nfl.com/news/2026-nfl-schedule-release-nine-international-games-dates-times-matchups).
- Venue-local Melbourne date corroborated by the [official international games page](https://www.nfl.com/international/international-games).
- Thanksgiving selection checked against the [official holiday roundup](https://www.nfl.com/news/thanksgiving-2026-nfl-schedule-release).
- Christmas Day selection checked against the [official Christmas roundup](https://www.nfl.com/news/christmas-netflix-2026-nfl-schedule-release).
- Christmas Eve checked against the [venue's Texans–Eagles event](https://www.lincolnfinancialfield.com/events/houston-texans-vs-philadelphia-eagles/).
- Opener checked against the [official season viewing schedule](https://www.nfl.com/news/nfl-make-your-plan-to-watch-the-2026-nfl-season).

Those are verification links, not additional inputs to the distributed data license. No contrary date was found in the selected scope. Venue sponsorship labels differ between some official pages and the community article; the registry avoids carrying venue names and uses city suffixes only where useful. The earlier memo's NFL Operations division-PDF URL returned 404 on this follow-up and was not relied upon.

This is an editorial snapshot, not an automatically current schedule. A maintainer must review a newer article revision and the official event page before changing or expanding records, preserving source hash/revision and checking moves or cancellation. A daily build of a pinned registry is not proof of daily source review.

## Specifically blocked: automated nflverse schedules feed

The original proposed automated feed remains blocked under this task's requirement to resolve its upstream provenance. That source-specific limitation does not block the community selection above.

Primary evidence inspected:

1. [nflverse-data schedules release](https://github.com/nflverse/nflverse-data/releases/tag/schedules), release ID `251386473`, identifies Lee Sharpe's `nfldata/data/games.rds` as the maintained input. Its games.csv asset on September 11 at 17:52:01 UTC was 2,178,382 bytes, with GitHub-supplied digest `sha256:849c4baf48f529215402a693a41d3c1c8f5a217e12bb66df9b48d664dfb07909`.
2. The release repository has an actual [CC BY 4.0 license](https://github.com/nflverse/nflverse-data/blob/6d676213eeac07d381b9e14a564515d9cfe84f46/LICENSE.md) at main revision `6d676213eeac07d381b9e14a564515d9cfe84f46`. It is a genuine data-repository declaration. It is not a field-level source or authorization record for data contributed by other rightsholders.
3. The complete [nfldata tree at revision 401130321e89f98d8b3e26aafc2f532d80ace89e](https://github.com/nflverse/nfldata/tree/401130321e89f98d8b3e26aafc2f532d80ace89e) contains no license file or game-source ingestion script. Its [schedule release workflow](https://github.com/nflverse/nfldata/blob/401130321e89f98d8b3e26aafc2f532d80ace89e/.github/workflows/release_games.yml) reads an already prepared RDS, compares it with the release, and upserts by `game_id`. This verifies propagation, not original collection.
4. [nfldata's dataset documentation](https://github.com/nflverse/nfldata/blob/401130321e89f98d8b3e26aafc2f532d80ace89e/DATASETS.md#games) identifies sources for several other datasets but does not identify upstream ownership/permission for game date, time, team, or stadium fields. Recent CSV commits are labeled automated data updates. Inspected maintainer comments on schedule-correction issues establish active maintenance, not reuse authority.
5. [Issue 35, Commercial use clarification for nflverse schedule data](https://github.com/nflverse/nfldata/issues/35), opened September 2, explicitly asks whether the release license covers underlying schedule data and normalized redistribution. It remained open with **zero comments** at this check. [Issue 33](https://github.com/nflverse/nfldata/issues/33), opened July 12, asks for an explicit nfldata license; its sole comment is another downstream user's request, with no maintainer grant.

The absence of a response is not proof that reuse is prohibited. It means this requested provenance check cannot establish the rights chain from the public evidence examined. Do not silently represent the gap as resolved, and do not install a publishing adapter for this feed in this release. Revisit if an applicable primary grant/source declaration appears, without contacting anyone under the current instruction.

If the feed is later approved, its separate technical requirements still apply: use `America/New_York` with DST, stable `game_id`, calendar-year filtering across overlapping seasons, and explicit Week 18 confirmation before accepting either date or time. The current date-only community registry deliberately does not impersonate those unimplemented behaviors.
