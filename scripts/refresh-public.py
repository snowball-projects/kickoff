"""Explicit network refresh; never invoked by the ordinary frontend build.

Scheduled weekly by .github/workflows/refresh.yml. Warnings mean some data was
kept from the previous snapshot; they are written to --warnings for the workflow.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from kickoff.feeds import FEEDS
from kickoff.open_schedules import refresh_open_schedules

parser = argparse.ArgumentParser()
parser.add_argument("--year", type=int, action="append", help="Calendar year; repeatable. Default: this year and next")
parser.add_argument("--no-feeds", action="store_true", help="Skip the scheduled league feeds")
parser.add_argument("--warnings", type=Path, help="Write refresh warnings to this file")
args = parser.parse_args()
this_year = datetime.now(timezone.utc).year
root = Path(__file__).resolve().parents[1]
warnings: list[str] = []
for year in args.year or [this_year, this_year + 1]:
    path = refresh_open_schedules(
        year,
        root / "data" / "open-working" / str(year),
        root / "data" / "published",
        feeds=None if args.no_feeds else FEEDS,
        warnings=warnings,
    )
    print(path)
for warning in warnings:
    print(f"warning: {warning}")
if args.warnings:
    args.warnings.write_text("".join(f"- {warning}\n" for warning in warnings))
