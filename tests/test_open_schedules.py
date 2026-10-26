import json
from datetime import datetime, timezone
from urllib.error import HTTPError

import pytest

from kickoff import open_schedules
from kickoff.open_schedules import f1_events, football_events


def test_football_keeps_unzoned_times_unknown_and_stable_identity():
    match = {"date": "2026-09-12", "time": "15:00", "team1": "Home", "team2": "Away", "round": "Matchday 1"}
    first = football_events({"matches": [match]}, "en.1", "2026-27", "https://example.org")[0]
    moved = football_events({"matches": [{**match, "date": "2026-09-13"}]}, "en.1", "2026-27", "https://example.org")[0]
    assert first.start_time_utc is None
    assert first.calendar_date == "2026-09-12"
    assert first.event_id == moved.event_id


def test_football_accepts_both_recorded_score_shapes():
    match = {"date": "2026-09-12", "team1": "Home", "team2": "Away"}
    for score in [{"ft": [0, 0]}, [0, 0]]:
        event = football_events({"matches": [{**match, "score": score}]}, "en.1", "2026-27", "https://example.org")[0]
        assert event.status == "finished"


def test_f1_preserves_saturday_race_and_utc_session_times():
    text = "id: 1164\nround: 15\ndate: 2026-09-26\ntime: 11:00\ngrandPrixId: azerbaijan\nqualifyingDate: 2026-09-25\nqualifyingTime: 12:00\n"
    events = f1_events(text, 2026, "https://example.org")
    assert len(events) == 2
    assert events[0].start_time_utc == "2026-09-26T11:00:00Z"
    assert events[1].event_type == "qualifying"
    assert events[1].calendar_date == "2026-09-25"


def test_football_withholds_postponed_and_canceled_dates_and_classifies_playoffs():
    match = {"date": "2026-05-10", "team1": "Home", "team2": "Away", "round": "Playoffs"}
    rows = [{**match, "status": status} for status in ("canceled", "postponed", "cancelled")]
    assert football_events({"matches": rows}, "en.2", "2025-26", "https://example.org") == []
    event = football_events({"matches": [match]}, "en.2", "2025-26", "https://example.org")[0]
    assert event.competition_phase == "postseason"
    assert event.is_postseason and not event.is_regular_season


def test_only_unpublished_season_404_is_optional(monkeypatch, tmp_path):
    class Clock(datetime):
        month = 10

        @classmethod
        def now(cls, tz=None):
            return datetime(2026, cls.month, 26, tzinfo=timezone.utc)

    monkeypatch.setattr(open_schedules, "datetime", Clock)
    cases = [
        # October: 2026-27 is active; 2027-28 and calendar 2027 are future.
        (10, 2027, "2027-28/en.1.json", 404, True),
        (10, 2027, "2027/br.1.json", 404, True),
        (10, 2027, "/contents/src/data/seasons/2027/races?", 404, True),
        # January: the upcoming European 2026-27 season can be unpublished.
        (1, 2026, "2026-27/en.1.json", 404, True),
        (10, 2026, "2026-27/en.1.json", 404, False),
        (1, 2026, "2025-26/en.1.json", 404, False),
        (10, 2026, "2026/br.1.json", 404, False),
        (10, 2026, "/contents/src/data/seasons/2026/races?", 404, False),
        (10, 2027, "/race.yml", 404, False),
        (10, 2027, "2027-28/en.1.json", 500, False),
        (10, 2027, "/contents/src/data/seasons/2027/races?", 403, False),
    ]
    for index, (month, year, missing, status, optional) in enumerate(cases):
        Clock.month = month

        def read(url, missing=missing, status=status, year=year):
            if missing in url:
                raise HTTPError(url, status, "source unavailable", {}, None)
            if "/commits/" in url:
                return json.dumps({"sha": "a" * 40}).encode()
            if "/contents/" in url:
                return json.dumps([{"type": "dir", "path": f"src/data/seasons/{year}/races/01"}]).encode()
            if url.endswith("race.yml"):
                return f"id: 1234\nround: 1\ndate: {year}-03-01\ngrandPrixId: test\n".encode()
            return json.dumps({"matches": [{"date": f"{year}-05-01", "team1": "Home", "team2": "Away"}]}).encode()

        monkeypatch.setattr(open_schedules, "read_url", read)
        output = tmp_path / str(index)
        if optional:
            bundle = json.loads(open_schedules.refresh_open_schedules(year, output).read_text())
            assert bundle["events"]
            if "/contents/" in missing:
                assert not any(event["source"] == "f1db" for event in bundle["events"])
            else:
                assert not any(missing in event["source_url"] for event in bundle["events"])
        else:
            with pytest.raises(HTTPError) as error:
                open_schedules.refresh_open_schedules(year, output)
            assert error.value.code == status
            assert not (output / f"{year}.json").exists()
