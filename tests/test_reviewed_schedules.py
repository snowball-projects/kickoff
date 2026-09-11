import copy
import json
from pathlib import Path

import pytest

from sportsbro.open_schedules import refresh_open_schedules
from sportsbro.reviewed_schedules import load_reviewed_schedules, reviewed_events

ROOT = Path(__file__).resolve().parents[1]


def golf_registry():
    return json.loads((ROOT / "data/reviewed/2026-golf.json").read_text())


def test_reviewed_dates_keep_inclusive_cross_month_span_and_stable_identity():
    payload = golf_registry()
    events, notices = reviewed_events(payload, 2026)
    event = next(
        e
        for e in events
        if e.event_id.endswith("womens-open") and e.league == "GOLF_MAJORS_WOMEN" and e.calendar_date.endswith("07-30")
    )
    assert event.end_calendar_date == "2026-08-02"
    assert event.start_time_utc is event.start_time_local is event.timezone is None
    assert len(events) == len(notices) == 9
    moved = copy.deepcopy(payload)
    moved["events"][-1]["start_date"] = "2026-07-31"
    assert reviewed_events(moved, 2026)[0][-1].event_id == events[-1].event_id


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["sources"][0].update(license="MIT"),
        lambda p: p["sources"][0].update(url="https://en.wikipedia.org/wiki/2026_Masters_Tournament"),
        lambda p: p["sources"][0].update(sha256=""),
        lambda p: p["events"][0].update(start_date="2026-04"),
        lambda p: p["events"][0].update(end_date="2026-04-08"),
        lambda p: p["events"][0].update(start_time_utc="2026-04-09T00:00:00Z"),
        lambda p: p["events"].append(p["events"][0]),
    ],
)
def test_registry_rejects_unpinned_unlicensed_or_false_precision(mutation):
    payload = golf_registry()
    mutation(payload)
    with pytest.raises(ValueError):
        reviewed_events(payload, 2026)


def test_all_reviewed_assets_have_valid_provenance_and_dates():
    events, sources, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    assert events and sources
    assert len({event.event_id for event in events}) == len(events)
    assert all(event.start_time_utc is None for event in events)


def test_network_failure_preserves_published_snapshot(monkeypatch, tmp_path):
    target = tmp_path / "published"
    target.mkdir()
    old = target / "2026.json"
    old.write_text("previous reviewed snapshot")

    def fail(_):
        raise OSError("offline")

    monkeypatch.setattr("sportsbro.open_schedules.read_url", fail)
    with pytest.raises(OSError, match="offline"):
        refresh_open_schedules(2026, tmp_path / "working", target)
    assert old.read_text() == "previous reviewed snapshot"


def test_openfootball_expansion_has_correct_season_paths(monkeypatch, tmp_path):
    requests = []

    def read(url):
        requests.append(url)
        if "/commits/" in url:
            return json.dumps({"sha": "a" * 40}).encode()
        if "/contents/" in url:
            return json.dumps([{"type": "dir", "path": "src/data/seasons/2026/races/01"}]).encode()
        if url.endswith("race.yml"):
            return b"id: 1234\nround: 1\ndate: 2026-03-01\ntime: 12:00\ngrandPrixId: test\n"
        season = url.split("/")[-2]
        day = "2025-10-01" if season == "2025-26" else "2026-10-01"
        return json.dumps(
            {"matches": [{"date": day, "time": "20:00", "team1": "Home", "team2": "Away", "round": "Round 1"}]}
        ).encode()

    monkeypatch.setattr("sportsbro.open_schedules.read_url", read)
    result = refresh_open_schedules(2026, tmp_path / "working", tmp_path / "published")
    bundle = json.loads(result.read_text())
    assert len(bundle["events"]) == 10
    assert sum(url.endswith("br.1.json") for url in requests) == 1
    assert any(url.endswith("/2026/br.1.json") for url in requests)
    assert all(
        any(url.endswith(f"/{season}/{league}.json") for url in requests)
        for season in ("2025-26", "2026-27")
        for league in ("en.2", "nl.1", "pt.1")
    )
    assert all(e["start_time_utc"] is None for e in bundle["events"] if e["source"] == "openfootball")
