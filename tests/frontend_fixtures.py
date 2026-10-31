"""Small offline UI inputs, derived from reviewed facts with explicitly synthetic feeds."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from kickoff import feeds
from kickoff.open_schedules import refresh_open_schedules
from kickoff.published import publish_sports
from kickoff.reviewed_schedules import load_reviewed_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read


def build(output: Path) -> None:
    reviewed, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    payload = json.loads((ROOT / "tests/fixtures/espn-golf.json").read_text())
    with patch("kickoff.feeds.get_json", lambda url: payload["feeds"]["lpga" if "/lpga/" in url else "pga"]):
        pga = feeds.FEEDS["PGA_TOUR"][1](2026)
        lpga = feeds.FEEDS["LPGA_TOUR"][1](2026)
    nfl = [replace(e, source="espn", source_url="https://www.espn.com/nfl/") for e in reviewed if e.league == "NFL"]
    with TemporaryDirectory(prefix="kickoff-fixture-") as staging:
        with patch("kickoff.open_schedules.read_url", fake_open_read):
            path = refresh_open_schedules(
                2026,
                Path(staging),
                ROOT / "data/reviewed",
                feeds={
                    "PGA_TOUR": ("espn", lambda _: pga),
                    "LPGA_TOUR": ("espn", lambda _: lpga),
                    "NFL": ("espn", lambda _: nfl),
                },
            )
        current = json.loads(path.read_text())
    # An empty source year still appears in metadata without an event-file request.
    boundary = {**current, "season": 2027, "events": [], "sources": [], "input_evidence": [], "exclusions": []}
    publish_sports([current, boundary], output)


if __name__ == "__main__":
    import sys

    build(Path(sys.argv[1]))
