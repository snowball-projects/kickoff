# Changes

## Unreleased

- Prepare a reusable automated PR/check refresh rehearsal. Keep the existing
  weekly publication path until separate permission approval and live acceptance.

## 0.6.0 — 2026-10-18

- Add Agenda with Yesterday, Today and Upcoming, shared interests, device-local
  dates and bounded Show more through later published dates.
- Publish 16 sourced October climbing gender/discipline/round sessions. Eleven
  clocks include four explicitly shared session starts; five disputed clocks stay
  Time TBD. Preserve all 11 other senior stop spans and source attribution.
- Convert offset-aware league timestamps to UTC before writing `Z`, including
  date/year rollover, and reject timestamps without an offset.
- Validate event titles, statuses, dates, spans, tags, participants and known clocks with
  one schema at publication and browser loading. Invalid snapshots show a
  retryable data error. Run publication and climbing data tests even for
  data-only pull requests and Pages updates.
- Bound both downloaded and gzip-expanded responses to 80 MB for league feeds
  and retained local provider adapters. Preserve provider recovery by reporting
  size-limit and corrupt-gzip failures as fetch errors.
- Update pypdf to 6.19.0 and transitive source-map-js to 1.2.2 to resolve the
  dependency advisories found in the October 2026 review. Align both package
  versions at 0.6.0.

- Keep event previews concise and modal close buttons visible while About or
  Interests content scrolls. Preserve keyboard access and day-level sources.

- Streamline Interests and Advanced options; move golf, boxing and privacy
  disclosures into About. Retire boxing category filters without retaining
  hidden saved exclusions. Remove search and month arrows, retaining scrolling,
  Today and keyboard navigation. Clarify automatic browser-local times and
  snapshot freshness.

- Simplify golf interests to PGA Tour and LPGA Tour, with per-tour major scope,
  motorsport sessions and selected boxing categories under Advanced options.
  Preserve legacy major selections, save options on-device, and remove the
  More filters interface while retaining its underlying filter support.

- Publish full NFL, NBA, MLB, NHL, UEFA Champions League, PGA Tour, UFC,
  NASCAR Cup and IndyCar schedules from official league feeds and ESPN, refreshed
  every Monday by a scheduled workflow that commits only real changes and keeps
  the previous data if a feed fails or shrinks. 2026 now has 9,280 events
  and 2027 5,537.
- Add Basketball, Baseball, Hockey and Climbing and weightlifting interest groups.
- Standardize the project name as kickoff. The Python package, the
  frontend package and the KICKOFF_ environment variables follow.


## 0.5.0

- Group interests by sport with collapsible league lists, group selection and
  mixed states. Preserve saved choices, add national soccer flags and label the
  EFL Championship as England's competition.
- Preview event dates, times, locations and notes on hover or day focus; keep
  click/tap/Enter day details, Escape dismissal and continuous month scrolling.
- Confirm a programmatic month jump reaches its destination before settling;
  retain resize alignment during delayed scroll delivery and bound stalled motion.
- Add 41 PGA Tour and 26 LPGA Tour records, bringing the reviewed 2026 snapshot
  to 3,621 events across 24 competitions. Clearly label 63 final-date-only
  markers; preserve full spans for THE PLAYERS, three playoffs and nine majors.
  Retain pinned attribution, separate CC BY-SA/CC0 components and MIT software.

## 0.4.0

- Expand the reviewed 2026 calendar to 3,554 events across 22 competitions:
  four more football leagues, World Climbing, NASCAR Cup, IndyCar, selected
  NFL and combat cards, IWF Worlds, and nine golf majors.
- Preserve date-only spans, stable event IDs, participant identities and source
  terms. Add attributed CC BY-SA and CC0 downloads and explicit coverage limits.
- Fix an idle-timer race when resizing during a smooth Today jump.
- Withhold canceled/postponed football dates and preserve playoff/Chase phases.
  Keep the previous publication usable when a refresh fails.

## 0.3.0

- Add native continuous month scrolling with bounded rendering and a heading
  that follows the visible month.
- Preserve Today, keyboard and reduced-motion navigation, interests, search,
  year view and day details across month changes.
- Load years independently, distinguish missing schedules from empty results,
  and keep the browser cache bounded. Add scrolling regression checks.

## 0.2.0

- Repair F1 parsing, parser tests and full-weekend semantics after Windows merge.
- Preserve and complete multi-day dates, tournament phases and static providers.
- Launch month/year/day calendar, device-local interests, Today navigation and search.
- Publish licensed F1DB/openfootball snapshots with provenance and honest time limits.
- Remove resurrected server/generated files; preserve private historical source.
- Add original calendar/stadium icon and matching favicons.

