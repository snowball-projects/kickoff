# Four small openfootball additions

Verified September 11, 2026 using public JSON at commit `41a6eb96ba816757ff892387da5cb111390a7f9c`. `inspect_openfootball.py` retrieves the seven pinned files without third-party Python dependencies and creates `openfootball-evidence.json` with hashes, byte sizes, counts, ranges, field shapes, exceptional statuses, and round counts.

The [repository README](https://github.com/openfootball/football.json/blob/41a6eb96ba816757ff892387da5cb111390a7f9c/README.md) expressly dedicates schema, data, and scripts to the public domain; the repository has a matching [CC0 1.0 license](https://github.com/openfootball/football.json/blob/41a6eb96ba816757ff892387da5cb111390a7f9c/LICENSE.md). This is the same already-reviewed source family. Continue existing contributor attribution and per-input revision/hash evidence. No new service, API key, subscription, or large runtime is required.

| Key | Proposed league identifier / label | Files for calendar year 2026 | All rows / rows dated 2026 |
| --- | --- | --- | --- |
| `en.2` | `CHAMPIONSHIP` / Championship | `2025-26/en.2.json`, `2026-27/en.2.json` | 557 + 552 / 271 + 288 = **559** |
| `nl.1` | `EREDIVISIE` / Eredivisie | `2025-26/nl.1.json`, `2026-27/nl.1.json` | 306 + 306 / 154 + 153 = **307** |
| `pt.1` | `PRIMEIRA_LIGA` / Primeira Liga | `2025-26/pt.1.json`, `2026-27/pt.1.json` | 306 + 306 / 164 + 144 = **308** |
| `br.1` | `BRASILEIRAO` / Brasileiro Série A | **`2026/br.1.json`** | 380 / **380** |

That is **1,554** additional dated 2026 records before any cancellation/postponement filtering. All source rows have dates; no within-file duplicate `(team1, team2, round)` identities were found. Empty future score fields are normal. Scores are mixed dictionaries (`ft` lists) and direct lists: keep the existing normalization supporting both. No file declares a timezone even when its rows have `time`; continue emitting date-only events.

For cross-year European leagues, fetch `(year-1)-(year last two digits)` and `year-(year+1 last two digits)`, then filter events by actual calendar date. Brazil uses the single calendar-year path `str(year)/br.1.json`; do not try `2025-26/br.1.json` or `2026-27/br.1.json`, or fetch Brazil twice. Preserve a useful failure when a season file is not yet published. Do not silently replace the whole prior snapshot with partial results.

Two semantic fixes are necessary when expanding the existing football parser:

1. **Respect source status.** Two Eredivisie rows are `status: "canceled"`: NAC Breda–SC Heerenveen on May 10 and FC Utrecht–Go Ahead Eagles on September 8. Four rows are `status: "postponed"`: Braga–Gil Vicente on August 16; Mineiro–Bragantino, Chapecoense–Vasco, and São Paulo–Santos on July 29. None has a final score. The existing score-only status calculation would incorrectly mark them scheduled. Preserve cancellation/postponement clearly or exclude them from the ordinary upcoming calendar until a confirmed replacement date exists.
2. **Do not label playoffs regular season.** The 2025–26 Championship source has 552 league games plus five records whose exact round label is `Playoffs`. Preserve these with postseason/playoff phase and `is_regular_season=False`, or explicitly omit them from a regular-season-only scope. The 2026–27 file currently has only the 552 league fixtures. Do not imply future playoffs are complete.

The README says current JSON is rebuilt daily from Football.TXT, but upstream Football.TXT editing itself has no automatic daily update. A fresh repository revision must not be marketed as a guarantee that every schedule change has been reviewed.
