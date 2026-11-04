"""Fetch every schedule into generated static assets; primary feed failures stop publication."""

import argparse
import json
import shutil
import sys
import zlib
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from types import SimpleNamespace
from urllib.parse import quote
from urllib.request import Request, urlopen

from kickoff.feeds import FEEDS
from kickoff.http import MAX_BYTES, read_bounded_response
from kickoff.open_schedules import refresh_open_schedules
from kickoff.published import PublishedWindow, load_published_window, publish_sports
from kickoff.refresh_metrics import refresh_metrics
from kickoff.result_loader import ResultsLoader
from kickoff.weightlifting_startlists import StartListLoader

PUBLIC_DATA = "https://snowball-projects.github.io/kickoff/data/"
BASELINE_BUDGET_SECONDS = 90
BASELINE_SOCKET_SECONDS = 15


class PublishedFiles:
    """Read our CDN with normal caching, gzip and eight bounded concurrent reads."""

    def __init__(self):
        self.deadline = monotonic() + BASELINE_BUDGET_SECONDS

    def read_bytes(self, name: str) -> bytes:
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Published baseline deadline exceeded")
        request = Request(
            PUBLIC_DATA + quote(name, safe=""),
            headers={
                "User-Agent": "kickoff-refresh (https://github.com/snowball-projects/kickoff)",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        chunks, size = [], 0
        with urlopen(request, timeout=min(BASELINE_SOCKET_SECONDS, remaining)) as response:
            while True:
                if monotonic() >= self.deadline:
                    raise TimeoutError("Published baseline deadline exceeded")
                chunk = response.read1(min(65_536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Published baseline exceeds transfer size limit")
            buffered = SimpleNamespace(headers=response.headers, read=BytesIO(b"".join(chunks)).read)
        if monotonic() >= self.deadline:
            raise TimeoutError("Published baseline deadline exceeded")
        return read_bounded_response(buffered)

    def read_many(self, names):
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(self.read_bytes, name): name for name in names}
            bodies = {}
            for future in as_completed(futures):
                try:
                    bodies[futures[future]] = future.result()
                except (OSError, ValueError, EOFError, zlib.error):
                    pass
            return bodies


def refresh(
    years, output, reviewed, *, force_full=False, read_bytes=None, read_many=None, clock=None, result_loader=None
):
    with refresh_metrics():
        now = (clock or (lambda: datetime.now(timezone.utc)))()
        if force_full:
            window = PublishedWindow(now)
        else:
            if read_bytes is None:
                reader = PublishedFiles()
                read_bytes, read_many = reader.read_bytes, reader.read_many
            window = load_published_window(read_bytes, now, read_many)
        start_lists = StartListLoader()
        with TemporaryDirectory(prefix="kickoff-collect-") as staging:
            staging = Path(staging)
            collected = staging / "collected"
            collected.mkdir()
            bundles = [
                json.loads(
                    refresh_open_schedules(
                        year,
                        collected,
                        reviewed,
                        feeds=FEEDS,
                        available_seasons=years,
                        enrich_times=True,
                        start_list_loader=start_lists,
                        result_loader=result_loader,
                        window=window,
                    ).read_text()
                )
                for year in years
            ]
            published = staging / "published"
            publish_sports(bundles, published)
            output.mkdir(parents=True, exist_ok=True)
            for path in sorted(published.iterdir(), key=lambda p: p.name == "manifest.json"):
                shutil.copyfile(path, output / path.name)
            (output / "refresh-state.json").unlink(missing_ok=True)
        return window


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
    parser.add_argument(
        "--force-full", action="store_true", help="Rebuild everything from sources, ignoring published files"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    years = args.year or coverage_years(datetime.now(timezone.utc).date())
    refresh(
        years,
        root / "frontend/public/data",
        root / "data/reviewed",
        force_full=args.force_full,
        result_loader=ResultsLoader(),
    )
    for name in ["LICENSE", "THIRD-PARTY-NOTICES.md"]:
        shutil.copyfile(root / name, root / "frontend/public" / name)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
