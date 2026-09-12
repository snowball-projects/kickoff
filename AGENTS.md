# sportsbro

- Style `sportsbro` and `snowball` lowercase. Original software is MIT; data and
  dependencies retain their terms. Read snowball's canonical principles before
  public claims, product/data/architecture decisions.
- Keep Python ingestion, normalization, validation and export separate from the
  static React calendar. No live scores, betting or backend by default. Read
  README and docs/PUBLIC_RELEASE.md before editing ingestion/public output.
- Install Python with the locked requirements and editable dev package. Run
  `ruff check src tests scripts`, `ruff format --check src tests scripts`,
  `pytest` and `python -m build --no-isolation` in `.venv`.
- Frontend: Node 24, `npm ci`, `npm test`, `npx playwright install chromium`,
  `npm run test:browser`, `npm run build` from `frontend`. Keep the lockfile.
  `PLAYWRIGHT_CHROME=1` uses installed Chrome for browser tests.
  `npm run dev` supplies a preview. Tests use offline fixtures.
- Keep month scrolling native and bounded, preserve the visible position when
  recycling months, honor reduced motion, and retain keyboard day navigation.
  Missing years must not hide available schedules or imply there are no events.
- Public builds accept only reviewed data/published snapshots. Revalidate rights,
  coverage and timezones before adding a source. Code's MIT license does not
  license raw schedules. Preserve citations, upstream commits, hashes and dates.
- Raw source/cache data stays local and ignored. Never expose secrets, historical
  private payloads or unfiltered normalized files. Public export passes through
  sportsbro.web. Keep end-date spans and display-zone date conversions intact.
- The owner approved deletion of the original `adelevski/sportsbro` GitHub
  repository, and that remote has been deleted. Original/repaired private Git
  history and old release artifacts are retained in the private preservation
  archive; its index maps the former `retirement-review/sportsbro/` folder.
  Publish only reviewed clean source to
  snowball-projects/sportsbro, the owner-approved canonical home.
- Preserve both sides of useful merge work; docs/MERGE-REPAIR.md records the
  September repair. Do not force-push or delete preserved local private history,
  backups or release artifacts.
- CLAUDE.md imports this file. Keep operational detail in docs. Verify Pages and
  live assets before calling a release published; review staged changes first.
