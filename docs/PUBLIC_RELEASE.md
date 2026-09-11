# Public schedule boundary

The 2026 collection contains **3,621 records across 24 selectable competitions**.
It is a reviewed community snapshot, not an official or live feed. A refresh
records retrieval time; it does not certify that every event was checked then.
Dates can move. An empty day means no matching published records.

## Published coverage

| Competition | Records | Supported scope |
| --- | ---: | --- |
| Premier League / Bundesliga / La Liga / Serie A / Ligue 1 | 374 / 297 / 379 / 374 / 287 | Dated openfootball fixtures in calendar 2026 from the overlapping 2025–26 and 2026–27 files |
| EFL Championship (England) / Eredivisie / Primeira Liga / Brazil Série A | 559 / 305 / 307 / 377 | Same scope; Championship includes five classified playoff games, Brazil uses its single-year file |
| Formula 1 | 115 | Source-provided races, practice, qualifying and sprint sessions; Races only is the initial UI setting |
| World Climbing | 13 | Senior 2026 World Climbing Series stops, inclusive event spans, not timed rounds |
| NASCAR Cup | 36 | Numbered points races; ten Chase races classified as postseason; no exhibitions or practice/qualifying |
| IndyCar | 18 | Championship races; archive coverage, season ended September 6 |
| NFL | 19 | **Selected opener, international and holiday games**, not the full schedule |
| UFC / PFL / RIZIN / ONE | 42 / 16 / 9 / 16 | Reviewed annual rows; PFL global cards only; ONE whole Fight Night/Samurai cards classified as combat sports |
| IWF Worlds | 1 | Senior championship span, October 27–November 8; not a promise of lifting on every day |
| Men's / women's golf majors | 4 / 5 | Competitive tournament spans; all 2026 majors are past |
| PGA Tour / LPGA Tour season additions | 41 / 26 | 37 PGA and 26 LPGA final-date markers; THE PLAYERS and three PGA playoff tournaments have verified full spans. Majors are selected separately; no full daily tour schedule is claimed |
| Selected boxing unifications | 1 | Navarrete–Foster, October 24; the qualifying WBO/IBF vs WBC bout is documented below |

Football source times have no verified timezone declaration and remain Time TBD.
Canceled or postponed fixtures with old dates are withheld until the source
supplies a usable schedule. This excludes seven such rows in the current
calendar-year inputs, including one from the original five-league collection.
F1DB explicitly defines its times as UTC; the UI converts those to the device zone.

All Wikimedia additions are **date-only** and stay on their source calendar dates.
Known inclusive spans are preserved. Golf's **63 final-date-only markers** appear
on the final date listed by the source; they do not imply one-day tournaments.
Opening dates and tee times are unavailable for those entries. Melbourne's NFL game is September 11
at the venue (September 10 in the US); its note explains this difference without
inventing a kickoff. Combat records are whole cards, not prelim/main-card or
ring-walk clocks. An interrupted IndyCar race can span two dates without being
two events. Dates, names and title eligibility can change.

## Reuse and attribution

Software is [MIT](../LICENSE). Data keeps its own terms:

- [openfootball](https://github.com/openfootball/football.json):
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
- [F1DB](https://github.com/f1db/f1db):
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Wikipedia contributors: the identified adapted schedule component is
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), including
  its records within the combined calendar. Preserve attribution, source links,
  license and change notices, and the applicable share-alike terms when reusing it.
- Wikidata contributors: the IWF and THE PLAYERS structured-data records are
  [CC0 1.0](https://www.wikidata.org/wiki/Wikidata:Licensing).

Each published bundle preserves source revisions, input hashes, retrieval times,
changes and license notices. Per-event links identify their pinned sources.
About sportsbro provides attribution and downloads of the separately identified
Wikipedia and Wikidata components. Those downloads use immutable content-hash
filenames listed in the year's `components` field. No article prose, images,
logos, results or private raw payloads are included. Official organizer sources
were used for verification, not claimed as open redistribution grants.

## Decisions and omissions

- [Climbing and motorsport evidence](sources/climbing-motorsport.md): senior stops
  only; no youth/para/continental climbing or invented 2026 senior Worlds.
- [NFL evidence](sources/nfl.md): 19 licensed community selections are published.
  The automated nflverse feed remains blocked by unresolved upstream provenance;
  its data-repository CC BY declaration does not answer that specific gap.
  No Week 18 placeholder dates, full regular season or postseason are supplied.
- [Combat and IWF evidence](sources/combat-iwf.md): UFC October 3 and PFL Chicago
  conflicts are resolved. RIZIN November 8 remains held while official pages
  disagree on identity. PFL regional cards and ONE Friday Fights/Inner Circle
  are outside scope. No full IWF calendar or session grid is claimed.
- Boxing includes cards contesting all four full WBA/WBC/IBF/WBO titles, or a
  unification between reigning champions bringing at least three of those
  titles in one division. The rule applies to women and men equally; it excludes
  interim/secondary titles, exhibitions and influencer cards. The initial set
  contains only the reviewed Navarrete–Foster qualifying card and is not exhaustive.
  [Qualification evidence](sources/combat-iwf.md#boxing-qualification-evidence)
  records the three belts and requires review near fight week. No owner exceptions.
- [Golf evidence](sources/golf.md): nine majors and 67 PGA/LPGA season additions,
  mostly final-date markers; no complete daily tour schedule, business-week
  calendar, team cups or tee times. PGA additions span January–November and LPGA
  markers February–November. The canceled Sentry is excluded.
- [openfootball evidence](sources/openfootball.md): source paths, statuses,
  score shapes and Championship playoff classification.

Existing official-source adapters remain local experiments, outside public
publication. This includes MLB, NBA, NHL, official NASCAR/IndyCar/UFC/ONE/PGA/IFSC
feeds and other unreviewed inputs. No paid service or backend was added.

A normal build makes no provider requests. New sources require a documented
rights, provenance, coverage and date-semantics review, offline fixtures and a
publishing-allowlist change. Never restore old reference CSVs or caches as public
data. See [operation and maintenance](OPERATIONS.md).
