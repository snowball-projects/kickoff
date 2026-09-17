# Combat sports and IWF snapshot review

Reviewed September 11, 2026. The data in [`data/reviewed/2026-combat-iwf.json`](../../data/reviewed/2026-combat-iwf.json) is a selected community
schedule snapshot, not a complete live feed. It has **85 date-only events** and
seven pinned source records. No official promoter feed, paid API, artwork,
scraped fight card, broadcast clock, estimated duration or individual ring-walk
time is included.

## Supported scope

| League | Records | Exact scope |
| --- | ---: | --- |
| UFC | 42 | The scheduled and past event rows present in the reviewed 2026 annual article, January 24–December 12. This is annual coverage as listed at review, not a promise that all remaining cards have been announced. |
| PFL | 16 | Main global PFL cards present in the 2026 table. Six Africa/MENA regional rows are omitted. No separate Bellator or future rebranded season is inferred. Chicago's October card uses its separate article because the annual table has a conflicting date. |
| RIZIN | 9 | Nine of ten 2026 annual rows. The November 8 event is held because the official site still presents two identities. |
| ONE | 16 | Whole Fight Night 39–50 and Samurai 1–4 cards as present in the reviewed article. Five are future rows. Friday Fights and The Inner Circle are excluded. Cards are `combat_sports`, because they can combine MMA, Muay Thai, kickboxing and grappling. |
| IWF Worlds | 1 | Senior World Weightlifting Championships, October 27–November 8 inclusive. This is the championship span, not a claim that lifting happens every day. |
| Major boxing | 1 | The individually reviewed upcoming Navarrete–Foster card qualifying under the explicit three-belt unification rule below. This is not a complete historical or future boxing calendar. |

All dates stay as calendar dates from the reusable source. A Wikipedia day is
not converted to midnight UTC. ONE's Asian event dates can differ from a US
broadcast-date label; no conversion or time is inferred. IWF's two Wikidata
claims have day precision (`precision=11`) despite their serialized midnight
suffix. Both ends of its span are included. No venue is added for IWF, because
the reviewed entity supplies none.

## Sources and attribution

