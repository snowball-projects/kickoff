"""Small offline UI inputs, derived from reviewed facts with explicitly synthetic feeds."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from kickoff import feeds
from kickoff.open_schedules import refresh_open_schedules
from kickoff.reviewed_schedules import load_reviewed_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read


def build(output: Path) -> None:
    reviewed, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    payload = json.loads((ROOT / "tests/fixtures/espn-golf.json").read_text())
    with patch("kickoff.feeds.get_json", lambda url: payload["feeds"]["lpga" if "/lpga/" in url else "pga"]):
        pga = feeds.FEEDS["PGA_TOUR"][1](2026)
        lpga = feeds.FEEDS["LPGA_TOUR"][1](2026)
    nfl = [replace(e, source="espn", source_url="https://www.espn.com/nfl/") for e in reviewed if e.league == "NFL"]
    with patch("kickoff.open_schedules.read_url", fake_open_read):
        refresh_open_schedules(
            2026,
            output,
            ROOT / "data/reviewed",
            feeds={
                "PGA_TOUR": ("espn", lambda _: pga),
                "LPGA_TOUR": ("espn", lambda _: lpga),
                "NFL": ("espn", lambda _: nfl),
            },
        )
    # A boundary fixture verifies the UI without freezing a whole season's remote data.
    (output / "2027.json").write_text(
        json.dumps(
            {"schema_version": "1", "season": 2027, "available_seasons": [2026, 2027], "providers": [], "events": []}
        )
    )


if __name__ == "__main__":
    import sys

    build(Path(sys.argv[1]))
