# Reviewed event registries

These are deliberately selected publication inputs. Wikimedia date registries
were reviewed September 11, 2026; the official October climbing session registry
was reviewed October 15, 2026. They are not refreshed by a normal build or a network
schedule refresh. Each row references a source receipt with contributor
attribution, license, exact revision, input URL, raw-byte hash, retrieval time
and transformation notes.

Wikipedia-derived records and adaptations retain **CC BY-SA 4.0**. The IWF and
THE PLAYERS Wikidata structured records retain **CC0 1.0**. These data terms are separate
from the software's MIT license. Preserve the source receipts and applicable
share-alike obligations on reuse. The source URLs identify contributors and
license links provide the applicable terms.

The October climbing registry contains manually reviewed facts from two
explicitly allowlisted official event pages, with source/PDF/organizer byte
hashes and no data license grant. Its optional `local_time` is a verified venue
wall clock; `start_time_scope: "shared_session"` explicitly marks the shared
session start for separate women’s and men’s round records. It does not
establish a gender-specific start. The importer derives an offset and UTC instant using the stop’s
reviewed IANA zone. Unknown or disputed clocks stay null. See the
[session evidence](../../docs/sources/climbing-sessions.md).

The `start_date` and `end_date` fields are inclusive calendar dates, never
synthetic midnight timestamps. A row with `date_scope: "final_date"` has equal
start/end fields representing only the source's final-date marker, not a
one-day tournament. Missing opening dates are not inferred; the public importer
and UI preserve an explicit `final date only` tag. IDs survive renaming or rescheduling. Games
also retain away/home participant identities. See [coverage and source
reviews](../../docs/PUBLIC_RELEASE.md) and [maintenance](../../docs/OPERATIONS.md).
