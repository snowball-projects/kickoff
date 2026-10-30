import importlib.util
import json
import os
import subprocess
import sys
from datetime import date

import pytest

from kickoff import feeds, open_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read

spec = importlib.util.spec_from_file_location("refresh_public", ROOT / "scripts/refresh-public.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_success_fetches_every_configured_feed_and_exports_fresh_data(monkeypatch, tmp_path):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    monkeypatch.setattr(open_schedules, "fill_missing_start_times", lambda *_: [])
    calls = []

    def fetch(league, kind, year):
        calls.append((league, year))
        return [
            feeds.make_event(
                source=kind,
                league=league,
                sport="test",
                upstream_id="fresh",
                season=str(year),
                title=f"{league} fixture",
                day=f"{year}-11-01",
                utc=None,
                source_url="https://example.test/schedule",
            )
        ]

    configured = {
        league: (kind, lambda year, league=league, kind=kind: fetch(league, kind, year))
        for league, (kind, _) in feeds.FEEDS.items()
    }
    monkeypatch.setattr(runner, "FEEDS", configured)
    runner.refresh([2026], tmp_path, ROOT / "data/reviewed")
    bundle = json.loads((tmp_path / "2026.json").read_text())
    assert calls == [(league, 2026) for league in feeds.FEEDS]
    assert bundle["available_seasons"] == [2026]
    assert all(
        any(e["league"] == league and e["event_id"].endswith("fresh") for e in bundle["events"])
        for league in feeds.FEEDS
    )


@pytest.mark.parametrize("failed", ["EPL", "F1", *feeds.FEEDS])
def test_feed_failure_stops_before_build_or_deploy(tmp_path, failed):
    workflow = (ROOT / ".github/workflows/publish.yml").read_text()
    assert workflow.index("Fetch every schedule") < workflow.index("Build site") < workflow.index("Deploy Pages")
    assert "continue-on-error" not in workflow and "always()" not in workflow
    assert "python scripts/refresh-public.py" in workflow
    # Execute the actual refresh entry point with offline sources. Bash's fail-fast
    # execution models the workflow's default success gating for build/deployment.
    bootstrap = tmp_path / "refresh.py"
    bootstrap.write_text("""
import runpy
import sys
from kickoff import feeds, open_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read
failed = sys.argv[1]
def broken(_):
    raise OSError(f"{failed}: source offline")
def read(url):
    if (failed == "EPL" and url.endswith("en.1.json")) or (failed == "F1" and "f1db/f1db" in url):
        return broken(url)
    return fake_open_read(url)
open_schedules.read_url = read
feeds.FEEDS = {league: (kind, broken if league == failed else lambda _: [])
               for league, (kind, _) in feeds.FEEDS.items()}
sys.argv = ["scripts/refresh-public.py", "--year", "2026"]
runpy.run_path(str(ROOT / "scripts/refresh-public.py"), run_name="__main__")
""")
    result = subprocess.run(
        ["bash", "-e", "-c", '"$PYTHON" "$BOOTSTRAP" "$FAILED"\ntouch "$BUILD"\ntouch "$DEPLOY"'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHON": sys.executable,
            "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "src")]),
            "BOOTSTRAP": str(bootstrap),
            "FAILED": failed,
            "BUILD": str(tmp_path / "built"),
            "DEPLOY": str(tmp_path / "deployed"),
        },
    )
    assert result.returncode != 0
    assert f"{failed}: source offline" in result.stderr
    assert not (tmp_path / "built").exists()
    assert not (tmp_path / "deployed").exists()


@pytest.mark.parametrize(
    "fetch",
    [
        feeds.nfl_events,
        feeds.nhl_events,
        feeds.mlb_events,
        feeds.ucl_events,
        feeds.FEEDS["PGA_TOUR"][1],
        feeds.FEEDS["LPGA_TOUR"][1],
    ],
)
def test_malformed_payload_never_becomes_successful_empty_feed(monkeypatch, fetch):
    monkeypatch.setattr(feeds, "get_json", lambda *_, **__: {})
    with pytest.raises((ValueError, KeyError)):
        fetch(2026)


@pytest.mark.parametrize(
    "today,years",
    [
        (date(2026, 10, 27), [2025, 2026, 2027]),
        (date(2028, 2, 29), [2027, 2028, 2029]),
        # Source dates and local today can each differ from UTC at year boundaries.
        (date(2027, 1, 1), [2025, 2026, 2027, 2028]),
        (date(2026, 12, 31), [2025, 2026, 2027, 2028]),
        (date(2027, 1, 3), [2026, 2027, 2028]),
    ],
)
def test_default_coverage_contains_the_rolling_window_and_timezone_boundary_days(today, years):
    assert runner.coverage_years(today) == years


def test_default_refresh_passes_every_coverage_year_to_all_feeds(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 27, tzinfo=timezone.utc)

    calls = []
    monkeypatch.setattr(runner, "datetime", Clock)
    monkeypatch.setattr(sys, "argv", ["refresh-public.py"])
    monkeypatch.setattr(runner, "__file__", str(tmp_path / "scripts/refresh-public.py"))
    monkeypatch.setattr(runner.shutil, "copyfile", lambda *_: None)
    monkeypatch.setattr(runner, "refresh_open_schedules", lambda year, *_, **kwargs: calls.append((year, kwargs)))
    runner.main()
    assert [year for year, _ in calls] == [2025, 2026, 2027]
    assert all(
        kwargs == {"feeds": runner.FEEDS, "available_seasons": [2025, 2026, 2027], "enrich_times": True}
        for _, kwargs in calls
    )


def test_explicit_refresh_years_override_the_default_window(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(sys, "argv", ["refresh-public.py", "--year", "2024", "--year", "2026"])
    monkeypatch.setattr(runner, "__file__", str(tmp_path / "scripts/refresh-public.py"))
    monkeypatch.setattr(runner.shutil, "copyfile", lambda *_: None)
    monkeypatch.setattr(runner, "refresh", lambda years, *_: calls.extend(years))
    runner.main()
    assert calls == [2024, 2026]
