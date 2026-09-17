"""Explicit network refresh; never invoked by the ordinary frontend build."""

import argparse
from pathlib import Path

from kickoff.open_schedules import refresh_open_schedules

parser = argparse.ArgumentParser()
parser.add_argument("--year", type=int, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
path = refresh_open_schedules(args.year, root / "data" / "open-working", root / "data" / "published")
print(path)
