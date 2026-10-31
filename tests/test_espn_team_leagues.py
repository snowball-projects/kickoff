import copy
import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds
from kickoff.validation import validate_batch
from kickoff.web import _event_payload

FIXTURE = json.loads((Path(__file__).parent / "fixtures/espn-team-leagues.json").read_text())
CASES = {row["label"]: row for row in FIXTURE["cases"]}


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["label"])
def test_primary_scoreboard_phases_and_factual_team_fields(case):
    row = case["event"]
    league = case["league"]
    phase = feeds.espn_team_phase(row, league)
    assert phase == case["expected_phase"]
    sport = feeds.TEAM_LEAGUES[league][1]
    event = feeds._espn_event(
        row,
        league=league,
        sport=sport,
        zone=feeds.EASTERN,
        fallback_url=case["url"],
        input_url=case["url"],
        phase=phase,
    )
    assert validate_batch([event]) == []
    assert event.facts_source_url == case["url"] and event.facts_checked_date
    assert event.week_label is None if sport != "football" else event.week_label is not None
    for participant in event.participants:
        original = next(r for r in row["competitions"][0]["competitors"] if r["homeAway"] == participant.role)
        assert participant.short_name == original["team"]["shortDisplayName"]
        total = next((r["summary"] for r in original.get("records", []) if r["type"] == "total"), None)
        assert participant.record == total
        assert (
            participant.final_score == int(original["score"])
            if event.status == "finished"
            else participant.final_score is None
        )
    public = _event_payload(event)
    assert "raw_source_payload" not in public and "odds" not in public


def test_every_civil_day_including_ncaa_postseason_and_both_year_boundaries(monkeypatch):
    calls = []
    ncaa = CASES["mens_final"]["event"]
    regular = CASES["mens_d1_regular"]["event"]

    def get(url):
        query = parse_qs(urlsplit(url).query)
        prefix = query["dates"][0]
        calls.append(prefix)
        assert query["groups"] == ["50"] and query["limit"] == ["1000"]
        assert len(prefix) == 8
        return {"events": [ncaa] if prefix == "20260406" else [regular] if prefix == "20260117" else []}

    monkeypatch.setattr(feeds, "get_json", get)
    events = feeds.espn_team_events(2026, "NCAA_MENS_BASKETBALL")
    assert len(calls) == len(set(calls)) == 367
    assert "20251231" in calls and "20270101" in calls
    assert "20260715" in calls  # no off-season date cap
    assert {e.competition_phase for e in events} == {"regular_season", "final"}
    assert len(events) == 2


def test_fbs_and_fcs_union_keeps_cross_division_game_once_and_week_facts(monkeypatch):
    calls = []
    game = CASES["fbs_bowl"]["event"]
    game = {**game, "date": "2026-12-01T00:30Z"}

    def get(url):
        query = parse_qs(urlsplit(url).query)
        calls.append((query["dates"][0], query["groups"][0]))
        assert query["limit"] == ["200"]  # 1000 silently falls back to25 in this API
        return {"events": [{}, game] if query["dates"] == ["20261130"] else []}

    monkeypatch.setattr(feeds, "get_json", get)
    (event,) = feeds.espn_team_events(2026, "COLLEGE_FOOTBALL")
    assert len(calls) == 734 and {g for _, g in calls} == {"80", "81"}
    assert {"fbs", "fcs"} <= set(event.tags)
    assert event.calendar_date == "2026-11-30"
    assert event.is_postseason and event.week_label
    assert "LA Bowl" in event.round_or_stage


@pytest.mark.parametrize(
    "league,label,count",
    [
        ("NCAA_MENS_BASKETBALL", "mens_d1_regular", 145),
        ("NCAA_WOMENS_BASKETBALL", "womens_d1_regular", 122),
    ],
)
def test_grouped_heavy_days_retain_every_returned_game(monkeypatch, league, label, count):
    # Synthetic identities exercise the complete source-derived heavy-day count.
    games = [{**CASES[label]["event"], "id": f"synthetic-{i}"} for i in range(count)]

    def get(url):
        query = parse_qs(urlsplit(url).query)
        assert query["groups"] == ["50"]
        return {"events": games if query["dates"] == ["20260117"] else []}

    monkeypatch.setattr(feeds, "get_json", get)
    result = feeds.espn_team_events(2026, league)
    assert len(result) == len({e.event_id for e in result}) == count


def test_saturated_year_and_month_split_without_truncating_or_losing_source_urls(monkeypatch):
    league = "WNBA"
    path, sport, groups, _ = feeds.TEAM_LEAGUES[league]
    monkeypatch.setitem(feeds.TEAM_LEAGUES, league, (path, sport, groups, 2))
    regular = CASES["wnba_regular_season"]["event"]
    one = {**regular, "id": "1", "date": "2026-01-01T20:00Z"}
    two = {**regular, "id": "2", "date": "2026-01-02T20:00Z"}
    calls = []

    def get(url):
        prefix = parse_qs(urlsplit(url).query)["dates"][0]
        calls.append(prefix)
        if prefix in {"2026", "202601"}:
            return {"events": [one, two]}
        return {"events": [one] if prefix == "20260101" else [two] if prefix == "20260102" else []}

    monkeypatch.setattr(feeds, "get_json", get)
    events = feeds.espn_team_events(2026, league)
    assert len(events) == 2
    assert "202612" in calls and "20260131" in calls
    assert all("dates=2026010" in e.facts_source_url for e in events)


def test_a_saturated_daily_response_stops_publication(monkeypatch):
    path, sport, groups, _ = feeds.TEAM_LEAGUES["COLLEGE_FOOTBALL"]
    monkeypatch.setitem(feeds.TEAM_LEAGUES, "COLLEGE_FOOTBALL", (path, sport, groups, 1))
    monkeypatch.setattr(feeds, "get_json", lambda _url: {"events": [CASES["fbs_bowl"]["event"]]})
    with pytest.raises(ValueError, match="refusing to truncate"):
        feeds.espn_team_events(2026, "COLLEGE_FOOTBALL")


def test_in_season_invitational_is_not_a_conference_postseason_tournament():
    row = copy.deepcopy(CASES["mens_conference_final"]["event"])
    row["competitions"][0]["conferenceCompetition"] = False
    row["competitions"][0]["notes"] = [{"type": "event", "headline": "Maui Invitational - Final"}]
    assert feeds.espn_team_phase(row, "NCAA_MENS_BASKETBALL") == "regular_season"
    assert FIXTURE["checked_date"] == date.fromisoformat(FIXTURE["checked_date"]).isoformat()


def test_soccer_leg_notes_preserve_the_published_competition_stage(monkeypatch):
    row = CASES["nations_playoff"]["event"]
    monkeypatch.setattr(feeds, "get_json", lambda url: {"events": [row] if "dates=2026&" in url else []})
    (event,) = feeds.espn_team_events(2026, "UEFA_NATIONS_LEAGUE")
    assert event.round_or_stage == "Relegation playoffs"
    assert event.subtitle == "Relegation playoffs · 1st Leg"
    assert event.week_label is None and event.is_postseason


def test_tournament_round_metadata_keeps_specific_round_and_full_popup_note(monkeypatch):
    row = CASES["mens_final"]["event"]
    monkeypatch.setattr(feeds, "get_json", lambda url: {"events": [row] if "dates=20260406&" in url else []})
    (event,) = feeds.espn_team_events(2026, "NCAA_MENS_BASKETBALL")
    assert event.round_or_stage == "National Championship"
    assert event.subtitle == "NCAA Men's Basketball Championship - National Championship"
    assert event.competition_phase == "final"
