from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff.refresh_state import unit_is_frozen
from kickoff.source_units import espn_unit, mlb_unit, nhl_unit, unit_key

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
ESPN = "https://site.api.espn.com/apis/site/v2/sports"


def espn_game(identity="1", status="STATUS_FINAL", scores=True):
    competitors = [
        {"team": {"displayName": "First"}, "score": "0"},
        {"team": {"displayName": "Second"}, "score": {"displayValue": "2"}},
    ]
    if not scores:
        del competitors[0]["score"]
    return {
        "id": identity,
        "status": {"type": {"name": status, "completed": status == "STATUS_FINAL"}},
        "competitions": [{"competitors": competitors}],
    }


def test_canonical_keys_preserve_queries_filters_and_duplicate_values_without_fragments():
    assert unit_key("http://EXAMPLE.org/a?week=1&dates=2025&groups=81&groups=80#fragment") == (
        "https://example.org/a?dates=2025&groups=80&groups=81&week=1"
    )
    assert unit_key("https://example.org/a?a=&b=2") == "https://example.org/a?a=&b=2"
    with pytest.raises(ValueError):
        unit_key("https://user:password@example.org/private")


@pytest.mark.parametrize(
    "query,start,end",
    [
        ("2024", "2024-01-01", "2025-01-01"),
        ("202402", "2024-02-01", "2024-03-01"),
        ("20240229", "2024-02-29", "2024-03-01"),
    ],
)
def test_espn_civil_bounds_are_complete_intervals_with_exclusive_end(query, start, end):
    observed = espn_unit(
        f"{ESPN}/soccer/usa.1/scoreboard?dates={query}&limit=1000", {"events": [espn_game()]}, "MLS", NOW
    )
    assert (observed.start, observed.end) == (start, end)
    assert observed.complete and observed.closed
    assert observed.event_ids == ("espn-mls-1",)
    assert observed.unresolved == {}
    assert observed.observed_at == NOW.isoformat()


def test_all_dropped_undecided_and_missing_result_ids_survive_before_public_filters():
    rows = [
        espn_game("1"),
        espn_game("2", "STATUS_POSTPONED"),
        espn_game("3", "STATUS_CANCELED"),
        espn_game("4", scores=False),
        espn_game("5", "STATUS_SCHEDULED"),
    ]
    rows.append(espn_game("6"))
    rows[-1]["competitions"][0]["competitors"][0]["team"]["displayName"] = "TBA"
    observed = espn_unit(
        f"{ESPN}/football/college-football/scoreboard?dates=20250101&limit=200&groups=80",
        {"events": rows},
        "COLLEGE_FOOTBALL",
        NOW,
    )
    assert len(observed.event_ids) == 6
    assert observed.unresolved == {
        "espn-college_football-2": "STATUS_POSTPONED",
        "espn-college_football-3": "STATUS_CANCELED",
        "espn-college_football-4": "result_unconfirmed",
        "espn-college_football-5": "STATUS_SCHEDULED",
        "espn-college_football-6": "result_unconfirmed",
    }
    assert not unit_is_frozen(observed.key, observed.event_ids, {observed.key: observed})


def test_unknown_finished_individual_result_is_not_promoted_from_status_or_score_alone():
    event = espn_game()
    event["competitions"][0]["competitors"] = [{"athlete": {"displayName": "Athlete"}, "score": "65"}]
    observed = espn_unit(f"{ESPN}/golf/pga/scoreboard?dates=2025&limit=500", {"events": [event]}, "PGA_TOUR", NOW)
    assert observed.unresolved == {"espn-pga_tour-1": "result_unconfirmed"}


def test_college_group_requests_stay_distinct_and_only_reviewed_empty_slot_is_ignored():
    url = f"{ESPN}/football/college-football/scoreboard?dates=20250101&limit=200&groups="
    payload = {"events": [{}, espn_game()]}
    first, second = [espn_unit(url + str(group), payload, "COLLEGE_FOOTBALL", NOW) for group in [80, 81]]
    assert first.key != second.key
    assert first.event_ids == second.event_ids == ("espn-college_football-1",)
    with pytest.raises(ValueError, match="Missing source id"):
        espn_unit(url + "80", payload, "NFL", NOW)


def test_saturated_windows_stay_incomplete_until_exact_children_are_attached():
    observed = espn_unit(
        f"{ESPN}/soccer/usa.1/scoreboard?dates=2025&limit=2", {"events": [espn_game("1"), espn_game("2")]}, "MLS", NOW
    )
    assert not observed.complete and not observed.closed
    assert observed.children == ()
    assert not unit_is_frozen(observed.key, observed.event_ids, {observed.key: observed})


