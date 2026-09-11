# Golf source review

Reviewed September 11, 2026. Golf contains **76 records**: the four men's and five
women's majors, 41 other PGA Tour tournaments and 26 other LPGA Tour tournaments.
This is a reviewed community selection, not a full daily tour calendar or live
feed. Major interests remain separate, with no duplicate tour records for majors.

**63 records are final-date markers, not one-day tournaments:** 37 PGA and all
26 LPGA additions. Their season tables list final dates without opening dates.
The calendar labels them as final dates and notes this limit on every record.
PGA coverage runs January 18–November 22; LPGA markers run February 1–November 22.
No missing opening date was obtained by assuming four days of play.

The other 13 records preserve inclusive competitive spans: nine existing majors,
THE PLAYERS March 12–15, FedEx St. Jude August 13–16, BMW August 20–23 and Tour
Championship August 27–30. The three FedEx Cup events are postseason; THE PLAYERS
is not classified as a major. All records are date-only, stay on their source
calendar dates and supply no tee times or invented timezone.

## Reuse and provenance

The [reviewed registry](../../data/reviewed/2026-golf.json) pins source revisions,
raw API-byte SHA-256 hashes, retrieval times, contributor attribution, license
links and transformation notices. The existing nine major rows and receipts
remain unchanged. New sources are:

| Source | Revision | Selected records | License |
| --- | --- | ---: | --- |
| [2026 PGA Tour](https://en.wikipedia.org/w/index.php?title=2026_PGA_Tour&oldid=1372211962) | 1372211962 | 37 final dates | CC BY-SA 4.0 |
| [2026 FedEx Cup Playoffs](https://en.wikipedia.org/w/index.php?title=2026_FedEx_Cup_Playoffs&oldid=1372634692) | 1372634692 | 3 spans | CC BY-SA 4.0 |
| [2026 Players Championship, Q138632122](https://www.wikidata.org/w/index.php?title=Q138632122&oldid=2474720054) | 2474720054 | 1 span | CC0 1.0 |
| [2026 LPGA Tour](https://en.wikipedia.org/w/index.php?title=2026_LPGA_Tour&oldid=1372529225) | 1372529225 | 26 final dates | CC BY-SA 4.0 |

Wikipedia adaptations retain [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
with attribution, source links and modification notices, as required by the
[Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content).
THE PLAYERS uses structured day-precision P580/P582 values under
[Wikidata's CC0 policy](https://www.wikidata.org/wiki/Wikidata:Licensing).
Wikidata's midnight serialization does not establish a clock time. No images,
prose, results, player fields or prize money are included. Data licenses remain
separate from the MIT software; public component downloads preserve them.

## Accuracy checks and limits

All 26 LPGA markers match the pinned season rows; none is canceled, postponed or
struck through there. The eight September–November dates also match the
[current LPGA schedule](https://www.lpga.com/tournaments). The
[ShopRite page](https://www.lpga.com/tournaments/shoprite-lpga-powered-by-wakefern)
confirms a three-day tournament ending May 31, illustrating why four-day spans
cannot be assumed. The opening Hilton event concluded February 1 after a
[weather reduction to 54 holes](https://prod.crown.lpga.com/news/2026/nelly-korda-collects-16th-career-title-at-hilton-grand-vacations-tournament-of-champions);
its marker does not promise a fourth round.

The [official THE PLAYERS page](https://www.pgatour.com/tournaments/2026/the-players-championship/R2026011/overview)
corroborates March 12–15. The playoffs article gives each included span explicitly.
The [PGA schedule](https://www.pgatour.com/schedule/2026) and selected organizer
pages were used for accuracy checks, not as redistribution licenses.

Travelers retains **June 29**, the actual Monday conclusion after a
[weather-delayed playoff](https://www.pgatour.com/article/news/latest/2026/06/28/weather-delay-travelers-rain-forecast-delay-suspended-sunday-final-round-tpc-river-highlands),
instead of the general schedule's planned June 28 finish. **Austin Championship**
uses the current name after Good Good's August withdrawal, corroborated by the
[organizer's announcement](https://www.austinchampionship.com/). Its November
9–15 business week is not used as a competitive span.

The earlier major review found incorrect or absent Wikidata dates for PGA,
U.S. Open, The Open and Evian; those records continue using verified Wikipedia
infoboxes. The PGA season Wikidata item Q136090359 only has year precision, so it
cannot supply the season schedule. Only the individually verified Players item
adds CC0 golf data. Retrieval timestamps do not certify every event independently;
future dates and names can change.

## Existing majors

| Tournament | Inclusive 2026 dates | Wikipedia revision |
| --- | --- | --- |
| Masters | April 9–12 | 1365105813 |
| PGA Championship | May 14–17 | 1370641499 |
| U.S. Open | June 18–21 | 1373024366 |
| The Open | July 16–19 | 1373024175 |
| Chevron | April 23–26 | 1362471818 |
| U.S. Women's Open | June 4–7 | 1362471868 |
| Women's PGA | June 25–28 | 1371673907 |
| Evian | July 9–12 | 1370642460 |
| Women's Open | July 30–August 2 | 1367542936 |

All nine are past. Their actual tournament infoboxes establish the spans.
[LPGA's Evian page](https://www.lpga.com/tournaments/the-evian-championship)
corroborates July 9–12; [The Open spectator timeline](https://www.theopen.com/tickets-and-hospitality/spectator-guide)
separates practice days from July 16–19 championship play.

## Omissions and operation

The canceled Sentry and the season tables' unofficial events are excluded. No
Presidents/Solheim cups, Hero World Challenge, Grant Thornton Invitational,
qualifying, practice, full DP World/LIV/Champions coverage or 2027 dates are
promised. Zurich Classic and Dow Championship remain included official tour
tournaments with team formats.

The official PGA business-week ICS remains outside the public allowlist.
[golfastR](https://github.com/array-carpenter/golfastr) obtains tournament data
from ESPN; its MIT code license does not establish ESPN schedule reuse rights,
so its data was not ingested. No paid source or service was added.

Publication uses the checked-in registry without provider requests. Raw review
inputs stay local and outside the public bundle. Refreshes require deliberate
source review, ordinary validation and a published snapshot diff. Keep the last
reviewed snapshot when a future fetch or rights check fails.
