"""Fetch every schedule into generated static assets; primary feed failures stop publication."""

import argparse
import json
import shutil
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from kickoff.feeds import FEEDS
from kickoff.open_schedules import refresh_open_schedules
from kickoff.published import publish_sports


def refresh(years: list[int], output: Path, reviewed: Path) -> None:
    with TemporaryDirectory(prefix="kickoff-collect-") as staging:
        bundles = [
            json.loads(
                refresh_open_schedules(
                    year, Path(staging), reviewed, feeds=FEEDS, available_seasons=years, enrich_times=True
                ).read_text()
            )
            for year in years
        ]
    print(publish_sports(bundles, output))


def coverage_years(today: date) -> list[int]:
    """Source years for the rolling window in every visitor timezone.

    Two boundary days cover the UTC/local today difference plus an event's
    source-date conversion. Annual bundles retain these boundary spillovers.
    """
    start = today.replace(year=today.year - 1, day=min(today.day, monthrange(today.year - 1, today.month)[1]))
    end = today.replace(year=today.year + 1, day=min(today.day, monthrange(today.year + 1, today.month)[1]))
    return list(range((start - timedelta(days=2)).year, (end + timedelta(days=2)).year + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        help="Calendar year; repeatable. Default: one year back through one year forward",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    years = args.year or coverage_years(datetime.now(timezone.utc).date())
    refresh(years, root / "frontend/public/data", root / "data/reviewed")
    for name in ["LICENSE", "THIRD-PARTY-NOTICES.md"]:
        shutil.copyfile(root / name, root / "frontend/public" / name)


if __name__ == "__main__":
    main()
