"""Trimmed ESPN tournament and rugby facts, without nested tennis match imports."""

import copy
import json
from urllib.parse import parse_qs, urlparse

import pytest

from kickoff import feeds
from kickoff.open_schedules import refresh_open_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read


@pytest.fixture
def calendars(monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/espn-tournaments.json").read_text())

    def fetch(url):
        parsed = urlparse(url)
        sport, tour, _ = parsed.path.split("/sports/")[1].split("/")
        year = parse_qs(parsed.query)["dates"][0]
        return copy.deepcopy(fixture["feeds"][f"{sport}/{tour}/{year}"])

    monkeypatch.setattr(feeds, "get_json", fetch)
    return fixture


@pytest.mark.parametrize("league,count", [("ATP", 61), ("WTA", 125)])
def test_every_top_level_tennis_tournament_is_one_date_only_span_with_source_major_flag(calendars, league, count):
    events = feeds.FEEDS[league][1](2026)
    original = calendars["feeds"][f"tennis/{league.lower()}/2026"]["events"]
    assert len(events) == len({event.event_id for event in events}) == count
    by_id = {f"espn-{league.lower()}-{row['id']}": row for row in original}
    for event in events:
        row = by_id[event.event_id]
        assert event.source == "espn" and event.sport == "tennis" and event.event_type == "tournament"
        assert event.start_time_utc is None and event.start_time_local is None
        assert event.calendar_date == feeds._local_date(row["date"], feeds.EASTERN)
        assert event.end_calendar_date == feeds._local_date(row["endDate"], feeds.EASTERN)
        assert event.end_calendar_date >= event.calendar_date
        assert event.source_url == (
            row["links"][0]["href"] if row["links"] else f"https://www.espn.com/tennis/schedule/_/type/{league.lower()}"
        )
        assert event.facts_checked_date and f"tennis/{league.lower()}/scoreboard?dates=2026" in event.facts_source_url
        assert not event.participants and not event.week_label
        assert (event.competition_phase == "championship") is row["major"]
    assert sum(event.is_postseason for event in events) == 4
    # Grand Slams are reported by the flag, independent of title/year spelling.
    grand_slam = next(row for row in original if row["major"])
    grand_slam["name"] = "Future sponsor title"
    monkey_event = feeds.FEEDS[league][1](2026)
    assert next(event for event in monkey_event if event.title == "Future sponsor title").is_postseason
    assert feeds.FEEDS[league][1](2027) == []


def test_tennis_ignores_nested_matches_and_deduplicates_returned_tournament_identities(monkeypatch, calendars):
    rows = calendars["feeds"]["tennis/atp/2026"]["events"]
    row = next(event for event in rows if event.get("groupings"))
    monkeypatch.setattr(feeds, "get_json", lambda _: {"events": [row, row]})
    events = feeds.FEEDS["ATP"][1](2026)
    assert len(events) == 1
    assert events[0].event_id == f"espn-atp-{row['id']}"
    assert not events[0].participants


@pytest.mark.parametrize("league,count", [("DP_WORLD_TOUR", 34), ("LIV_GOLF", 12)])
def test_new_golf_tours_keep_all_source_tournaments_and_spans_without_duplicate_pga_majors(calendars, league, count):
    events = feeds.FEEDS[league][1](2026)
    assert len(events) == len({event.event_id for event in events}) == count
    assert all(event.start_time_utc is None and event.end_calendar_date > event.calendar_date for event in events)
    assert all(event.source_url.startswith("https://www.espn.com/golf/leaderboard?") for event in events)
    assert not {event.title for event in events} & feeds.GOLF_MAJORS["PGA_TOUR"]
    assert all(event.facts_checked_date and event.facts_source_url for event in events)


def test_all_rugby_competitions_use_the_same_source_backed_team_game_parser(calendars):
    for league, (slug, _) in feeds.RUGBY_LEAGUES.items():
        for year in (2025, 2026, 2027):
            original = calendars["feeds"][f"rugby/{slug}/{year}"]["events"]
            events = feeds.FEEDS[league][1](year)
            assert len(events) == sum(bool(row) for row in original)
            assert len({event.event_id for event in events}) == len(events)
            for event in events:
                assert event.sport == "rugby" and event.event_type == "game"
                assert event.source == "espn" and event.source_url.startswith("https://www.espn.com/rugby/")
                assert event.home_participant and event.away_participant
                assert event.home_participant.participant_id and event.away_participant.short_name
                assert event.facts_checked_date and f"rugby/{slug}/scoreboard?dates={year}" in event.facts_source_url
                assert event.calendar_date.startswith(str(year))
                assert all(participant.record is None for participant in event.participants)


def test_rugby_final_scores_are_published_but_tbd_clocks_keep_the_source_date(calendars):
    (final,) = feeds.FEEDS["SIX_NATIONS"][1](2026)
    assert final.start_time_utc == "2026-02-05T20:10:00Z"
    assert final.status == "finished"
    assert (final.home_participant.name, final.home_participant.final_score) == ("France", 36)
    assert (final.away_participant.name, final.away_participant.final_score) == ("Ireland", 14)
    top14 = feeds.FEEDS["TOP_14"][1](2027)[0]
    assert top14.start_time_utc is None
    assert top14.calendar_date == "2027-01-02"
    assert all(participant.final_score is None for participant in top14.participants)


def test_rugby_undecided_opponents_use_shared_appointments_without_losing_known_facts(calendars, monkeypatch):
    row = copy.deepcopy(calendars["feeds"]["rugby/164205/2027"]["events"][0])
    competition = row["competitions"][0]
    unknown = next(team for team in competition["competitors"] if team["homeAway"] == "away")
    unknown["team"]["displayName"] = " TBD "
    row["name"] = "Australia vs TBD"
    competition["notes"] = [{"type": "event", "headline": "Quarterfinal"}]
    monkeypatch.setattr(feeds, "get_json", lambda _: {"events": [row]})
    (partial,) = feeds.FEEDS["RUGBY_WORLD_CUP"][1](2027)
    assert partial.title == "Quarterfinal · Australia"
    assert partial.round_or_stage == "Quarterfinal"
    assert partial.home_participant.name == "Australia" and partial.away_participant is None
    assert len(partial.participants) == 1
    assert partial.calendar_date == "2027-10-01" and partial.start_time_utc == "2027-10-01T10:45:00Z"
    assert partial.source_url == row["links"][0]["href"]

    for team in competition["competitors"]:
        team["team"]["displayName"] = "TBA"
    row["name"] = "TBA vs TBA"
    competition["notes"] = []
    (appointment,) = feeds.FEEDS["RUGBY_WORLD_CUP"][1](2027)
    assert appointment.title == "Rugby World Cup"
    assert not appointment.participants and not appointment.home_participant and not appointment.away_participant
    assert appointment.calendar_date == partial.calendar_date and appointment.start_time_utc == partial.start_time_utc
    assert appointment.facts_source_url == partial.facts_source_url and appointment.facts_checked_date


def test_new_sports_publish_with_existing_validation_and_espn_license(calendars, monkeypatch, tmp_path):
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    selected = {
        league: feeds.FEEDS[league] for league in ["ATP", "WTA", "DP_WORLD_TOUR", "LIV_GOLF", *feeds.RUGBY_LEAGUES]
    }
    path = refresh_open_schedules(2026, tmp_path, ROOT / "data/reviewed", feeds=selected)
    bundle = json.loads(path.read_text())
    assert len({event["event_id"] for event in bundle["events"]}) == len(bundle["events"])
    assert {"tennis", "rugby", "golf"} <= {event["sport"] for event in bundle["events"]}
    assert "No license granted" in bundle["data_licenses"]["espn"]
    assert all(name in bundle["coverage"] for name in ["ATP", "WTA", "DP World Tour", "LIV Golf", "Six Nations"])
