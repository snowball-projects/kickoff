# sportsbro

A calendar for the sports you follow, by snowball.

**[Open sportsbro](https://snowball-projects.github.io/sportsbro/)**

Choose individual leagues or whole collapsible sport groups, scroll up or down
through months, zoom out to the year, or open a day's events. Hover an event for
its dates, time, location and notes. Focusing a day previews its first event;
Enter or a tap opens all events and sources, and Escape dismisses the preview.
The heading follows the visible month; **Today** at the
bottom left returns smoothly to the current month. Reduced-motion settings skip
the animation. Interests stay on your device; no account, analytics, live scores
or betting features.

With a day focused, arrow keys move between days, Page Up/Down changes month,
and Shift + Page Up/Down changes year. Search covers the year shown in the
heading. Calendar navigation spans 1900–2100; years without a published schedule
are marked unavailable.

The reviewed 2026 collection covers nine football leagues, F1, World Climbing,
NASCAR Cup, IndyCar, selected NFL and combat cards, IWF Worlds, golf majors and
selected PGA/LPGA season dates. Most added golf entries show only a tournament's
listed final date; they are labeled **Final date**, with no implied opening date.
[Coverage and data licenses](docs/PUBLIC_RELEASE.md) give exact inclusions and
omissions. Most additions are date-only; verified F1 times use your device's zone.
Software is MIT; Wikipedia-derived schedule data retains CC BY-SA 4.0.

## Run

```sh
cd frontend
npm ci
npm run dev
```

Node 24 is used for deployment. From `frontend`, verify the calendar with:

```sh
npm test
npx playwright install chromium
npm run test:browser
npm run build
```

Unit tests check dates, navigation, scroll state and schedule loading. Browser
tests exercise the scrolling calendar; `PLAYWRIGHT_CHROME=1 npm run test:browser`
uses an installed Google Chrome instead of Playwright's Chromium. The build
prepares the checked-in reviewed snapshot and writes static `frontend/dist/`.
Normal builds make no schedule-provider requests.

## Ingestion and verification

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock -e '.[dev]'
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m ruff format --check src tests scripts
.venv/bin/python -m pytest
.venv/bin/python -m build --no-isolation
```

To refresh the public snapshot explicitly:

```sh
.venv/bin/python scripts/refresh-public.py --year 2026
```

This pins upstream commits, retains raw inputs locally, normalizes approved
sources and passes through the sanitized web exporter. Review the resulting
`data/published/2026.json` diff before publishing. A failed fetch does not replace
the last published snapshot. Original official-source adapters remain available
through `sportsbro fetch`, `validate`, `audit` and `export-web` for local use;
the public frontend build accepts only reviewed open-source datasets.

- [Operation and next steps](docs/OPERATIONS.md)
- [Windows merge reconciliation](docs/MERGE-REPAIR.md)
- [Icon source and prompt](assets/PROMPT.md)

## License

Original code: [MIT](LICENSE). Third-party schedules and dependencies retain
[their licenses](THIRD-PARTY-NOTICES.md). No official league affiliation.

[Operations](https://snowball-projects.github.io/operations/#sportsbro)