def test_empty_future_current_and_unbounded_units_never_close_but_historical_can():
    for value, expected in [
        ("2027", False),
        ("2026", False),
        ("2025", True),
        ("20261102", False),
        ("20261101", True),
        ("unknown", False),
    ]:
        observed = espn_unit(f"{ESPN}/soccer/usa.1/scoreboard?dates={value}", {"events": []}, "MLS", NOW)
        assert observed.closed is expected
        assert unit_is_frozen(observed.key, (), {observed.key: observed}) is expected
    absent = espn_unit(f"{ESPN}/football/nfl/scoreboard?dates=2025", None, "NFL", NOW)
    assert not absent.complete and not absent.closed


def calendar(year=2025):
    return {
        "season": {"year": year},
        "leagues": [
            {
                "season": {"year": year},
                "calendar": [
                    {
                        "value": "2",
                        "entries": [
                            {"value": "1", "startDate": "2025-03-01T08:00Z", "endDate": "2025-03-08T07:59Z"},
                            {"value": "2", "startDate": "2025-03-08T08:00Z", "endDate": "2025-03-15T07:59Z"},
                        ],
                    },
                    {
                        "value": "3",
                        "entries": [{"value": "1", "startDate": "2025-06-01T08:00Z", "endDate": "2025-06-08T07:59Z"}],
                    },
                ],
            }
        ],
        "events": [espn_game()],
    }


def test_week_bounds_need_exact_actual_year_phase_and_week_and_are_not_invented():
    url = f"{ESPN}/football/nfl/scoreboard?dates=2025&seasontype=2&week=2"
    observed = espn_unit(url, calendar(), "NFL", NOW)
    assert (observed.start, observed.end) == ("2025-03-08T08:00Z", "2025-03-15T07:59Z")
    assert observed.closed
    wrong_year = espn_unit(url.replace("dates=2025", "dates=2027"), calendar(), "NFL", NOW)
    assert wrong_year.start is None and wrong_year.end is None and not wrong_year.closed
    unknown_week = espn_unit(url.replace("week=2", "week=99"), calendar(), "NFL", NOW)
    assert unknown_week.start is None and not unknown_week.closed


def test_ufl_annual_discovery_requires_every_real_regular_and_postseason_week():
    url = f"{ESPN}/football/ufl/scoreboard?dates=2025&limit=1000"
    annual = espn_unit(url, calendar(), "UFL", NOW)
    assert len(annual.children) == 3
    assert {
        (parse_qs(urlsplit(c).query)["seasontype"][0], parse_qs(urlsplit(c).query)["week"][0]) for c in annual.children
    } == {("2", "1"), ("2", "2"), ("3", "1")}
    assert not annual.complete and not annual.closed
    children = {key: espn_unit(key, calendar(), "UFL", NOW) for key in annual.children}
    finished_annual = replace(annual, complete=True, closed=True)
    units = {annual.key: finished_annual, **children}
    assert unit_is_frozen(annual.key, annual.event_ids, units)
    del units[annual.children[-1]]
    assert not unit_is_frozen(annual.key, annual.event_ids, units)
    with pytest.raises(ValueError, match="Missing UFL weekly"):
        espn_unit(url, {"events": [espn_game()]}, "UFL", NOW)


def nba_payload(year=2025, current=2027, **changes):
    return {
        "requestedSeason": {"year": year, "type": 2},
        "season": {"year": current},
        "events": [espn_game()],
        **changes,
    }


def test_nba_shared_games_belong_to_both_team_units_and_proven_past_season_can_close():
    url = f"{ESPN}/basketball/nba/teams/1/schedule?season=2025&seasontype=2"
    first = espn_unit(url, nba_payload(), "NBA", NOW)
    second = espn_unit(url.replace("teams/1", "teams/2"), nba_payload(), "NBA", NOW)
    assert first.key != second.key and first.event_ids == second.event_ids == ("espn-nba-1",)
    assert first.complete and first.closed and first.start is None and first.end is None
    assert unit_is_frozen(first.key, first.event_ids, {first.key: first})


@pytest.mark.parametrize(
    "payload",
    [
        nba_payload(year=2026),
        nba_payload(current=2025),
        nba_payload(events=[]),
        nba_payload(events=[espn_game(status="STATUS_SCHEDULED")]),
        nba_payload(events=[espn_game(scores=False)]),
        nba_payload(pagination={"page": 1, "pageCount": 2}),
    ],
)
def test_nba_unknown_current_incomplete_or_nonfinal_season_cannot_close(payload):
    observed = espn_unit(f"{ESPN}/basketball/nba/teams/1/schedule?season=2025&seasontype=2", payload, "NBA", NOW)
    assert not observed.closed


def mlb_game(identity=1, detailed="Final"):
    return {
        "gamePk": identity,
        "status": {"detailedState": detailed},
        "teams": {"home": {"team": {"name": "First"}, "score": 0}, "away": {"team": {"name": "Second"}, "score": 1}},
    }


