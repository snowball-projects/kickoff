import json
from datetime import datetime
from urllib.error import HTTPError

import pytest

from kickoff import open_schedules
from kickoff.registry import build_registry
from kickoff.validation import validate_batch
from kickoff.web import _event_payload
from kickoff.world_cup import HOST_CHECKED, HOST_COUNTRIES, HOST_SOURCE, TEAM_COUNTRIES, world_cup_events
from tests.test_reviewed_schedules import fake_open_read


def match(**kwargs):
    return {
        "date": "2026-06-11",
        "time": "13:00 UTC-6",
        "team1": "Mexico",
        "team2": "South Africa",
        "group": "Group A",
        "round": "Matchday 1",
        "ground": "Mexico City",
        **kwargs,
    }


def parse(**kwargs):
    return world_cup_events({"matches": [match(**kwargs)]}, 2026, "https://example.org/pinned")[0]


@pytest.mark.parametrize(
    "clock,utc",
    [
        ("13:00 UTC-6", "2026-06-11T19:00:00Z"),
        ("20:00 UTC-7", "2026-06-12T03:00:00Z"),
        ("12:00 UTC-4", "2026-06-11T16:00:00Z"),
        ("09:00 UTC+5:30", "2026-06-11T03:30:00Z"),
    ],
)
def test_explicit_offset_preserves_source_day_and_instant(clock, utc):
    event = parse(time=clock)
    assert event.start_time_utc == utc
    assert event.calendar_date == event.end_calendar_date == "2026-06-11"
    assert datetime.fromisoformat(event.start_time_local) == datetime.fromisoformat(utc)
    assert validate_batch([event]) == []


@pytest.mark.parametrize("clock", [None, "13:00", "13:00 CST", "25:00 UTC-6", "13:00 UTC-24", "13:00 UTC-6:99"])
def test_unzoned_or_invalid_clock_stops_publication(clock):
    with pytest.raises(ValueError):
        parse(time=clock)


@pytest.mark.parametrize(
    "stage", ["Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Match for third place", "Final"]
)
def test_knockouts_have_phase_label_and_final_scores(stage):
    event = parse(group=None, round=stage, score={"ft": [0, 0], "et": [1, 0]})
    assert event.subtitle == event.round_or_stage == stage
    assert event.is_postseason and not event.is_regular_season
    assert event.status == "finished"
    assert [p.final_score for p in event.participants] == [1, 0]
    assert validate_batch([event]) == []
    assert parse().is_regular_season


def test_penalty_scores_remain_separate_from_on_field_final():
    event = parse(group=None, round="Final", score={"ft": [0, 0], "et": [1, 1], "p": [4, 3]})
    assert event.subtitle == "Final · Penalties 4-3"
    assert [p.final_score for p in event.participants] == [1, 1]
    assert event.round_or_stage == "Final"
    assert parse(score={"ft": [0, 0]}).status == "finished"
    assert parse().home_participant.final_score is None


@pytest.mark.parametrize("score", [{"ft": [None, 0]}, {"et": [-1, 2]}, {"ft": [1]}, {"ft": [True, 0]}])
def test_invalid_supplied_results_stop_publication(score):
    with pytest.raises(ValueError):
        parse(score=score)


def test_all_reviewed_grounds_keep_separate_country_provenance():
    assert len(HOST_COUNTRIES) == 16
    assert sorted(HOST_COUNTRIES.values()).count("US") == 11
    for ground, country in HOST_COUNTRIES.items():
        event = _event_payload(parse(ground=ground))
        assert event["venue"] == ground and event["country"] == country
        assert event["country_source_url"] == HOST_SOURCE
        assert event["country_checked_date"] == HOST_CHECKED
    with pytest.raises(KeyError):
        parse(ground="unverified venue")


def test_national_flags_cross_public_boundary_and_identity_survives_rescheduling():
    assert len(TEAM_COUNTRIES) == 48
    for team, code in TEAM_COUNTRIES.items():
        event = _event_payload(parse(team1=team))
        assert event["participants"][0]["country_code"] == code
        assert event["participants"][0]["entity_type"] == "national_team"
        assert event["facts_source_url"] == event["source_url"]
        assert event["facts_checked_date"]
    first = parse(num=104, group=None, round="Final")
    moved = parse(num=104, group=None, round="Final", date="2026-07-19", time="15:00 UTC-4", team1="Spain")
    assert first.event_id == moved.event_id
    assert parse().event_id == parse(date="2026-06-12").event_id


def test_public_refresh_collects_pinned_world_cup_and_cc0_receipt(monkeypatch, tmp_path):
    requests = []

    def read(url):
        requests.append(url)
        return fake_open_read(url)

    monkeypatch.setattr(open_schedules, "read_url", read)
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path).read_text())
    event = next(e for e in bundle["events"] if e["league"] == "FIFA_WORLD_CUP")
    assert event["subtitle"] == "Group A"
    assert event["start_time_utc"] == "2026-06-11T19:00:00Z"
    assert "/" + "a" * 40 + "/2026/worldcup.json" in event["source_url"]
    source = next(s for s in bundle["sources"] if s["url"].endswith("worldcup.json"))
    assert source["license"] == "CC0 1.0" and source["revision"] == "a" * 40
    receipt = next(s for s in bundle["input_evidence"] if "/worldcup.json/" in s["url"])
    assert receipt["parsed_events"] == 1 and len(receipt["sha256"]) == 64
    assert "fifa_world_cup" not in build_registry()


def test_known_world_cup_404_cannot_silently_publish_empty_tournament(monkeypatch, tmp_path):
    def read(url):
        if url.endswith("/worldcup.json"):
            raise HTTPError(url, 404, "missing edition", {}, None)
        return fake_open_read(url)

    monkeypatch.setattr(open_schedules, "read_url", read)
    with pytest.raises(HTTPError):
        open_schedules.refresh_open_schedules(2026, tmp_path)
    assert not (tmp_path / "2026.json").exists()
