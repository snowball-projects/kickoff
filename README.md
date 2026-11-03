# kickoff

[A calendar for the sports you follow](https://snowball-projects.github.io/kickoff/), by snowball.
Choose leagues, browse Calendar or Agenda, and open an event for its sources.
Interests stay on your device. Times use your timezone; date-only events keep their source dates.
Golf has daily rounds and ESPN top-five leaderboards in Agenda and event popups.
The calendar spans one year before today through one year after today,
with events where sources provide them.

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

Pages fetches all schedules, builds and deploys daily at 09:17 UTC, on pushes to
main and on demand. A primary schedule feed failure stops publication, leaving
the live site unchanged. Failed optional ESPN clock lookups log a warning and
leave affected events date-only; existing source times are preserved. The daily
build writes nothing back. Team logos use supplied ESPN images and the checked-in
URL list, read offline across seasons. Add missing logos in a normal PR to
`src/kickoff/config/team_logos.json`, under league and provider/team ID (or exact
source name when no ID exists), with reviewed names, `source_url` and `checked_date`.
Country-image URLs also need an audited entry in
`espn-country-images.json` matching the team's reviewed national country identity;
clubs do not use country images. Checks run in CI on pull requests.
Local schedule refresh accepts `--year 2026`.

Reviewed facts, source links and historical check dates live in `data/reviewed`;
edit records and their receipts together, preserving IDs and uncertainty.
The manifest and per-year league files live in `frontend/public/data`; browsers load
only selected leagues.
The build writes `frontend/dist`.
The original local adapters remain available through `kickoff fetch`, `validate`,
`audit` and `export-web`. Code is [MIT](LICENSE); data retains its [source terms](THIRD-PARTY-NOTICES.md).
