import copy
import hashlib
import json
from pathlib import Path

import pytest

from kickoff.open_schedules import refresh_open_schedules
from kickoff.reviewed_schedules import load_reviewed_schedules, reviewed_events

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
    assert len(events) == 76
    assert len(notices) == 13
    moved = copy.deepcopy(payload)
    row = next(row for row in moved["events"] if row["id"] == event.event_id)
    row["start_date"] = "2026-07-31"
    assert (
        next(e for e in reviewed_events(moved, 2026)[0] if e.event_id == event.event_id).calendar_date == "2026-07-31"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["sources"][0].update(license="MIT"),
        lambda p: p["sources"][0].update(url="https://en.wikipedia.org/wiki/2026_Masters_Tournament"),
        lambda p: p["sources"][0].update(sha256=""),
        lambda p: p["events"][0].update(start_date="2026-04"),
        lambda p: p["events"][0].update(end_date="2026-04-08"),
        lambda p: p["events"][0].update(start_time_utc="2026-04-09T00:00:00Z"),
        lambda p: p["events"][0].update(date_scope="final_date"),
        lambda p: p["events"][0].update(date_scope="guessed"),
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


def test_golf_season_additions_keep_final_dates_explicit_and_majors_separate():
    events, notices = reviewed_events(golf_registry(), 2026)
    pga = [event for event in events if event.league == "PGA_TOUR"]
    lpga = [event for event in events if event.league == "LPGA_TOUR"]
    assert len(pga) == 41
    assert len(lpga) == 26
    markers = [event for event in events if "final date only" in event.tags]
    assert len(markers) == 63
    assert all(event.calendar_date == event.end_calendar_date for event in markers)
    assert all("opening date" in event.subtitle for event in markers)
    assert all(event.start_time_utc is event.start_time_local is event.timezone is None for event in events)
    assert {event.calendar_date[5:7] for event in pga} == {f"{month:02}" for month in range(1, 12)}
    players = next(event for event in pga if event.title == "The Players Championship")
    assert (players.calendar_date, players.end_calendar_date, players.source) == (
        "2026-03-12",
        "2026-03-15",
        "wikidata",
    )
    assert len([event for event in pga if event.competition_phase == "postseason"]) == 3
    assert next(event for event in pga if event.title == "Travelers Championship").calendar_date == "2026-06-29"
    assert not any("Sentry" in event.title for event in events)
    assert sum(event.league == "GOLF_MAJORS_MEN" for event in events) == 4
    assert sum(event.league == "GOLF_MAJORS_WOMEN" for event in events) == 5
    assert {notice["license"] for notice in notices} == {"CC BY-SA 4.0", "CC0 1.0"}


def test_network_failure_preserves_published_snapshot(monkeypatch, tmp_path):
    target = tmp_path / "published"
    target.mkdir()
    old = target / "2026.json"
    old.write_text("previous reviewed snapshot")

    def fail(_):
        raise OSError("offline")

    monkeypatch.setattr("kickoff.open_schedules.read_url", fail)
    with pytest.raises(OSError, match="offline"):
        refresh_open_schedules(2026, tmp_path / "working", target)
    assert old.read_text() == "previous reviewed snapshot"


def test_openfootball_expansion_has_correct_season_paths(monkeypatch, tmp_path):
    requests = []

    def read(url):
        requests.append(url)
        return fake_open_read(url)

    monkeypatch.setattr("kickoff.open_schedules.read_url", read)
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


def fake_open_read(url):
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


def test_late_refresh_failure_keeps_prior_components_and_truthful_partial_coverage(monkeypatch, tmp_path):
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    reviewed = tmp_path / "reviewed"
    reviewed.mkdir()
    registry = reviewed / "2026-golf.json"
    registry.write_text(json.dumps(golf_registry()))
    output = tmp_path / "published"
    path = refresh_open_schedules(2026, tmp_path / "working", output, reviewed)
    original = path.read_bytes()
    bundle = json.loads(original)
    assert "4 men's golf majors" in bundle["coverage"]
    assert "World Climbing" not in bundle["coverage"]
    modified = golf_registry()
    modified["events"][0]["title"] += " revised"
    registry.write_text(json.dumps(modified))
    write = Path.write_bytes

    def fail_final(path, body):
        if path == output / "2026.tmp":
            raise OSError("disk full during final write")
        return write(path, body)

    monkeypatch.setattr(Path, "write_bytes", fail_final)
    with pytest.raises(OSError, match="disk full"):
        refresh_open_schedules(2026, tmp_path / "working", output, reviewed)
    assert path.read_bytes() == original
    for component in bundle["components"]:
        assert hashlib.sha256((output / component["path"]).read_bytes()).hexdigest() == component["sha256"]


def test_chase_rounds_and_major_championships_keep_phase():
    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    chase = [event for event in events if event.league == "NASCAR_CUP" and event.is_postseason]
    assert len(chase) == 10
    assert all(int(event.event_id.rsplit("-", 1)[1]) >= 27 for event in chase)
    assert all(event.competition_phase == "championship" for event in events if event.league == "IWF_WORLDS")


def test_wikidata_prose_cannot_be_published_as_cc0():
    payload = golf_registry()
    payload["sources"][0].update(
        url="https://www.wikidata.org/w/index.php?title=Wikidata:Licensing&oldid=1365105813",
        license="CC0 1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
    )
    with pytest.raises(ValueError, match="structured Wikidata"):
        reviewed_events(payload, 2026)


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
