import copy
import hashlib
import json
from pathlib import Path

import pytest

from kickoff.reviewed_schedules import load_reviewed_schedules, reviewed_events
from kickoff.web import _event_payload

ROOT = Path(__file__).resolve().parents[1]


def registry():
    return json.loads((ROOT / "data/reviewed/2026-climbing-sessions.json").read_text())


def test_climbing_sessions_keep_verified_instants_disciplines_and_uncertainty():
    events, sources = reviewed_events(registry(), 2026)
    assert len(events) == 16
    assert len(sources) == 2
    assert sum(e.start_time_utc is not None for e in events) == 11
    assert all(e.source == "world_climbing" and e.event_type == "session" for e in events)
    slc = [e for e in events if "Salt Lake City" in e.title]
    santiago = [e for e in events if "Santiago" in e.title]
    assert len(slc) == 6 and len(santiago) == 10
    assert all("Boulder" in e.tags and "Lead" not in e.tags and "Speed" not in e.tags for e in slc)
    assert all("Boulder" not in e.tags and ("Lead" in e.tags or "Speed" in e.tags) for e in santiago)
    final = next(e for e in slc if "Men's Boulder final" in e.title)
    assert final.start_time_local == "2026-10-17T19:00:00-06:00"
    assert final.start_time_utc == "2026-10-18T01:00:00Z"
    assert final.calendar_date == final.end_calendar_date == "2026-10-17"
    speed = next(e for e in santiago if "Speed final" in e.title)
    assert speed.start_time_local == "2026-10-24T18:00:00-03:00"
    assert speed.start_time_utc == "2026-10-24T21:00:00Z"
    assert speed.start_time_scope == "shared_session"
    shared = [e for e in events if e.start_time_scope == "shared_session"]
    assert len(shared) == 4
    assert {e.start_time_utc for e in shared} == {"2026-10-24T21:00:00Z", "2026-10-25T12:00:00Z"}
    assert sum(e.start_time_utc is None for e in events) == 5
    combinations = []
    for e in events:
        assert " & " not in e.title
        gender = next(t for t in e.tags if t in {"Men", "Women"})
        discipline = next(t for t in e.tags if t in {"Lead", "Boulder", "Speed"})
        combinations.append((e.venue, gender, discipline, e.round_or_stage))
        assert not (discipline == "Speed" and e.round_or_stage == "semi-final")
    assert len(set(combinations)) == len(events)
    for event in events:
        if event.start_time_utc is None:
            assert event.start_time_local is event.timezone is None
            assert "Time withheld:" in event.subtitle
    all_events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    climbing = [e for e in all_events if e.league == "IFSC_WORLD_CUP"]
    assert len(climbing) == 27
    assert sum("event dates" in e.tags for e in climbing) == 11
    assert all(any(d in e.tags for d in ("Boulder", "Lead", "Speed")) for e in climbing)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["sources"][0].update(url="https://www.worldclimbing.com/events/unreviewed"),
        lambda p: p["sources"][0].update(license="MIT"),
        lambda p: p["sources"][0].update(sha256=""),
        lambda p: p["events"][0].update(local_time="25:00"),
        lambda p: p["events"][0].update(local_time="09:00+08:00"),
        lambda p: p["events"][0].update(timezone="Asia/Shanghai"),
        lambda p: p["events"][0].update(start_date="2026-10-15", end_date="2026-10-15"),
        lambda p: p["events"][0].update(end_date="2026-10-18"),
        lambda p: p["events"][0].update(league="IWF_WORLDS"),
        lambda p: p["events"][0].update(disciplines=["Speed"]),
        lambda p: p["events"][0].update(disciplines=["Lead", "Boulder"]),
        lambda p: p["events"][0].update(local_time=None, notes=""),
        lambda p: p["events"][0].update(start_time_scope="guessed"),
        lambda p: p["events"][0].update(start_time_scope="shared_session", local_time=None),
        lambda p: p["events"][0].update(gender="combined"),
        lambda p: p["events"][0].update(round_or_stage="practice"),
    ],
)
def test_climbing_publication_boundary_rejects_unreviewed_inputs(mutate):
    payload = copy.deepcopy(registry())
    mutate(payload)
    with pytest.raises(ValueError):
        reviewed_events(payload, 2026)


def test_published_sessions_match_sanitized_registry_and_licensed_component():
    bundle = json.loads((ROOT / "data/published/2026.json").read_text())
    events, sources = reviewed_events(registry(), 2026)
    published = {e["event_id"]: e for e in bundle["events"] if e["source"] == "world_climbing"}
    # Snapshot statuses reflect publication day, not the day this test runs.
    assert {k: {f: v for f, v in e.items() if f != "status"} for k, e in published.items()} == {
        e.event_id: {f: v for f, v in _event_payload(e).items() if f != "status"} for e in events
    }
    assert all(s in bundle["sources"] for s in sources)
    assert "no data license granted" in bundle["data_licenses"]["world_climbing"]
    assert not any(
        e["event_id"] in {"world-climbing-series-2026-salt-lake-city", "world-climbing-series-2026-santiago"}
        for e in bundle["events"]
    )
    for component in bundle["components"]:
        raw = (ROOT / "data/published" / component["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == component["sha256"]
        data = json.loads(raw)
        assert data["events"] == [e for e in bundle["events"] if e["source"] == data["sources"][0]["kind"]]
        assert all(e["source"] != "world_climbing" for e in data["events"])


def test_offline_refresh_preserves_official_climbing_sessions(monkeypatch, tmp_path):
    from kickoff.open_schedules import refresh_open_schedules
    from tests.test_reviewed_schedules import fake_open_read

    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    path = refresh_open_schedules(2026, tmp_path / "working", tmp_path / "published", ROOT / "data/reviewed")
    bundle = json.loads(path.read_text())
    sessions = [e for e in bundle["events"] if e["source"] == "world_climbing"]
    assert len(sessions) == 16
    assert sum(e["start_time_utc"] is not None for e in sessions) == 11
    assert len([s for s in bundle["sources"] if s.get("kind") == "world_climbing"]) == 2
    assert bundle["data_licenses"]["world_climbing"] == "Schedule facts; no data license granted"
    assert "World Climbing stop/session records" in bundle["coverage"]
