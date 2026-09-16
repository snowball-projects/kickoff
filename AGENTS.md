# sportsbro

A static sports calendar built from reviewed schedule snapshots. No live
scores, betting or backend by default.

## Scope and sources

- Read `README.md` and `docs/PUBLIC_RELEASE.md` before editing ingestion or
  public output.
- Read the [snowball principles](https://snowball-projects.github.io/principles/)
  before public claims or product, data and architecture decisions.
- Keep Python ingestion, normalization, validation and export separate from the
  static React calendar.

## Development and verification

- Python: install the locked requirements and the editable dev package. In
  `.venv`, run `ruff check src tests scripts`,
  `ruff format --check src tests scripts`, `pytest`, and
  `python -m build --no-isolation`.
- Frontend: Node 24. From `frontend`, run `npm ci`, `npm test`,
  `npx playwright install chromium`, `npm run test:browser` and
  `npm run build`. Keep the lockfile. `PLAYWRIGHT_CHROME=1` uses installed
  Chrome; `npm run dev` supplies a preview. Tests use offline fixtures.

## Interface behavior

- Keep month scrolling native and bounded, preserve the visible position when
  recycling months, honor reduced motion, and retain keyboard day navigation.
- Missing years must not hide available schedules or imply there are no events.
- Keep end-date spans and display-zone date conversions intact.

## Data and privacy

- Public builds accept only reviewed data and published snapshots. Revalidate
  rights, coverage and timezones before adding a source.
- The code's MIT license does not license raw schedules. Preserve citations,
  upstream commits, hashes and dates.
- Raw source and cache data stays local and ignored. Never expose secrets,
  historical private payloads or unfiltered normalized files. Public export
  passes through `sportsbro.web`.

## Publication

- `snowball-projects/sportsbro` is the canonical home; publish only reviewed
  clean source there.
- Review staged changes, then verify the Pages workflow and live assets before
  calling a release published. Do not force-push.
- `docs/MERGE-REPAIR.md` records the September 2026 history repair. Preserve
  both sides of that merge work.

## Stewardship

- Write `sportsbro` and `snowball` in lowercase.
- Original software is MIT; data and dependencies retain their own terms.
- Do not add AI-builder labels or production credits to public copy.
- `CLAUDE.md` imports this file. Keep operational detail in docs rather than
  duplicating agent instructions.
