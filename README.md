# kickoff

[A calendar for the sports you follow](https://snowball-projects.github.io/kickoff/), by snowball.
Choose leagues, browse Calendar or Agenda, and open an event for its sources.
Interests stay on your device. Times use your timezone; date-only events keep their source dates.

Use Python 3.12+ and Node 24:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock -e '.[dev]'
npm ci --prefix frontend
.venv/bin/python scripts/refresh-public.py
npm --prefix frontend run dev
```

Check and build:

```sh
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m ruff format --check src tests scripts
.venv/bin/python -m pytest
npm --prefix frontend test
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run test:browser
npm --prefix frontend run build
```

Pages runs checks, fetches all schedules, builds and deploys daily at 09:17 UTC,
on pushes to main and on demand. Nothing is committed back. A failed feed reuses
only its events and provenance from the live site's data; after deployment the
run fails with a summary naming each failed feed. Missing or invalid fallback
stops publication, preserving the live site. Local refresh accepts `--year 2026`.

Reviewed facts, source links and historical check dates live in `data/reviewed`;
edit records and their receipts together, preserving IDs and uncertainty.
Generated data lives in `frontend/public/data`, and the build writes `frontend/dist`.
The original local adapters remain available through `kickoff fetch`, `validate`,
`audit` and `export-web`. Code is [MIT](LICENSE); data retains its [source terms](THIRD-PARTY-NOTICES.md).
