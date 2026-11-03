# ESPN league additions, checked November 2, 2026

This review covers the supported 2025–2027 source years. Counts below are usable
calendar-year appointments after existing cancellation/postponement filtering,
deduplication and date-zone handling; zero means ESPN has not published usable
appointments for that year. The rolling calendar can display a narrower date range.
No optional competitions, synthetic games or guessed opponents are included.

| Competition | 2025 | 2026 | 2027 | Primary scoreboard |
| --- | ---: | ---: | ---: | --- |
| FA Cup | 123 | 103 | 0 | [ESPN `soccer/eng.fa`](https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard?dates=2026&limit=1000) |
| League Cup | 93 | 93 | 0 | [ESPN `soccer/eng.league_cup`](https://site.api.espn.com/apis/site/v2/sports/soccer/eng.league_cup/scoreboard?dates=2026&limit=1000) |
| Liga MX | 340 | 320 | 0 | [ESPN `soccer/mex.1`](https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard?dates=2026&limit=1000) |
| Copa Libertadores | 155 | 155 | 0 | [ESPN `soccer/conmebol.libertadores`](https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.libertadores/scoreboard?dates=2026&limit=1000) |
| Copa Sudamericana | 156 | 157 | 0 | [ESPN `soccer/conmebol.sudamericana`](https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.sudamericana/scoreboard?dates=2026&limit=1000) |
| NWSL | 189 | 244 | 0 | [ESPN `soccer/usa.nwsl`](https://site.api.espn.com/apis/site/v2/sports/soccer/usa.nwsl/scoreboard?dates=2026&limit=1000) |
| Women's Super League | 138 | 157 | 91 | [ESPN `soccer/eng.w.1`](https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/scoreboard?dates=2026&limit=1000) |
| UEFA Women's Champions League | 67 | 75 | 0 | [ESPN `soccer/uefa.wchampions`](https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.wchampions/scoreboard?dates=2026&limit=1000) |
| NBA G League | 795 | 789 | 492 | [ESPN `basketball/nba-development`](https://site.api.espn.com/apis/site/v2/sports/basketball/nba-development/scoreboard?dates=2026&limit=1000) |
| NBL | 170 | 201 | 56 | [ESPN `basketball/nbl`](https://site.api.espn.com/apis/site/v2/sports/basketball/nbl/scoreboard?dates=2026&limit=1000) |
| UFL | 43 | 43 | 0 | [ESPN `football/ufl`](https://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard?dates=2026&limit=1000) |
| CFL (withheld) | 0 | 0 | 0 | [ESPN `football/cfl`](https://site.api.espn.com/apis/site/v2/sports/football/cfl/scoreboard?dates=2026&limit=1000) |

## Collection and omissions

All 36 annual responses were compared with all twelve monthly responses for
the same league/year: identical identities, no saturated months (maximum 189).
The collector subdivides saturated year/month windows and refuses a saturated
daily response rather than truncating. G League and NBL postseason, preseason
and cup dates were also spot-checked against daily scoreboards.

UFL is an important exception to date-index completeness. Its 2025 annual,
monthly, daily and Core indexes omit four **completed** games (401743448,
401743456, 401743478, 401743494). Weekly scoreboards retain them. The collector
unions every week in ESPN’s published calendar, including postseason and the
overlapping previous source season; it has no fixed week count. For example,
[2025 regular-season week 1](https://site.api.espn.com/apis/site/v2/sports/football/ufl/scoreboard?dates=2025&limit=1000&seasontype=2&week=1).
Annual team facts survive sparse weekly copies, with their original receipts.
An independent audit found no annual/weekly loss of supplied clocks, venue,
city, state, country or stage facts across 82 overlapping games.

CFL annual and all monthly scoreboards are empty for 2025, 2026 and 2027.
[Core season events](https://sports.core.api.espn.com/v2/sports/football/leagues/cfl/seasons/2026/types/2/events?limit=1000)
were empty for types 1/2/3 in each year. All nine teams’ schedule endpoints
were empty for regular/postseason in each year, for example
[team 1, 2026 regular season](https://site.api.espn.com/apis/site/v2/sports/football/cfl/teams/1/schedule?season=2026&seasontype=2).
The default Core catalog’s only event, 401504210, is dated November 20, 2022;
it cannot supply this calendar. CFL is deliberately not registered or shown.

Four G League 2026 postponed rows and one canceled Sudamericana 2025 row
are withheld by the existing status rule. The 31 dated G League 2026 bracket
appointments without known opponents retain their source clocks and venues;
their label is the source league name, and TBD entries are removed from team
entities. No bracket round or participant is invented.

## Supplied facts, identity and rights

ESPN’s explicit offsets supply UTC instants; `timeValid: false` stays date-only.
Date grouping uses London for English competitions, Mexico City for Liga MX,
São Paulo for CONMEBOL, New York for NWSL/G League/UFL, Paris for UEFA women
and Sydney for NBL. Timed appointments still convert to each visitor’s zone.
Source season, cup/league/group stage, leg/round/week notes, final scores, team
records and short names are retained where provided. WSL’s season-title slug
and Liga MX Apertura/Clausura are regular play; their knockout/final stages
remain separate. NBL preseason, G League cup dates and UFL postseason remain
included.

Explicit venue city, state and country facts are retained. Country flags follow
the source venue or existing competition-country display rule. Clubs never
become national teams from a name, logo, venue or inferred country. NBL supplies
no venues for its 201 rows in 2026; G League venues do not supply countries.
2026 venue facts are absent from two Libertadores, one Sudamericana and one
UEFA women’s Champions League rows. Those facts stay missing.

Team-logo URLs come from ESPN’s supplied `team.logo`, or optional team metadata
when both team ID and full display name match. These URLs are constrained
to HTTPS `a.espncdn.com` team-logo paths or its UUID logo paths. They load lazily
without a referrer, with normal HTTP caching; no assets or raw payloads are
copied into the repository. Source URL and checked date accompany every image.
The reviewed FA Cup scoreboards lack images for 15 team appearances in 2025
and 16 in 2026. All 27 affected club metadata endpoints were also checked and
supplied no images; these stay text. UFL 2025’s scoreboards lack 32 images,
but three matching historical-team metadata endpoints supply them, so all
86 retained UFL team appearances now have sourced logos. The G League placeholder teams have no images and
are not treated as actual participants.

ESPN and the image owners grant no new data/image license. Names and small
images identify teams in factual schedule reporting; no affiliation is implied.
Odds, articles and raw responses are excluded. See [third-party notices](../../THIRD-PARTY-NOTICES.md).
The [review receipts](receipts/espn-leagues-review.json) retain annual source URLs, raw
response hashes, exact counts and omissions. Public refreshes preserve per-event sources/check dates. The review receipt
also hashes the sanitized normalized event arrays used for verification. Raw
evidence remains private.
