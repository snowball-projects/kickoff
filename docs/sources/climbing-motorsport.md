# sportsbro: reviewed climbing and motorsport extraction

Reviewed September 11, 2026. The owner-authorized first scope is **67 date-only
events**: 13 senior World Climbing Series stops, 36 NASCAR Cup points races and
18 IndyCar championship races. All are an adapted **CC BY-SA 4.0** data component,
separate from sportsbro's MIT software. No paid service or backend is involved.

## Deliverable and exact provenance

[`data/reviewed/2026-climbing-motorsport.json`](../../data/reviewed/2026-climbing-motorsport.json) follows schema version 1. Each event references one
source; every source has an article/revision URL, explicit Wikipedia-contributor
credit, license/link, retrieval time, exact response SHA-256, input URL and
modification statement. The local audit manifest `climbing-motorsport-inputs.json` preserves revision
timestamps separately; it is retained in the collection review directory and
is not a shipped repository input. SHA-256 refers to the **complete response bytes** from
MediaWiki `action=parse&oldid=...&prop=text&format=json`, not to rendered text or
the output asset.

| Source | Exact revision | Revision UTC | Rows |
| --- | --- | --- | --- |
| [Wikipedia contributors, 2026 World Climbing Series](https://en.wikipedia.org/w/index.php?title=2026_World_Climbing_Series&oldid=1373523818) | 1373523818 | 2026-09-06 13:11:05 | 13 |
| [Wikipedia contributors, 2026 NASCAR Cup Series](https://en.wikipedia.org/w/index.php?title=2026_NASCAR_Cup_Series&oldid=1373965067) | 1373965067 | 2026-09-09 01:02:14 | 36 |
| [Wikipedia contributors, 2026 IndyCar Series](https://en.wikipedia.org/w/index.php?title=2026_IndyCar_Series&oldid=1374195049) | 1374195049 | 2026-09-10 12:28:38 | 18 |

Inputs were retrieved at 18:01:47Z, 18:02:08Z and 18:02:03Z respectively on
September 11. The exact JSON responses are retained in this review directory's
`raw/` folder. Do not copy those full article responses into the public data
asset; they are local review evidence. No media files were downloaded or reused.

## Source and license review

The [Wikimedia terms, section 7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content)
allow licensed text reuse with attribution, require preservation of applicable
additional attribution notices, and require adapted text to retain CC BY-SA
terms and identify modifications. The three downloaded articles and selected
table sections were inspected; no table-specific imported-content credit,
copyright exclusion or incompatible license notice was identified. This is a
review of the visible source material, not a forensic audit of every editor or
historical revision. The content is community-maintained, not an official feed.

The [CC BY-SA 4.0 terms](https://creativecommons.org/licenses/by-sa/4.0/) must
remain with the adapted component and its redistributions. Show the source
credit/revision links and license to users and preserve them in downloads.
Do not label this data MIT or remove its source metadata when combining it with
other datasets. The asset's source-level `changes` records the extraction and
normalization. No photos, logos, media, results or third-party article prose
appear in the asset.

Primary organizer pages below were used as **accuracy checks**. They do not
supply the data's redistribution grant; the actual extracted fields come from
the explicitly licensed pinned Wikipedia tables. No official API payload was
copied into the asset.

## Date and coverage review

### World Climbing

The extracted dates match all 13 senior Series spans in the
[World Climbing January calendar announcement](https://www.worldclimbing.com/news/china-events-confirmed-to-complete-2026-calendar).
Source labels are preserved: Wikipedia calls the Spanish stop Madrid, while
the announcement calls its host municipality Alcobendas. No exact arena is
invented. Disciplines are taken from the same Wikipedia table and retained as
stop notes. Men's/women's results and relay rows are grouped into one stop.

The source's Guiyang September 11–13 inclusive span also matches the
[official event page](https://www.worldclimbing.com/events/world-climbing-series-guiyang-2026/).
The previous research found a disagreement over individual Speed rounds on
September 11 versus 12 in a separate generated feed. No such rounds, timestamps
or inferred durations are included here; the stop span is unaffected.

The dates range from May 1–3 at Keqiao to October 23–25 at Santiago. IDs include
season and stop identity, so future date corrections do not create new events.
This scope excludes youth, para, continental events, Games, a separate Nations
Grand Finale, and a nonexistent 2026 senior World Championship. It does not
claim to cover every event organized by World Climbing.

### NASCAR Cup

The numbered schedule rows are exactly 1–36, February 15 through November 8.
The Clash, the grouped Daytona Duel row and All-Star Race are excluded. No
practice, qualifying, support series or individual Duel-session coverage is
implied. The extraction expands rowspans before selecting fields, including
Daytona's inherited track/location cells.

All nine remaining race dates, September 13 through November 8, agree with
NASCAR's [August 5 television-calendar article](https://www.nascar.com/news-media/2026/08/05/how-to-watch-nascar-races-on-nbc-usa-sports-peacock-nbc-sports-app/).
That article still calls the October 11 track the Charlotte Roval. The venue's
[September 10 notice](https://www.charlottemotorspeedway.com/media/news/countdown-bank-america-400-weekend-charlotte-motor-speedway.html)
confirms the race is on the oval and calls it Bank of America 400. The pinned
Wikipedia source already has that corrected name and plain Charlotte Motor
Speedway venue, which are retained. This is a resolved source-age disagreement,
not a reason to change the supported October 11 race date.

Sponsor titles are the pinned table's titles and may change. Race identities
use season plus points-race round, not sponsor or date. The two Cook Out 400
races therefore remain distinct. All ET clocks are omitted: this review does
not certify television listings as actual green-flag times.

### IndyCar

Exactly 18 numbered championship races are included, March 1 through September
6. The season is complete, so this is archive coverage with no remaining 2026
race promise. It includes Washington, D.C.; the original 17-race announcement
does not represent this later season schedule. Track/location rowspans at
Indianapolis and Milwaukee are expanded before extraction.

The two unusual date values have specific primary corroboration:

- Nashville is **July 20**, not the original July 19. INDYCAR's
  [postponement notice](https://www.indycar.com/news/2026/07/07-19-nashville-rain-)
  confirms the move after rain.
- Milwaukee round 16 is **August 29–30**, representing one interrupted race.
  INDYCAR's [resumption notice](https://www.indycar.com/news/2026/08/08-29-milwaukee-restart)
  confirms that the first race began Saturday and continued Sunday. Round 17
  remains a separate August 30 race. Do not collapse the first span or dedupe
  the second race by venue/date.

The remaining dates were reviewed against the pinned table, with the
[current official schedule](https://www.indycar.com/Schedule) used as a secondary
sanity check; no exhaustive independent audit of all race sponsor titles was
performed. No practice, qualifying, warmup, support-series or exact clocks are
published.

## Reproduction and maintenance

The checked-in registry is the publication input. `scripts/refresh-public.py`
loads it without requesting Wikimedia and normalizes it through the shared
validated exporter. The registry preserves the input URLs, exact retrieved byte
hashes, revision links and transformations; full article responses remain local
review evidence under the collection's
`reports/sportsbro-expansion/implementation/` directory and are not shipped.

For a source update, inspect the pinned source and a newer revision, check the
scope and primary evidence above, preserve stable IDs, and update the registry's
source receipt and changed records together. Retain the prior raw inputs locally.
Re-rendered MediaWiki HTML can change when templates change, even at the same
article revision; a changed byte hash requires review. Builds never auto-approve
upstream article edits. Run the tests and review the published snapshot diff
before releasing. See [operations](../OPERATIONS.md).
