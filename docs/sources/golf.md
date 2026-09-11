# Golf majors source review

Reviewed September 11, 2026. The scope is the four men's and five women's 2026
majors, one inclusive competitive-round date span per tournament. All nine
records come from separately pinned Wikipedia tournament infoboxes under
CC BY-SA 4.0; none is presented as a complete PGA, LPGA, DP World or LIV tour.
THE PLAYERS, team cups, qualifying and practice rounds are outside this scope.
All nine majors are now past; no future 2027 dates are implied.

The [reviewed registry](../../data/reviewed/2026-golf.json) supplies contributor
attribution, exact article revisions, raw API-byte hashes, retrieval times,
license links and transformation notices for each row. No images, article prose,
results, fields, prize money or tee times are retained. Adapted schedule records
keep CC BY-SA 4.0, separate from the MIT software.

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

These dates are read from the actual individual tournament source, rather than
subtracting days from a season-table end date. The [LPGA Evian page](https://www.lpga.com/tournaments/the-evian-championship)
corroborates July 9–12. [The Open spectator timeline](https://www.theopen.com/tickets-and-hospitality/spectator-guide)
distinguishes July 12–15 practice days from July 16–19 championship play.
Those official pages are accuracy checks, not the redistribution license.

The earlier Wikidata candidate review found missing or wrong dates for PGA,
U.S. Open, The Open and Evian. This implementation consistently uses the verified
Wikipedia infoboxes for all nine events, avoiding a false claim of complete
CC0 golf coverage. No serialized midnight or inferred timezone is emitted.
The Women's Open remains visible on each day through August 2.

The official PGA business-week ICS is outside the public allowlist. It does not
establish competitive-round spans or an open redistribution grant. Full tour
feeds and exact tee times remain specifically unsupported.

Publication is reproducible from the checked-in registry without contacting
Wikimedia. The original API responses and extraction probe remain in the local
collection review directory; the public repository contains the selected data
and source receipts. Future source changes require a deliberate registry review,
then ordinary refresh, tests and a published snapshot diff.
