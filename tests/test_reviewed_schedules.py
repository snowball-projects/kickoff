import copy
import json
from pathlib import Path

import pytest

from kickoff.open_schedules import refresh_open_schedules
from kickoff.reviewed_schedules import load_reviewed_schedules, reviewed_events

ROOT = Path(__file__).resolve().parents[1]


def reviewed_registry():
    return json.loads((ROOT / "data/reviewed/2026-climbing-motorsport.json").read_text())


def test_reviewed_dates_keep_inclusive_span_and_stable_identity():
    payload = reviewed_registry()
    events, notices = reviewed_events(payload, 2026)
    event = next(e for e in events if e.event_id == "indycar-2026-round-16")
    assert (event.calendar_date, event.end_calendar_date) == ("2026-08-29", "2026-08-30")
    assert event.start_time_utc is event.start_time_local is event.timezone is None
    assert events and notices
    moved = copy.deepcopy(payload)
    row = next(row for row in moved["events"] if row["id"] == event.event_id)
    row["start_date"] = "2026-08-30"
    assert (
        next(e for e in reviewed_events(moved, 2026)[0] if e.event_id == event.event_id).calendar_date == "2026-08-30"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["sources"][0].update(license="MIT"),
        lambda p: p["sources"][0].update(url="https://en.wikipedia.org/wiki/2026_Masters_Tournament"),
        lambda p: p["sources"][0].update(sha256=""),
        lambda p: p["events"][0].update(start_date="2026-04"),
        lambda p: p["events"][0].update(end_date="2025-04-08"),
        lambda p: p["events"][0].update(start_time_utc="2026-04-09T00:00:00Z"),
        lambda p: p["events"].append(p["events"][0]),
    ],
)
def test_registry_rejects_unpinned_unlicensed_or_false_precision(mutation):
    payload = reviewed_registry()
    mutation(payload)
    with pytest.raises(ValueError):
        reviewed_events(payload, 2026)


def test_all_reviewed_assets_have_valid_provenance_and_dates():
    events, sources, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    assert events and sources
    assert len({event.event_id for event in events}) == len(events)
    assert all(event.start_time_utc is None for event in events if event.source == "wikipedia")


def test_openfootball_expansion_has_correct_season_paths(monkeypatch, tmp_path):
    requests = []

    def read(url):
        requests.append(url)
        return fake_open_read(url)

    monkeypatch.setattr("kickoff.open_schedules.read_url", read)
    result = refresh_open_schedules(2026, tmp_path / "published")
    bundle = json.loads(result.read_text())
    assert len(bundle["events"]) == 10
    assert sum(url.endswith("br.1.json") for url in requests) == 1
    assert any(url.endswith("/2026/br.1.json") for url in requests)
    assert all(
        any(url.endswith(f"/{season}/{league}.json") for url in requests)
        for season in ("2025-26", "2026-27")
        for league in ("en.2", "nl.1", "pt.1")
    )
    football = [e for e in bundle["events"] if e["source"] == "openfootball"]
    assert all(e["start_time_utc"] and e["start_time_local"] for e in football)


def fake_open_read(url):
    if "/commits/" in url:
        return json.dumps({"sha": "a" * 40}).encode()
    if "/contents/" in url:
        return json.dumps([{"type": "dir", "path": "src/data/seasons/2026/races/01"}]).encode()
    if url.endswith("race.yml"):
        return b"id: 1234\nround: 1\ndate: 2026-03-01\ntime: 12:00\ngrandPrixId: test\ncircuitId: monaco\n"
    if url.endswith("/circuits/monaco.yml"):
        return b"id: monaco\ncountryId: monaco\n"
    if url.endswith("/countries/monaco.yml"):
        return b"id: monaco\nalpha2Code: MC\n"
    season = url.split("/")[-2]
    day = "2025-10-01" if season == "2025-26" else "2026-10-01"
    return json.dumps(
        {"matches": [{"date": day, "time": "20:00", "team1": "Home", "team2": "Away", "round": "Round 1"}]}
    ).encode()


def test_chase_rounds_and_major_championships_keep_phase():
    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    chase = [event for event in events if event.league == "NASCAR_CUP" and event.is_postseason]
    assert len(chase) == 10
    assert all(int(event.event_id.rsplit("-", 1)[1]) >= 27 for event in chase)
    assert all(event.competition_phase == "championship" for event in events if event.league == "IWF_WORLDS")


def test_nfl_selection_has_real_participants_and_keeps_melbourne_venue_date():
    from kickoff.semantics import is_malformed_event

    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    games = [event for event in events if event.league == "NFL"]
    assert len(games) == 19
    assert all(not is_malformed_event(event) and len(event.participants) == 2 for event in games)
    melbourne = next(event for event in games if "Melbourne" in event.title)
    assert melbourne.calendar_date == "2026-09-11"
    assert melbourne.home_participant.name == "Los Angeles Rams"
    assert melbourne.away_participant.name == "San Francisco 49ers"