def test_mlb_membership_includes_dropped_and_undecided_and_missing_scores():
    games = [mlb_game(), mlb_game(2, "Postponed"), mlb_game(3, "Cancelled"), mlb_game(4), mlb_game(5)]
    games[3]["teams"]["home"]["team"]["name"] = "NL Lower Seed"
    del games[4]["teams"]["away"]["score"]
    observed = mlb_unit(
        "https://statsapi.mlb.com/api/v1/schedule?season=2025",
        {"dates": [{"games": games, "totalGames": 5}], "totalGames": 5},
        NOW,
    )
    assert len(observed.event_ids) == 5 and observed.complete and observed.closed
    assert observed.unresolved == {
        "mlb-mlb-2": "Postponed",
        "mlb-mlb-3": "Cancelled",
        "mlb-mlb-4": "undecided_opponents",
        "mlb-mlb-5": "result_unconfirmed",
    }
    assert (observed.start, observed.end) == ("2025-01-01", "2026-01-01")


def test_mlb_explicit_query_end_is_inclusive_and_count_mismatch_is_incomplete():
    observed = mlb_unit(
        "https://statsapi.mlb.com/api/v1/schedule?startDate=2025-05-01&endDate=2025-05-31", {"dates": []}, NOW
    )
    assert (observed.start, observed.end) == ("2025-05-01", "2025-06-01")
    assert observed.closed
    partial = mlb_unit("https://statsapi.mlb.com/api/v1/schedule?season=2025", {"dates": [], "totalGames": 1}, NOW)
    assert not partial.complete and not partial.closed


def nhl_game(identity=1, **changes):
    return {
        "id": identity,
        "gameType": 2,
        "gameScheduleState": "OK",
        "gameState": "OFF",
        "homeTeam": {"commonName": {"default": "First"}, "score": 0},
        "awayTeam": {"commonName": {"default": "Second"}, "score": 2},
        **changes,
    }


def test_nhl_cursor_is_exclusive_actual_navigation_not_a_future_child_dependency():
    payload = {
        "gameWeek": [{"date": "2025-06-25", "games": [nhl_game()], "numberOfGames": 1}],
        "nextStartDate": "2025-09-20",
        "numberOfGames": 1,
    }
    observed = nhl_unit("https://api-web.nhle.com/v1/schedule/2025-06-25", payload, NOW)
    assert (observed.start, observed.end) == ("2025-06-25", "2025-09-20")
    assert observed.complete and observed.closed and observed.children == ()
    assert unit_is_frozen(observed.key, observed.event_ids, {observed.key: observed})
    no_navigation = nhl_unit(observed.source_url, {"gameWeek": payload["gameWeek"]}, NOW)
    assert no_navigation.end == "2025-06-26"


def test_nhl_preserves_withheld_preseason_and_unfinished_ids_and_future_empty_is_open():
    games = [
        nhl_game(),
        nhl_game(2, gameType=1),
        nhl_game(3, gameScheduleState="PPD"),
        nhl_game(4, gameState="FUT"),
        nhl_game(5, awayTeam={"abbrev": "TBD", "score": 2}),
    ]
    observed = nhl_unit(
        "https://api-web.nhle.com/v1/schedule/2025-01-01", {"gameWeek": [{"date": "2025-01-01", "games": games}]}, NOW
    )
    assert len(observed.event_ids) == 5
    assert observed.unresolved == {
        "nhl-nhl-2": "outside_published_game_type",
        "nhl-nhl-3": "PPD",
        "nhl-nhl-4": "FUT",
        "nhl-nhl-5": "undecided_opponents",
    }
    future = nhl_unit(
        observed.source_url, {"gameWeek": [{"date": "2027-01-01", "games": []}], "nextStartDate": "2027-01-08"}, NOW
    )
    assert not future.closed


@pytest.mark.parametrize(
    "function,payload",
    [
        (espn_unit, {"events": {}}),
        (espn_unit, {"events": [1]}),
        (mlb_unit, {"dates": [{"games": None}]}),
        (nhl_unit, {"gameWeek": {}}),
    ],
)
def test_malformed_primary_source_arrays_fail(function, payload):
    with pytest.raises(ValueError):
        if function is espn_unit:
            function("https://example.org/schedule?dates=2025", payload, "NFL", NOW)
        else:
            function("https://example.org/schedule?season=2025", payload, NOW)


def test_ambiguous_dates_do_not_create_a_guessed_window():
    with pytest.raises(ValueError, match="Ambiguous dates"):
        espn_unit(f"{ESPN}/soccer/usa.1/scoreboard?dates=2025&dates=2026", {"events": []}, "MLS", NOW)


@pytest.mark.parametrize("league", ["LPGA_TOUR", "MAJOR_LEAGUE_RUGBY"])
def test_reviewed_annual_empty_placeholders_have_no_raw_game_identity(league):
    observed = espn_unit(
        f"{ESPN}/reviewed/scoreboard?dates=2025&limit=500",
        {"events": [{}, espn_game()]},
        league,
        NOW,
    )
    assert observed.event_ids == (f"espn-{league.lower()}-1",)
    assert observed.complete