| Source ID | Pinned source | Data terms |
| --- | --- | --- |
| `wikipedia-ufc` | [2026 in UFC, revision 1374208261](https://en.wikipedia.org/w/index.php?title=2026_in_UFC&oldid=1374208261) | CC BY-SA 4.0 |
| `wikipedia-pfl` | [2026 in Professional Fighters League, revision 1374220528](https://en.wikipedia.org/w/index.php?title=2026_in_Professional_Fighters_League&oldid=1374220528) | CC BY-SA 4.0 |
| `wikipedia-pfl-chicago` | [PFL Chicago: Carmouche vs. Bishop 2, revision 1374088812](https://en.wikipedia.org/w/index.php?title=PFL_Chicago%3A_Carmouche_vs._Bishop_2&oldid=1374088812) | CC BY-SA 4.0 |
| `wikipedia-rizin` | [2026 in Rizin Fighting Federation, revision 1374349911](https://en.wikipedia.org/w/index.php?title=2026_in_Rizin_Fighting_Federation&oldid=1374349911) | CC BY-SA 4.0 |
| `wikipedia-one` | [2026 in ONE Championship, revision 1374372383](https://en.wikipedia.org/w/index.php?title=2026_in_ONE_Championship&oldid=1374372383) | CC BY-SA 4.0 |
| `wikidata-iwf-worlds-2026` | [Wikidata Q124142978, revision 2499700131](https://www.wikidata.org/w/index.php?title=Q124142978&oldid=2499700131) | CC0 1.0 |
| `wikipedia-navarrete` | [Emanuel Navarrete, revision 1373169260](https://en.wikipedia.org/w/index.php?title=Emanuel_Navarrete&oldid=1373169260) | CC BY-SA 4.0 |

The manifest attributes each Wikipedia page to its contributors, links the
pinned page and [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
and marks the transformations. Adapted Wikipedia schedule content retains
CC BY-SA 4.0, including when distributed within a combined calendar. Preserve
its attribution and notices in the application and exported data. Do not
describe these rows as MIT data or imply promoter endorsement. The software
license remains separate. The [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content)
describe attribution, modified versions and share-alike requirements;
[Wikidata's licensing policy](https://www.wikidata.org/wiki/Wikidata:Licensing)
identifies its structured item data as CC0.

Each manifest `sha256` is the SHA-256 of the exact pinned API response bytes,
not of HTML or the normalized event array. `input_url` identifies that API
request; `url` is a human-readable permanent revision. Raw responses and
receipts are retained in the local collection review directory, under
`combat-source-evidence/`. The one-off local audit helper `build-combat-iwf.py`
verified their revisions and byte hashes; it is not shipped repository tooling. The
Navarrete retrieval timestamp was recovered from the saved response file's
write time after a later request hit HTTP 429; the raw bytes and revision were
already saved. Other source timestamps are the recorded retrieval times.

## Resolved conflicts and primary checks

**UFC October 3:** The initial official events listing showed a Fight Night
with Green–Ribovics while Wikipedia named UFC 332 with Silva–Wang. UFC's
[September 5 announcement](https://www.ufc.com/news/undisputed-flyweight-title-grabs-ufc-332-salt-lake-city)
explicitly identifies UFC 332 on October 3, headlined by Silva–Wang, with
Green–Ribovics on the same card. Its [Brazil event page](https://www.ufc.com.br/event/ufc-332)
also agrees. The Wikipedia row is included once as UFC 332; no clock is copied.

**PFL Chicago October 16/17:** The annual article's October 17 row is rejected.
The separately pinned event article has October 16 in both its date field and
opening description. This agrees with the
[Wintrust Arena event page](https://www.wintrustarena.com/events/detail/pfl-chicago-1016)
and [PFL's own current fighter/event notice](https://pflmma.com/regular-fighter/liz-carmouche).
The single published row points to that separate Wikipedia article, so the
corrected day has reusable provenance rather than a silently overwritten
annual-table value. PFL's odd overnight broadcast labels are not used.

**PFL Dubai and Lyon:** PFL's [September 7 Dubai announcement](https://pflmma.com/news/heavyweight-gold-on-the-line-as-vadim-nemkov-defends-his-pfl-world-title-against-sergei-bilostenniy-at-pfl-dubai)
corroborates November 14. The [September 9 Lyon announcement](https://pflmma.com/news/history-on-the-line-in-lyon-as-taylor-lapilus-and-mitch-mckee-battle-for-inaugural-pfl-bantamweight-world-title)
corroborates December 19 and Lapilus–McKee; the
[LDLC Arena event listing](https://www.olvallee.fr/evenement/pfl-lyon-decembre-2026/)
agrees. These rows keep their Wikipedia source and contain no official-feed
clock or descriptive promotional text.

**RIZIN November 8:** The current
[event index](https://jp.rizinff.com/_tags/%E5%A4%A7%E4%BC%9A%E6%83%85%E5%A0%B1)
and annual-page navigation say Landmark 17, matching the latest Wikipedia
table. However, their [linked event page](https://jp.rizinff.com/_ct/17852466)
still has the RIZIN.55 title. The card is excluded pending a coherent identity.
The other reviewed annual dates match the
[official annual overview](https://jp.rizinff.com/_ct/17813466), including the
December 31 Nagoya event. The exclusion is recorded in the JSON.

**IWF Worlds:** The Wikidata P580/P582 statements point to
[German Wikipedia revision 265407245](https://de.wikipedia.org/w/index.php?title=Weltmeisterschaften_im_Gewichtheben_2026&oldid=265407245).
The [IWF September 7 preparation announcement](https://iwf.sport/2026/09/07/iwf-delegation-impressed-by-outstanding-preparations-for-ningbo-2026/)
independently reconfirms the October 27–November 8 championship span. There is
no session-grid coverage here.

## Boxing qualification evidence

The selected rule includes a card when its qualifying bout contests all four
full WBA/WBC/IBF/WBO world titles, or unifies at least three of those full titles
held by the two reigning champions. It applies equally to men and women.
Interim, regular/secondary, franchise, regional and ceremonial titles do not
qualify; The Ring is not one of the four counted sanctioning bodies. A defense
of three belts against a non-champion does not meet the unification branch.
No owner exception has been added.

| Published card | Qualifying bout and belts | Date/venue evidence |
| --- | --- | --- |
| Emanuel Navarrete vs. O'Shaquie Foster | Navarrete enters as full IBF and WBO super featherweight champion; Foster enters as full WBC champion. These three titles are contested in a unification. The additional vacant Ring title is not counted. | The pinned [Navarrete article](https://en.wikipedia.org/w/index.php?title=Emanuel_Navarrete&oldid=1373169260), opening championship summary and “Navarrete vs. Foster” section, identifies the reigning titles and the announced October 24 card at Frost Bank Center in San Antonio. |

The [Top Rank September 2 announcement](https://toprank.com/news/emanuel-navarrete-oshaquie-foster-unification-showdown-set-for-oct-24-at-frost-bank-center-in-san-antonio-live-on-dazn)
and its [press-conference notice](https://toprank.com/news/press-conference-notes-emanuel-navarrete-and-oshaquie-foster-set-for-three-belt-unification-showdown-october-24-at-frost-bank-center-in-san-antonio)
agree on October 24, the venue and WBO/IBF versus WBC title status. These
event-specific announcements resolve the generic homepage's earlier October
25 card label. The app uses the reusable Wikipedia date and qualification
facts; it does not copy Top Rank's clock or card feed. The WBC notice linked
by Wikipedia returned HTTP 403 during direct review; that page was not
bypassed or treated as separately verified.

Recheck the bout near fight week: sanctions, vacated/stripped titles and weigh-in
eligibility can change qualification. Keep one event identity
`boxing-navarrete-foster-1` when dates or titles are revised. The reviewed set
contains this one upcoming qualifying card, not a claim that all qualifying
2026 fights were enumerated.

## Reproduction and maintenance

The checked-in registry is the publication input. `scripts/refresh-public.py`
loads it without requesting Wikimedia and normalizes it through the shared
validated exporter. The registry preserves the input URLs, exact retrieved byte
hashes, revision links and transformations; full article responses remain local
review evidence under the collection's
`reports/kickoff-expansion/implementation/` directory and are not shipped.

For a source update, inspect the pinned source and a newer revision, check the
scope and primary evidence above, preserve stable IDs, and update the registry's
source receipt and changed records together. Retain the prior raw inputs locally.
Re-rendered MediaWiki HTML can change when templates change, even at the same
article revision; a changed byte hash requires review. Builds never auto-approve
upstream article edits. Run the tests and review the published snapshot diff
before releasing. See [operations](../OPERATIONS.md).
