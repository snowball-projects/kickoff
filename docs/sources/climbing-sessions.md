# October 2026 World Climbing sessions

Reviewed October 15, 2026, at the owner's request to publish sourced session
information. The senior **World Climbing Series** (formerly IFSC World Cup)
stop identities are confirmed independently of the reported dates:

- [Salt Lake City](https://www.worldclimbing.com/events/world-climbing-series-salt-lake-city-2026): **October 16–18**, **Boulder only**. [USA Climbing](https://usaclimbing.org/world-climbing-series-salt-lake-city-2026/) confirms Smith's Ballpark and all three dates. This is separate from the May para and July continental events.
- [Santiago](https://www.worldclimbing.com/events/world-climbing-series-santiago-2026): **October 23–25**, **Lead and Speed**, with no Boulder competition. The [local organizer](https://www.worldclimbingsantiago.cl/) independently confirms both disciplines, dates and Parque Bicentenario de Cerrillos.

The two whole-stop rows are replaced by **16 gender/discipline/round rows**; 11 earlier stops
remain inclusive date-only spans. The resulting calendar has **27 climbing
records representing the same 13 stops**. Each actually scheduled combination
of women/men, discipline and round has its own pill; no separate Speed
semi-final is invented inside the finals session. Discipline tags (`Boulder`, `Lead`,
`Speed`) use the existing tag representation and appear alongside discipline
names in session titles. Earlier stops' tags come from their existing pinned
Wikipedia extraction, without a new source or inferred disciplines.

## Clock review

Clocks below are venue local. The provisional organizer information sheets are
[Salt Lake v2.0, October 8](https://ifsc.results.info/events/1488/infosheet) and
[Santiago v3.1, September 18](https://ifsc.results.info/events/1489/infosheet).
Only clocks that agree across the reviewed detailed sources are published.

| Local date | Session | Published local start |
| --- | --- | --- |
| October 16 | Salt Lake men's Boulder qualification | 09:00 MDT |
| October 16 | Salt Lake women's Boulder qualification | Time TBD: event page 16:00; information sheet 15:30 |
| October 17 | Salt Lake men's Boulder semi-final | 10:00 MDT |
| October 17 | Salt Lake men's Boulder final | 19:00 MDT |
| October 18 | Salt Lake women's Boulder semi-final | 10:00 MDT |
| October 18 | Salt Lake women's Boulder final | 19:00 MDT |
| October 23 | Santiago women's Lead qualification | 09:00 UTC−03:00 |
| October 23 | Santiago men's Speed qualification | Time TBD: event page/sheet 18:30; organizer has combined qualification 19:15 |
| October 23 | Santiago women's Speed qualification | Time TBD: event page/sheet 21:00; organizer has combined qualification 19:15 |
| October 24 | Santiago men's Lead qualification | 09:00 UTC−03:00 |
| October 24 | Santiago men's Speed final | Shared session starts 18:00 UTC−03:00; individual start unknown |
| October 24 | Santiago women's Speed final | Shared session starts 18:00 UTC−03:00; individual start unknown |
| October 25 | Santiago men's Lead semi-final | Shared session starts 09:00 UTC−03:00; individual start unknown |
| October 25 | Santiago women's Lead semi-final | Shared session starts 09:00 UTC−03:00; individual start unknown |
| October 25 | Santiago men's Lead final | Time TBD: sheet says not before 19:00; organizer time unconfirmed |
| October 25 | Santiago women's Lead final | Time TBD: event page/sheet 18:00; organizer time unconfirmed |

The Santiago organizer home page and its structured event data both establish
UTC−03:00, including `2026-10-23T09:00:00-03:00`. Its programme is more specific
than its general introductory sentence about the competition days; the latter
is not used to invent rounds. The two Speed qualification rows retain the
federation's category identities and date while withholding both clocks.

Both information sheets contain inconsistent offset headings: Salt Lake says
local time UTC+8; Santiago says local time UTC+2. These are not used as offsets.
The interpretation as **venue local wall clocks** follows the sheets' explicit
local-time label and the Santiago organizer's explicit offset, with conversion
through IANA `America/Denver` (MDT, UTC−06:00 on October 16–18) and
`America/Santiago` (UTC−03:00 on October 23–25). This is a documented correction
to the headings, not a claim that the organizers corrected their PDFs.
[IANA North America rules](https://github.com/eggert/tz/blob/main/northamerica)
and [South America rules](https://github.com/eggert/tz/blob/main/southamerica)
provide the zone rules; Chile's [2026 Decree 98](https://www.bcn.cl/leychile/navegar?idNorma=1225724)
extends the seasonal regime from September 2026.

Session starts are not first-athlete, first-race, broadcast or warmup clocks.
No end times, durations, practice, isolation, medals or separate gender clocks
for combined sessions are inferred. Four round records carry
`start_time_scope: "shared_session"`: the two Speed finals and two Lead
semi-finals. Their UTC/local timestamps represent the agreed shared session
start, and the UI says **Session starts …** in previews, details and agendas.
Their notes explicitly say the individual gender start is not separately
published. There are seven individual starts, four shared-session markers and
five unknown clocks across 16 round records.

Unknown clocks have null UTC/local/zone
fields and a visible explanation, never a synthetic midnight. The existing UI
converts agreed instants to the visitor's timezone; Salt Lake's 19:00 finals
therefore appear on October 18 and 19 in UTC. Unknown clocks stay on the venue
calendar date.

## Publication boundary and evidence

The owner requested these official schedule facts on October 15. This is a
small, manual, reviewed addition, with exact event-page URLs allowlisted in the
Python importer and frontend preparation gate. It adds no scraper or scheduled
requests to World Climbing or organizer sites. The existing refresh reuses the
checked-in registry. The [website terms](https://www.worldclimbing.com/terms-and-conditions/index)
reserve rights and restrict republication and automated collection; they do
**not** provide an open-data grant. These factual identities, dates, disciplines
and agreed start clocks are attributed with `Schedule facts; no data license
granted`, consistent with kickoff's attributed schedule-fact boundary. Neither
MIT nor Wikipedia's CC BY-SA is asserted over these official facts. No source
prose, media, results or raw HTML/PDF is published.

`data/reviewed/2026-climbing-sessions.json` retains the exact response SHA-256,
retrieval timestamp and transformation note for each event page, plus PDF and
organizer evidence hashes. Hashes identify retrieved bytes, not immutable
upstream revisions; `reviewed-2026-10-15` is a local review label. Raw responses
remain local. The separately licensed Wikipedia component removes only these
two superseded stop spans and gains discipline tags for its remaining stops;
attribution, original revision/hash and adaptation notices are preserved.

Offline tests check source/date/discipline boundaries, IANA conversion,
withheld clocks, immutable component consistency, frontend date rollover and
browser details/source links. No unrelated league schedules are refreshed.
