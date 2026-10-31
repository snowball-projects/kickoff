import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kickoff import feeds
from kickoff.open_schedules import football_events
from kickoff.validation import validate_event
from kickoff.web import _event_payload

ROOT = Path(__file__).resolve().parents[1]
FACTS = json.loads((ROOT / "tests/fixtures/team-facts.json").read_text())


def espn(row, league="NFL", sport="football"):
    return feeds._espn_event(
        row,
        league=league,
        sport=sport,
        zone=feeds.EASTERN,
        fallback_url="https://www.espn.com/",
        input_url="https://site.api.espn.com/source",
    )


def test_espn_supplied_short_names_records_week_and_only_completed_scores():
    scheduled = espn(FACTS["nfl"])
    final = espn(FACTS["nfl_final"])
    assert scheduled.week_label == scheduled.round_or_stage == "Week 9"
    assert scheduled.home_participant.short_name == "Ravens"
    assert scheduled.home_participant.record == "4-3"
    assert all(p.final_score is None for p in scheduled.participants)
    assert final.status == "finished"
    assert [p.final_score for p in final.participants] == [
        int(c["score"]) for c in FACTS["nfl_final"]["competitions"][0]["competitors"]
    ]
    assert final.facts_checked_date == datetime.now(UTC).date().isoformat()
    assert final.facts_source_url == "https://site.api.espn.com/source"
    assert validate_event(final) == []
    public = _event_payload(final)
    assert public["home_participant"]["record"] == final.home_participant.record
    assert public["facts_checked_date"] == final.facts_checked_date
    assert "odds" not in public and "raw_source_payload" not in public


def test_nba_top_level_records_join_both_team_ids_without_extra_requests(monkeypatch):
    calls = []

    def read(url, **_):
        calls.append(url)
        if url.endswith("/nba/teams"):
            return {"sports": [{"leagues": [{"teams": [{"team": {"id": str(i)}} for i in range(1, 31)]}]}]}
        for payload in FACTS["nba"]:
            if f"/teams/{payload['team']['id']}/schedule?season=2027&seasontype=2" in url:
                return payload
        return {"events": []}

    monkeypatch.setattr(feeds, "get_json", read)
    (event,) = feeds.nba_events(2026)
    assert len(calls) == 91
    assert event.status == "finished"
    assert event.home_participant.short_name == "Magic" and event.away_participant.short_name == "Hawks"
    assert event.home_participant.final_score == 125 and event.away_participant.final_score == 132
    for p in event.participants:
        original = next(row for row in FACTS["nba"] if row["team"]["id"] == p.participant_id)
        assert p.record == original["team"]["recordSummary"]
        assert f"/teams/{p.participant_id}/schedule?season=2027&seasontype=2" in p.team_source_url
    assert event.week_label is None and event.round_or_stage is None
    assert validate_event(event) == []


def test_ucl_retains_source_record_and_phase_without_inventing_match_number():
    event = espn(FACTS["ucl"], "UEFA_CHAMPIONS_LEAGUE", "soccer")
    assert event.home_participant.record == "0-2-1"
    assert event.home_participant.short_name == "Fenerbahce"
    assert event.round_or_stage == "League phase" and event.week_label is None
    assert event.home_participant.final_score == event.away_participant.final_score == 2


def test_official_league_record_score_and_name_availability(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *_a, **_k: {"dates": [{"games": [FACTS["mlb"]]}]})
    (mlb,) = feeds.mlb_events(2026)
    assert mlb.status == "finished" and mlb.away_participant.record == "4-1"
    assert mlb.home_participant.short_name is None
    assert [mlb.away_participant.final_score, mlb.home_participant.final_score] == [4, 1]
    assert mlb.round_or_stage == "World Series Game 5"
    monkeypatch.setattr(
        feeds,
        "get_json",
        lambda *_a, **_k: {
            "gameWeek": [{"date": "2026-10-31", "games": [FACTS["nhl"]]}],
            "nextStartDate": "2027-01-01",
        },
    )
    (nhl,) = feeds.nhl_events(2026)
    assert nhl.home_participant.short_name == "Bruins"
    assert all(p.record is None for p in nhl.participants)
    assert [nhl.away_participant.final_score, nhl.home_participant.final_score] == [4, 5]
    assert nhl.week_label is nhl.round_or_stage is None
    assert validate_event(mlb) == validate_event(nhl) == []


def test_openfootball_retains_only_supplied_final_scores_and_matchday():
    payload = {
        "matches": [
            {"date": "2026-10-31", "round": "Matchday 9", "team1": "Home", "team2": "Away", "score": {"ft": [0, 2]}}
        ]
    }
    (event,) = football_events(payload, "en.1", "2026-27", "https://example.com/pinned.json")
    assert event.round_or_stage == "Matchday 9" and event.status == "finished"
    assert event.home_participant.final_score == 0 and event.away_participant.final_score == 2
    assert all(p.record is p.short_name is None for p in event.participants)
    assert validate_event(event) == []


@pytest.mark.parametrize(
    "change",
    [
        lambda e: setattr(e, "facts_checked_date", None),
        lambda e: setattr(e, "facts_checked_date", "unknown"),
        lambda e: setattr(e, "facts_source_url", "not a source"),
        lambda e: setattr(e.home_participant, "record", "unknown"),
        lambda e: setattr(e.home_participant, "final_score", -1),
        lambda e: setattr(e.home_participant, "final_score", True),
        lambda e: setattr(e, "status", "scheduled"),
    ],
)
def test_produced_team_facts_require_dates_sources_and_confirmed_scores(change):
    event = espn(copy.deepcopy(FACTS["nfl_final"]))
    change(event)
    assert validate_event(event)


def test_copied_nfl_assets_match_original_receipts():
    assets = json.loads((ROOT / "frontend/src/team-assets.json").read_text())
    assert len(assets) == 32
    for asset in assets.values():
        path = ROOT / "frontend/public" / asset["url"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        assert asset["source"].startswith("https://") and asset["license_url"].startswith("https://")
        if path.suffix == ".png":
            assert asset["usage_basis"] and asset["reviewed_at"]


def test_a_finished_bout_does_not_mark_its_whole_card_finished():
    row = copy.deepcopy(FACTS["nfl_final"])
    row["status"] = {"type": {"completed": False, "state": "in"}}
    event = feeds._espn_event(
        row, league="UFC", sport="combat", zone=feeds.EASTERN, fallback_url="https://www.espn.com/", event_type="card"
    )
    assert event.status == "scheduled"


def test_short_names_without_records_still_require_their_checked_date():
    event = espn(copy.deepcopy(FACTS["nfl"]))
    for p in event.participants:
        p.record = None
    event.week_label = None
    event.facts_checked_date = None
    assert validate_event(event)
