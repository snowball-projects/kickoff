"""Exact-match enrichments from trimmed ESPN scoreboards and named standings stats."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kickoff import feeds
from kickoff.start_times import fill_missing_start_times, football_teams, team_aliases
from kickoff.validation import validate_event
from kickoff.web import _event_payload

FIXTURE = json.loads((Path(__file__).parent / "fixtures/espn-team-enrichment.json").read_text())


def primary(key, source, league, sport):
    row = FIXTURE[key]
    participants = {c["homeAway"]: c["team"]["displayName"] for c in row["competitions"][0]["competitors"]}
    if source == "openfootball":
        names = {value: name for name, value in football_teams()[league]["teams"].items()}
        participants = {c["homeAway"]: names[c["team"]["id"]] for c in row["competitions"][0]["competitors"]}
    elif source == "nhl":
        participants = {
            role: "Montréal Canadiens" if name == "Montreal Canadiens" else name for role, name in participants.items()
        }
    return feeds.make_event(
        source=source,
        league=league,
        sport=sport,
        upstream_id=row["id"],
        season="2026",
        title="Home versus away",
        utc=row["date"],
        day=row["date"][:10],
        home=participants["home"],
        away=participants["away"],
        source_url=f"https://example.com/{source}/schedule",
        facts_source_url=f"https://example.com/{source}/schedule",
    )


def answers(monkeypatch, rows):
    calls = []
    monkeypatch.setattr(feeds, "get_json", lambda url: calls.append(url) or {"events": rows})
    return calls


def test_soccer_summary_is_wins_draws_losses_confirmed_against_named_espn_standings():
    stats = {stat["name"]: int(stat["value"]) for stat in FIXTURE["soccer_standings"]["stats"]}
    competitor = next(
        c
        for c in FIXTURE["epl"]["competitions"][0]["competitors"]
        if c["team"]["id"] == FIXTURE["soccer_standings"]["team_id"]
    )
    record = next(r["summary"] for r in competitor["records"] if r["type"] == "total")
    assert record == f"{stats['wins']}-{stats['ties']}-{stats['losses']}" == "5-1-3"


@pytest.mark.parametrize(
    "key,source,league,sport",
    [
        ("epl", "openfootball", "EPL", "soccer"),
        ("nhl", "nhl", "NHL", "hockey"),
        ("mlb", "mlb", "MLB", "baseball"),
        ("world_cup", "openfootball", "FIFA_WORLD_CUP", "soccer"),
    ],
)
def test_known_clocks_receive_missing_team_facts_with_independent_source_receipts(
    monkeypatch, key, source, league, sport
):
    event = primary(key, source, league, sport)
    before = event.to_dict()
    row = FIXTURE[key]
    calls = answers(monkeypatch, [row])
    (receipt,) = fill_missing_start_times([event], 2026)
    assert len(calls) == 1
    assert receipt["clocks_added"] == []
    assert receipt["team_facts_added"][0]["event_id"] == event.event_id
    assert event.facts_checked_date == datetime.now(UTC).date().isoformat()
    for participant in [event.home_participant, event.away_participant, *event.participants]:
        original = next(c for c in row["competitions"][0]["competitors"] if c["homeAway"] == participant.role)
        assert participant.short_name == original["team"]["shortDisplayName"]
        assert participant.record == next(
            r["summary"] for r in original["records"] if r["type"] == ("ytd" if sport == "hockey" else "total")
        )
        assert participant.team_source_url == receipt["team_facts_added"][0]["team_source_url"]
        assert participant.team_source_url.startswith("https://www.espn.com/")
    for field in (
        "event_id",
        "source",
        "source_url",
        "facts_source_url",
        "calendar_date",
        "start_time_utc",
        "timezone",
        "round_or_stage",
        "week_label",
    ):
        assert getattr(event, field) == before[field]
    assert validate_event(event) == []
    assert _event_payload(event)["home_participant"]["team_source_url"] == event.home_participant.team_source_url
    assert fill_missing_start_times([event], 2026) == []


@pytest.mark.parametrize(
    "league",
    [
        "EPL",
        "CHAMPIONSHIP",
        "EREDIVISIE",
        "BUNDESLIGA",
        "LA_LIGA",
        "SERIE_A",
        "LIGUE_1",
        "PRIMEIRA_LIGA",
        "BRASILEIRAO",
    ],
)
def test_every_carried_domestic_soccer_league_fetches_facts_even_without_missing_clocks(monkeypatch, league):
    config = football_teams()[league]
    (home, home_id), (away, away_id) = list(config["teams"].items())[:2]
    event = feeds.make_event(
        source="openfootball",
        league=league,
        sport="soccer",
        upstream_id="known-clock",
        season="2026",
        title="Match",
        utc="2026-10-28T16:00Z",
        day="2026-10-28",
        home=home,
        away=away,
    )
    row = copy.deepcopy(FIXTURE["epl"])
    row["date"] = row["competitions"][0]["date"] = event.start_time_utc
    for c in row["competitions"][0]["competitors"]:
        c["team"]["id"] = home_id if c["homeAway"] == "home" else away_id
    calls = answers(monkeypatch, [row])
    fill_missing_start_times([event], 2026)
    assert calls == [f"{feeds.ESPN}/soccer/{config['espn_path']}/scoreboard?dates=2026&limit=1000"]
    assert all(p.record and p.short_name and p.team_source_url for p in event.participants)


def test_monthly_baseball_lookup_is_shared_and_retains_supplied_records_scores_and_labels(monkeypatch):
    first = primary("mlb", "mlb", "MLB", "baseball")
    second = copy.deepcopy(first)
    second.event_id += "-unmatched"
    second.calendar_date = second.end_calendar_date = "2026-10-03"
    second.start_time_utc = "2026-10-03T20:00:00Z"
    first.status = "finished"
    for p in first.participants:
        p.record = "90-72"
        p.final_score = 4
    calls = answers(monkeypatch, [FIXTURE["mlb"]])
    (receipt,) = fill_missing_start_times([first, second], 2026)
    assert calls == [f"{feeds.ESPN}/baseball/mlb/scoreboard?dates=202610&limit=1000"]
    assert [item["event_id"] for item in receipt["team_facts_added"]] == [first.event_id]
    assert all(p.record == "90-72" and p.final_score == 4 and p.short_name for p in first.participants)
    assert not second.home_participant.short_name
    assert first.week_label is first.round_or_stage is None


@pytest.mark.parametrize("mutation", ["duplicate", "reversed", "wrong-team", "wrong-day", "canceled"])
def test_ambiguous_wrong_team_date_and_canceled_matches_leave_facts_absent(monkeypatch, mutation):
    event = primary("nhl", "nhl", "NHL", "hockey")
    before = event.to_dict()
    row = copy.deepcopy(FIXTURE["nhl"])
    if mutation == "reversed":
        for c in row["competitions"][0]["competitors"]:
            c["homeAway"] = "away" if c["homeAway"] == "home" else "home"
    elif mutation == "wrong-team":
        row["competitions"][0]["competitors"][0]["team"]["displayName"] = "Unrelated team"
    elif mutation == "wrong-day":
        row["date"] = "2026-10-04T23:00Z"
    elif mutation == "canceled":
        row["competitions"][0]["status"] = {"type": {"name": "STATUS_CANCELED"}}
    answers(monkeypatch, [row, copy.deepcopy(row)] if mutation == "duplicate" else [row])
    (receipt,) = fill_missing_start_times([event], 2026)
    assert not receipt["team_facts_added"]
    assert event.to_dict() == before


def test_group_records_and_abbreviations_do_not_fill_absent_overall_record_or_short_display_name(monkeypatch):
    event = primary("world_cup", "openfootball", "FIFA_WORLD_CUP", "soccer")
    for p in event.participants:
        p.entity_type = "national_team"
        p.metadata = {"country_code": "MX" if p.role == "home" else "ZA"}
        p.final_score = 1 if p.role == "home" else 0
    row = copy.deepcopy(FIXTURE["world_cup"])
    for c in row["competitions"][0]["competitors"]:
        c["records"] = [{"type": "group", "summary": "1-0-0"}]
        c["team"].pop("shortDisplayName")
        c["team"]["abbreviation"] = "AAA"
    before = event.to_dict()
    answers(monkeypatch, [row])
    (receipt,) = fill_missing_start_times([event], 2026)
    assert not receipt["team_facts_added"]
    assert event.to_dict() == before


def test_equal_primary_instant_matches_a_venue_date_that_differs_from_utc(monkeypatch):
    event = primary("world_cup", "openfootball", "FIFA_WORLD_CUP", "soccer")
    event.start_time_utc = "2026-06-12T03:00:00Z"
    event.calendar_date = event.end_calendar_date = "2026-06-11"
    row = copy.deepcopy(FIXTURE["world_cup"])
    row["date"] = row["competitions"][0]["date"] = event.start_time_utc
    answers(monkeypatch, [row])
    fill_missing_start_times([event], 2026)
    assert event.home_participant.short_name == "Mexico"
    assert event.calendar_date == "2026-06-11" and event.start_time_utc == "2026-06-12T03:00:00Z"


def test_reviewed_non_soccer_aliases_have_a_source_and_check_date():
    config = team_aliases()["NHL"]
    assert config["teams"] == {"Montréal Canadiens": "Montreal Canadiens", "Utah Utah Hockey Club": "Utah Hockey Club"}
    assert config["source_url"].startswith(f"{feeds.ESPN}/hockey/nhl/")
    assert datetime.fromisoformat(config["checked_date"])


def test_native_espn_hockey_records_share_the_same_overall_parser():
    row = FIXTURE["nhl"]
    event = feeds._espn_event(
        row, league="NHL", sport="hockey", zone=feeds.EASTERN, fallback_url=FIXTURE["sources"]["nhl"]
    )
    for participant in event.participants:
        competitor = next(c for c in row["competitions"][0]["competitors"] if c["homeAway"] == participant.role)
        assert participant.record == next(r["summary"] for r in competitor["records"] if r["type"] == "ytd")
    assert event.week_label is None


def test_historical_utah_name_matches_only_its_reviewed_espn_identity(monkeypatch):
    row = FIXTURE["nhl_2025"]
    event = feeds.make_event(
        source="nhl",
        league="NHL",
        sport="hockey",
        upstream_id="2024020611",
        season="20242025",
        title="Historical NHL game",
        utc=row["date"],
        day="2025-01-02",
        home="Calgary Flames",
        away="Utah Utah Hockey Club",
    )
    calls = answers(monkeypatch, [row])
    fill_missing_start_times([event], 2025)
    assert calls == [FIXTURE["sources"]["nhl_2025"]]
    assert event.away_participant.name == "Utah Utah Hockey Club"
    assert event.away_participant.short_name == "Utah HC"
    assert event.away_participant.record == "17-15-6"
    assert event.home_participant.record == "18-13-7"


def test_unique_same_season_soccer_identity_fills_facts_after_a_date_move_without_changing_clocks(monkeypatch):
    event = primary("epl", "openfootball", "EPL", "soccer")
    event.season = "2026-27"
    event.calendar_date = event.end_calendar_date = "2026-12-29"
    event.start_time_utc = event.start_time_local = None
    row = copy.deepcopy(FIXTURE["epl"])
    answers(monkeypatch, [row])
    (receipt,) = fill_missing_start_times([event], 2026)
    assert event.home_participant.short_name and event.home_participant.record
    assert event.calendar_date == "2026-12-29"
    assert event.start_time_utc is event.start_time_local is None
    assert not receipt["clocks_added"]
    assert receipt["team_facts_added"]


@pytest.mark.parametrize("kind", ["other-season", "ambiguous", "postseason"])
def test_soccer_season_fallback_requires_one_exact_regular_season_pair(monkeypatch, kind):
    event = primary("epl", "openfootball", "EPL", "soccer")
    event.season = "2026-27"
    event.calendar_date = event.end_calendar_date = "2026-12-29"
    event.start_time_utc = "2026-12-29T20:15:00Z"
    row = copy.deepcopy(FIXTURE["epl"])
    if kind == "other-season":
        row["season"]["year"] = 2025
    if kind == "postseason":
        event.competition_phase = "postseason"
    rows = [row, copy.deepcopy(row)] if kind == "ambiguous" else [row]
    answers(monkeypatch, rows)
    before = event.to_dict()
    (receipt,) = fill_missing_start_times([event], 2026)
    assert not receipt["team_facts_added"]
    assert event.to_dict() == before


@pytest.mark.parametrize("conflicting_number", [False, True])
def test_known_doubleheader_instant_supplies_facts_without_inventing_game_numbers(monkeypatch, conflicting_number):
    event = primary("mlb", "mlb", "MLB", "baseball")
    event.raw_source_payload = {"game_number": 2, "double_header": "Y"}
    row = copy.deepcopy(FIXTURE["mlb"])
    row["competitions"][0]["notes"] = [{"headline": "Doubleheader - Game 1"}] if conflicting_number else []
    sibling = copy.deepcopy(row)
    sibling["date"] = sibling["competitions"][0]["date"] = "2026-10-02T03:00Z"
    answers(monkeypatch, [sibling, row])
    (receipt,) = fill_missing_start_times([event], 2026)
    assert not receipt["clocks_added"]
    assert bool(event.home_participant.short_name) is not conflicting_number
    assert bool(receipt["team_facts_added"]) is not conflicting_number


def test_soccer_season_identity_requires_a_single_primary_fixture_too(monkeypatch):
    event = primary("epl", "openfootball", "EPL", "soccer")
    event.season = "2026-27"
    event.calendar_date = event.end_calendar_date = "2026-12-29"
    event.start_time_utc = None
    sibling = copy.deepcopy(event)
    sibling.event_id += "-replay"
    answers(monkeypatch, [FIXTURE["epl"]])
    (receipt,) = fill_missing_start_times([event, sibling], 2026)
    assert not receipt["team_facts_added"]
    assert event.home_participant.record is sibling.home_participant.record is None


@pytest.mark.parametrize("ambiguous", [False, True])
def test_neutral_hockey_facts_follow_team_identity_when_roles_disagree(monkeypatch, ambiguous):
    source = FIXTURE["nhl_neutral_primary"]
    event = feeds.make_event(
        source="nhl",
        league="NHL",
        sport="hockey",
        upstream_id=source["event_id"],
        season="20262027",
        title="Neutral-site game",
        utc=source["start_time_utc"],
        day=source["calendar_date"],
        home=source["home_participant"]["name"],
        away=source["away_participant"]["name"],
    )
    row = FIXTURE["nhl_neutral"]
    answers(monkeypatch, [row, copy.deepcopy(row)] if ambiguous else [row])
    fill_missing_start_times([event], 2026)
    assert event.home_participant.name == "Chicago Blackhawks" and event.home_participant.role == "home"
    assert event.away_participant.name == "Ottawa Senators" and event.away_participant.role == "away"
    if ambiguous:
        assert event.home_participant.record is event.away_participant.record is None
    else:
        assert event.home_participant.record == "4-9-1"
        assert event.away_participant.record == "9-5-1"
    assert event.start_time_utc == source["start_time_utc"]


def test_explicit_source_offset_matches_world_cup_venue_date_when_espn_changes_the_hour(monkeypatch):
    event = primary("world_cup", "openfootball", "FIFA_WORLD_CUP", "soccer")
    event.calendar_date = event.end_calendar_date = "2026-06-30"
    event.start_time_local = "2026-06-30T19:00:00-06:00"
    event.start_time_utc = "2026-07-01T01:00:00Z"
    event.timezone = "UTC-06:00"
    row = copy.deepcopy(FIXTURE["world_cup"])
    row["date"] = row["competitions"][0]["date"] = "2026-07-01T02:00Z"
    answers(monkeypatch, [row])
    (receipt,) = fill_missing_start_times([event], 2026)
    assert event.home_participant.short_name == "Mexico"
    assert event.calendar_date == "2026-06-30"
    assert event.start_time_utc == "2026-07-01T01:00:00Z"
    assert not receipt["clocks_added"]
