"""Actual collectors skip only proven request units and retain source boundaries."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds
from kickoff.incremental import RefreshPlan
from kickoff.refresh_state import Baseline, SourceUnit
from kickoff.source_units import unit_key
from kickoff.web import _event_payload
from kickoff.weightlifting_startlists import StartListLoader
from tests.test_feeds import espn_game
from tests.test_weightlifting_startlists import event as lifting_event
from tests.test_weightlifting_startlists import setup_catalog

NOW = datetime(2027, 11, 4, tzinfo=timezone.utc)


def published_game(identity, league, sport, day="2026-05-01"):
    event = feeds.make_event(
        source="espn",
        league=league,
        sport=sport,
        upstream_id=identity,
        season="2026",
        title="Away at Home",
        utc=f"{day}T15:00Z",
        day=day,
        home="Home",
        away="Away",
        status="finished",
        facts_source_url="https://example.test/old-source",
    )
    event.facts_checked_date = "2026-11-03"
    for p, score in zip(event.participants, [2, 1], strict=True):
        p.final_score = score
    return _event_payload(event)


def proven(url, ids=(), children=(), end="2026-05-02"):
    return SourceUnit(
        unit_key(url), url, "2026-11-03T12:00:00+00:00", tuple(ids), {}, True, True, tuple(children), "2026-01-01", end
    )


def plan_for(events=(), units=()):
    baseline = Baseline(
        manifest={"available_seasons": [2026]},
        bundles={"2026-fixture.json": {"season": 2026, "events": list(events)}},
        units={u.key: u for u in units},
        frozen_ids=frozenset(e["event_id"] for e in events),
    )
    return RefreshPlan(baseline, NOW)


def finished(identity, utc):
    row = espn_game(identity, utc, "Home", "Away", status="STATUS_FINAL")
    for side, score in zip(row["competitions"][0]["competitors"], [2, 1], strict=True):
        side["score"] = str(score)
    return row


def test_college_reuse_is_group_specific_and_keeps_prior_fact_dates(monkeypatch):
    url = f"{feeds.ESPN}/football/college-football/scoreboard?dates=20260501&limit=200&groups=80"
    row = published_game("old", "COLLEGE_FOOTBALL", "football")
    row["tags"].append("fbs")
    plan = plan_for([row], [proven(url, [row["event_id"]])])
    calls = []

    def read(url, **_):
        calls.append(url)
        return {"events": []}

    monkeypatch.setattr(feeds, "get_json", read)
    events = feeds.espn_team_events(2026, "COLLEGE_FOOTBALL", plan=plan)
    assert len(events) == 1 and _event_payload(events[0]) == row
    assert url not in calls
    assert url.replace("groups=80", "groups=81") in calls
    assert plan.baseline.units[unit_key(url)].observed_at == "2026-11-03T12:00:00+00:00"


def test_saturation_records_every_child_before_historical_parent_can_close(monkeypatch):
    path, sport, groups, _ = feeds.TEAM_LEAGUES["MLS"]
    monkeypatch.setitem(feeds.TEAM_LEAGUES, "MLS", (path, sport, groups, 2))
    rows = [finished("one", "2026-01-02T15:00Z"), finished("two", "2026-02-02T15:00Z")]
    calls = []

    def read(url, **_):
        prefix = parse_qs(urlsplit(url).query)["dates"][0]
        calls.append(prefix)
        return {
            "events": rows
            if prefix == "2026"
            else [rows[0]]
            if prefix == "202601"
            else [rows[1]]
            if prefix == "202602"
            else []
        }

    monkeypatch.setattr(feeds, "get_json", read)
    plan = plan_for()
    events = feeds.espn_team_events(2026, "MLS", plan=plan)
    key = unit_key(f"{feeds.ESPN}/{path}/scoreboard?dates=2026&limit=2")
    parent = plan.current[key]
    assert len(events) == 2 and len(parent.children) == 12
    assert parent.complete and parent.closed
    assert all(child in plan.current and plan.current[child].complete for child in parent.children)
    assert all(f"2026{month:02}" in calls for month in range(1, 13))


def test_failed_saturation_child_never_makes_parent_authoritative(monkeypatch):
    path, sport, groups, _ = feeds.TEAM_LEAGUES["MLS"]
    monkeypatch.setitem(feeds.TEAM_LEAGUES, "MLS", (path, sport, groups, 2))
    rows = [finished("one", "2026-01-02T15:00Z"), finished("two", "2026-02-02T15:00Z")]

    def read(url, **_):
        prefix = parse_qs(urlsplit(url).query)["dates"][0]
        if prefix == "202602":
            raise OSError("Unavailable required child")
        return {"events": rows if prefix == "2026" else []}

    monkeypatch.setattr(feeds, "get_json", read)
    plan = plan_for()
    with pytest.raises(OSError):
        feeds.espn_team_events(2026, "MLS", plan=plan)
    parent = plan.current[unit_key(f"{feeds.ESPN}/{path}/scoreboard?dates=2026&limit=2")]
    assert not parent.complete and not parent.closed


def test_ufl_reuses_entire_proven_week_graph_without_losing_supplemental_game(monkeypatch):
    path = feeds.TEAM_LEAGUES["UFL"][0]
    annual = f"{feeds.ESPN}/{path}/scoreboard?dates=2026&limit=1000"
    weeks = [annual + "&seasontype=2&week=1", annual + "&seasontype=3&week=1"]
    events = [published_game(str(i), "UFL", "football") for i in range(3)]
    ids = [e["event_id"] for e in events]
    units = [
        proven(weeks[0], ids[:2]),
        proven(weeks[1], ids[2:]),
        proven(annual, ids[:2], [unit_key(w) for w in weeks]),
    ]
    plan = plan_for(events, units)
    calls = []

    def read(url, **_):
        calls.append(url)
        return {"events": []}

    monkeypatch.setattr(feeds, "get_json", read)
    actual = feeds.espn_team_events(2026, "UFL", plan=plan)
    assert {e.event_id for e in actual} == set(ids)
    assert annual not in calls and not set(weeks) & set(calls)
    assert {unit_key(annual), *(unit_key(w) for w in weeks)} <= plan._skipped


def test_nhl_reused_week_keeps_actual_next_cursor(monkeypatch):
    url = "https://api-web.nhle.com/v1/schedule/2026-01-01"
    row = published_game("old", "NHL", "hockey", "2026-01-01")
    row["source"] = "nhl"
    row["event_id"] = "nhl-nhl-old"
    plan = plan_for([row], [proven(url, [row["event_id"]], end="2026-01-08")])
    calls = []

    def read(url, **_):
        calls.append(url)
        return {"gameWeek": [{"date": "2026-01-08", "games": []}], "nextStartDate": "2027-01-01"}

    monkeypatch.setattr(feeds, "get_json", read)
    (actual,) = feeds.nhl_events(2026, plan=plan)
    assert _event_payload(actual) == row
    assert calls == ["https://api-web.nhle.com/v1/schedule/2026-01-08"]


def test_wholly_frozen_start_list_book_has_no_source_read_but_active_book_still_loads(monkeypatch, tmp_path):
    setup_catalog(monkeypatch, tmp_path)
    item = lifting_event("session")
    assert StartListLoader().enrich([item], tmp_path, 2026, skip_ids={"session"}) == ([], [])
    assert item.participants == []
    sources, _ = StartListLoader().enrich([item], tmp_path, 2026, skip_ids={"different-session"})
    assert sources and len(item.participants) == 2


def pending(url, identity=None, reason="STATUS_POSTPONED"):
    return SourceUnit(
        unit_key(url),
        url,
        "2026-01-01T12:00:00+00:00",
        (identity,) if identity else (),
        {identity: reason} if identity else {},
        True,
        False,
    )


def test_nhl_changed_navigation_requeries_prior_postponed_week_with_actual_parser(monkeypatch):
    old = "https://api-web.nhle.com/v1/schedule/2026-01-08"
    plan = plan_for(units=[pending(old, "nhl-nhl-123", "PPD")])
    calls = []

    def read(url, **_):
        calls.append(url)
        day = url.rsplit("/", 1)[-1]
        games = (
            [
                {
                    "id": 123,
                    "gameType": 2,
                    "gameState": "OFF",
                    "gameScheduleState": "OK",
                    "startTimeUTC": "2026-01-08T15:00Z",
                    "season": 20252026,
                    "homeTeam": {"commonName": {"default": "Home"}, "score": 2},
                    "awayTeam": {"commonName": {"default": "Away"}, "score": 1},
                }
            ]
            if url == old
            else []
        )
        return {
            "gameWeek": [{"date": day, "games": games}],
            "nextStartDate": "2026-01-15" if day == "2026-01-01" else "2027-01-01",
        }

    monkeypatch.setattr(feeds, "get_json", read)
    (event,) = feeds.nhl_events(2026, plan=plan)
    assert calls == [old.replace("01-08", "01-01"), old.replace("01-08", "01-15"), old]
    assert event.event_id == "nhl-nhl-123" and event.status == "finished"
    assert [p.final_score for p in event.participants] == [2, 1]
    assert plan.current[unit_key(old)].unresolved == {}
    assert plan.current[unit_key(old)].observed_at != plan.baseline.units[unit_key(old)].observed_at


@pytest.mark.parametrize(
    "league,query", [("MLS", "dates=202605&limit=1000"), ("UFL", "dates=2026&limit=1000&seasontype=2&week=7")]
)
def test_espn_old_month_or_week_requeried_after_current_discovery_omits_it(monkeypatch, league, query):
    path = feeds.TEAM_LEAGUES[league][0]
    old = f"{feeds.ESPN}/{path}/scoreboard?{query}"
    identity = f"espn-{league.lower()}-recovered"
    plan = plan_for(units=[pending(old, identity)])
    calls = []
    row = finished("recovered", "2026-05-01T15:00Z")
    row["competitions"][0]["competitors"][0].update(winner=True, advance=True, aggregateScore="3", shootoutScore="2")

    def read(url, **_):
        calls.append(url)
        return {"events": [row] if url == old else []}

    monkeypatch.setattr(feeds, "get_json", read)
    (event,) = feeds.espn_team_events(2026, league, plan=plan)
    assert calls.count(old) == 1 and event.event_id == identity
    assert event.status == "finished" and plan.current[unit_key(old)].unresolved == {}
    first = event.participants[0]
    assert first.final_score == 2


def test_same_id_in_current_parent_does_not_prove_old_child_has_no_added_game(monkeypatch):
    path = feeds.TEAM_LEAGUES["MLS"][0]
    old = f"{feeds.ESPN}/{path}/scoreboard?dates=202605&limit=1000"
    before = pending(old, "espn-mls-same")
    plan = plan_for(units=[before])
    calls = []

    def read(url, **_):
        calls.append(url)
        if url == old:
            return {"events": [finished("same", "2026-05-01T15:00Z"), finished("added", "2026-05-02T15:00Z")]}
        query = parse_qs(urlsplit(url).query)
        return {"events": [finished("same", "2026-05-01T15:00Z")] if query["dates"] == ["2026"] else []}

    monkeypatch.setattr(feeds, "get_json", read)
    events = feeds.espn_team_events(2026, "MLS", plan=plan)
    assert {event.event_id for event in events} == {"espn-mls-same", "espn-mls-added"}
    assert calls.count(old) == 1 and plan.units[before.key].unresolved == {}
    assert plan.units[before.key].observed_at != before.observed_at


def test_empty_open_old_month_is_requeried_but_frozen_known_members_are_not(monkeypatch):
    path = feeds.TEAM_LEAGUES["MLS"][0]
    empty = f"{feeds.ESPN}/{path}/scoreboard?dates=202604&limit=1000"
    frozen = f"{feeds.ESPN}/{path}/scoreboard?dates=202605&limit=1000"
    row = published_game("old", "MLS", "soccer")
    plan = plan_for([row], [pending(empty), proven(frozen, [row["event_id"]])])
    calls = []
    monkeypatch.setattr(feeds, "get_json", lambda url, **_: calls.append(url) or {"events": []})
    feeds.espn_team_events(2026, "MLS", plan=plan)
    assert empty in calls and frozen not in calls


def test_nba_removed_team_schedule_is_requeried_through_existing_team_parser(monkeypatch):
    old = f"{feeds.ESPN}/basketball/nba/teams/retired/schedule?season=2026&seasontype=3"
    plan = plan_for(units=[pending(old, "espn-nba-recovered")])
    calls = []

    def read(url, **_):
        calls.append(url)
        if url.endswith("/teams"):
            return {"sports": [{"leagues": [{"teams": [{"team": {"id": str(i)}} for i in range(30)]}]}]}
        return {"events": [finished("recovered", "2026-05-01T15:00Z")] if url == old else []}

    monkeypatch.setattr(feeds, "get_json", read)
    (event,) = feeds.nba_events(2026, plan=plan)
    assert calls.count(old) == 1 and event.event_id == "espn-nba-recovered"
    assert event.competition_phase == "postseason" and plan.current[unit_key(old)].unresolved == {}


def test_ucl_vanished_discovery_day_still_requeries_prior_unresolved_scoreboard(monkeypatch):
    old = f"{feeds.ESPN}/soccer/uefa.champions/scoreboard?dates=20260501"
    plan = plan_for(units=[pending(old, "espn-uefa_champions_league-recovered")])
    calls = []

    def read(url, **_):
        calls.append(url)
        return [] if "openligadb" in url else {"events": [finished("recovered", "2026-05-01T15:00Z")]}

    monkeypatch.setattr(feeds, "get_json", read)
    (event,) = feeds.ucl_events(2026, plan=plan)
    assert calls.count(old) == 1 and event.event_id == "espn-uefa_champions_league-recovered"
    assert plan.current[unit_key(old)].unresolved == {}


@pytest.mark.parametrize("kind", ["mlb", "espn"])
def test_prior_annual_unresolved_source_survives_rolling_calendar_year_change(monkeypatch, kind):
    old = (
        "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2025&gameType=R,F,D,L,W&hydrate=venue(location)"
        if kind == "mlb"
        else f"{feeds.ESPN}/rugby/180659/scoreboard?dates=2025&limit=500"
    )
    plan = plan_for(units=[pending(old, f"{kind}-old", "missing_result")])
    calls = []

    def read(url, **_):
        calls.append(url)
        return {"dates": []} if kind == "mlb" else {"events": []}

    monkeypatch.setattr(feeds, "get_json", read)
    if kind == "mlb":
        assert feeds.mlb_events(2026, plan=plan) == []
    else:
        fetch = feeds.espn_season_feed("rugby/180659", "SIX_NATIONS", "rugby", "game", "https://example.com/")
        assert fetch(2026, plan=plan) == []
    assert calls.count(old) == 1 and unit_key(old) in plan.current


def test_replayed_nhl_week_follows_its_new_source_cursor_until_current_walk_rejoins(monkeypatch):
    old = "https://api-web.nhle.com/v1/schedule/2026-01-08"
    plan = plan_for(units=[pending(old, "nhl-nhl-123", "PPD")])
    calls = []
    following = {
        "2026-01-01": "2026-01-15",
        "2026-01-08": "2026-01-09",
        "2026-01-09": "2026-01-15",
        "2026-01-15": "2027-01-01",
    }

    def read(url, **_):
        calls.append(url.rsplit("/", 1)[-1])
        day = calls[-1]
        return {"gameWeek": [{"date": day, "games": []}], "nextStartDate": following[day]}

    monkeypatch.setattr(feeds, "get_json", read)
    assert feeds.nhl_events(2026, plan=plan) == []
    assert calls == ["2026-01-01", "2026-01-15", "2026-01-08", "2026-01-09"]


def test_open_old_window_with_all_known_members_frozen_still_discovers_new_game(monkeypatch):
    path = feeds.TEAM_LEAGUES["MLS"][0]
    old = f"{feeds.ESPN}/{path}/scoreboard?dates=202605&limit=1000"
    row = published_game("old", "MLS", "soccer")
    plan = plan_for([row], [pending(old, row["event_id"], "missing_result")])
    calls = []

    def read(url, **_):
        calls.append(url)
        return {"events": [finished("added-later", "2026-05-02T15:00Z")] if url == old else []}

    monkeypatch.setattr(feeds, "get_json", read)
    events = feeds.espn_team_events(2026, "MLS", plan=plan)
    assert calls.count(old) == 1
    assert {event.event_id for event in events} == {"espn-mls-added-later"}
    assert plan.current[unit_key(old)].event_ids == ("espn-mls-added-later",)


@pytest.mark.parametrize("kind", ["espn", "mlb"])
def test_recovered_old_annual_game_keeps_its_new_calendar_year_and_original_source_season(monkeypatch, kind):
    old = (
        f"{feeds.ESPN}/rugby/180659/scoreboard?dates=2025&limit=500"
        if kind == "espn"
        else "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2025&gameType=R,F,D,L,W&hydrate=venue(location)"
    )
    identity = "espn-six_nations-recovered" if kind == "espn" else "mlb-mlb-123"
    plan = plan_for(units=[pending(old, identity)])
    calls = []
    rugby = finished("recovered", "2026-05-01T15:00Z")
    rugby["season"] = {"year": 2025}
    baseball = {
        "gamePk": 123,
        "gameDate": "2026-05-01T15:00Z",
        "officialDate": "2026-05-01",
        "season": "2025",
        "gameType": "R",
        "status": {"detailedState": "Final", "abstractGameState": "Final"},
        "teams": {
            "home": {"team": {"name": "Home", "id": 1}, "score": 2, "isWinner": True},
            "away": {"team": {"name": "Away", "id": 2}, "score": 1, "isWinner": False},
        },
    }

    def read(url, **_):
        calls.append(url)
        if kind == "espn":
            return {"events": [rugby] if url == old else []}
        return {"dates": [{"games": [baseball]}] if url == old else []}

    monkeypatch.setattr(feeds, "get_json", read)
    if kind == "espn":
        fetch = feeds.espn_season_feed("rugby/180659", "SIX_NATIONS", "rugby", "game", "https://example.com/")
        (event,) = fetch(2026, plan=plan)
    else:
        (event,) = feeds.mlb_events(2026, plan=plan)
    assert event.event_id == identity and event.calendar_date == "2026-05-01"
    assert event.season == "2025" and event.status == "finished"
    assert event.facts_source_url == old
    assert [p.final_score for p in event.participants] == [2, 1]
    assert len(calls) == 2 and calls.count(old) == 1
    assert plan.current[unit_key(old)].event_ids == (identity,)
    assert plan.current[unit_key(old)].unresolved == {}


def test_future_nba_postseason_waits_for_its_calendar_year_instead_of_duplicate_early_fetch(monkeypatch):
    old = f"{feeds.ESPN}/basketball/nba/teams/1/schedule?season=2026&seasontype=3"
    plan = plan_for(units=[pending(old, "espn-nba-future")])
    calls = []

    def read(url, **_):
        calls.append(url)
        if url.endswith("/teams"):
            return {"sports": [{"leagues": [{"teams": [{"team": {"id": str(i)}} for i in range(30)]}]}]}
        return {"events": []}

    monkeypatch.setattr(feeds, "get_json", read)
    feeds.nba_events(2025, plan=plan)
    assert old not in calls
    feeds.nba_events(2026, plan=plan)
    assert calls.count(old) == 1
