import json

import pytest

from kickoff import feeds
from kickoff.open_schedules import collect_feed_events, refresh_open_schedules
from kickoff.web import _event_payload
from tests.test_reviewed_schedules import ROOT, fake_open_read


def espn_game(event_id, utc, home, away, status="STATUS_SCHEDULED", time_valid=True, **extra):
    return {
        "id": event_id,
        "date": utc,
        "name": f"{away} at {home}",
        "status": {"type": {"name": status}},
        "season": {"year": 2026, "slug": extra.pop("slug", "regular-season")},
        "links": [{"href": f"https://www.espn.com/nfl/game/_/gameId/{event_id}"}],
        "competitions": [
            {
                "timeValid": time_valid,
                "venue": {"fullName": "Stadium"},
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": home}},
                    {"homeAway": "away", "team": {"displayName": away}},
                ],
            }
        ],
        **extra,
    }


def serve(monkeypatch, routes):
    def get_json(url, **_):
        for fragment, payload in routes.items():
            if fragment in url:
                return payload
        return None

    monkeypatch.setattr(feeds, "get_json", get_json)


def test_espn_games_use_eastern_dates_and_drop_canceled_or_tbd_clocks(monkeypatch):
    serve(
        monkeypatch,
        {
            "seasontype=2&week=1": {
                "events": [
                    espn_game("1", "2026-09-11T00:20Z", "Seattle Seahawks", "New England Patriots"),
                    espn_game("2", "2026-09-13T17:00Z", "Bears", "Lions", status="STATUS_POSTPONED"),
                ]
            },
            "seasontype=2&week=18": {
                "events": [espn_game("3", "2027-01-10T05:00Z", "Jets", "Bills", time_valid=False)]
            },
        },
    )
    events = {event.event_id: event for event in feeds.nfl_events(2026)}
    opener = events["espn-nfl-1"]
    assert opener.calendar_date == "2026-09-10"  # Thursday night in the US, Friday in UTC
    assert opener.start_time_utc == "2026-09-11T00:20:00Z"
    assert opener.home_participant.name == "Seattle Seahawks"
    assert opener.source_url.startswith("https://www.espn.com/")
    assert "espn-nfl-2" not in events  # postponed games are withheld until rescheduled
    assert "espn-nfl-3" not in events  # January 2027 belongs to the 2027 calendar


def test_week_18_placeholder_time_stays_date_only(monkeypatch):
    serve(
        monkeypatch,
        {
            "dates=2026&seasontype=2&week=18": {
                "events": [espn_game("3", "2027-01-10T05:00Z", "Jets", "Bills", time_valid=False)]
            }
        },
    )
    (event,) = feeds.nfl_events(2027)
    assert event.calendar_date == "2027-01-10"
    assert event.start_time_utc is None


def test_golf_spans_and_canceled_tournaments(monkeypatch):
    golf = {
        "events": [
            {
                "id": "9",
                "name": "The Sentry",
                "date": "2026-01-08T05:00Z",
                "endDate": "2026-01-11T05:00Z",
                "status": {"type": {"name": "STATUS_CANCELED"}},
                "competitions": [{}],
            },
            {
                "id": "10",
                "name": "Sony Open in Hawaii",
                "date": "2026-01-15T05:00Z",
                "endDate": "2026-01-18T05:00Z",
                "status": {"type": {"name": "STATUS_FINAL"}},
                "competitions": [{"timeValid": False}],
            },
        ]
    }
    serve(monkeypatch, {"golf/pga/scoreboard": golf})
    (event,) = feeds.FEEDS["PGA_TOUR"][1](2026)
    assert (event.calendar_date, event.end_calendar_date) == ("2026-01-15", "2026-01-18")
    assert event.start_time_utc is None
    assert event.event_type == "tournament"


def test_mlb_official_feed_skips_postponed_and_marks_postseason(monkeypatch):
    def game(pk, kind, state="Scheduled", tbd=False):
        return {
            "gamePk": pk,
            "gameDate": "2026-10-24T00:08:00Z",
            "officialDate": "2026-10-23",
            "gameType": kind,
            "season": "2026",
            "status": {"detailedState": state, "startTimeTBD": tbd},
            "teams": {"away": {"team": {"name": "Away"}}, "home": {"team": {"name": "Home"}}},
            "venue": {"name": "Park"},
        }

    serve(
        monkeypatch,
        {"statsapi.mlb.com": {"dates": [{"games": [game(1, "W"), game(2, "R", "Postponed"), game(3, "R", tbd=True)]}]}},
    )
    events = {event.event_id: event for event in feeds.mlb_events(2026)}
    assert set(events) == {"mlb-mlb-1", "mlb-mlb-3"}
    assert events["mlb-mlb-1"].competition_phase == "final"
    assert events["mlb-mlb-1"].calendar_date == "2026-10-23"
    assert events["mlb-mlb-3"].start_time_utc is None


def test_mlb_undecided_postseason_slots_name_the_series(monkeypatch):
    game = {
        "gamePk": 9,
        "gameDate": "2026-10-31T00:08:00Z",
        "officialDate": "2026-10-30",
        "gameType": "W",
        "seriesDescription": "World Series",
        "seriesGameNumber": 6,
        "gamesInSeries": 7,
        "ifNecessary": "Y",
        "status": {"detailedState": "Scheduled", "startTimeTBD": True},
        "teams": {
            "away": {"team": {"name": "Lower Seed League Champion"}},
            "home": {"team": {"name": "Higher Seed League Champion"}},
        },
    }
    serve(monkeypatch, {"statsapi.mlb.com": {"dates": [{"games": [game]}]}})
    (event,) = feeds.mlb_events(2026)
    assert event.title == "World Series · Game 6 · teams TBD"
    assert event.subtitle == "World Series · Game 6 of 7 · if necessary"
    assert event.home_participant is None and event.participants == []


def test_nhl_walks_weeks_and_skips_preseason(monkeypatch):
    calls = []

    def get_json(url, **_):
        calls.append(url)
        if url.endswith("2026-01-01"):
            game = {
                "id": 7,
                "gameType": 2,
                "season": 20252026,
                "startTimeUTC": "2026-01-02T00:00:00Z",
                "gameScheduleState": "OK",
                "venue": {"default": "Arena"},
                "awayTeam": {"placeName": {"default": "Boston"}, "commonName": {"default": "Bruins"}},
                "homeTeam": {"placeName": {"default": "New York"}, "commonName": {"default": "Rangers"}},
            }
            preseason = {**game, "id": 8, "gameType": 1}
            return {"gameWeek": [{"date": "2026-01-01", "games": [game, preseason]}], "nextStartDate": "2027-01-01"}
        return {"gameWeek": []}

    monkeypatch.setattr(feeds, "get_json", get_json)
    (event,) = feeds.nhl_events(2026)
    assert event.title == "Boston Bruins at New York Rangers"
    assert len(calls) == 1


def published(events):
    return {"events": [_event_payload(event) for event in events]}


def test_failed_or_shrunken_feed_keeps_previous_events():
    old = [
        feeds.make_event(
            source="espn",
            league="NBA",
            sport="basketball",
            upstream_id=i,
            season="2026",
            title=f"Game {i}",
            utc=None,
            day="2026-11-01",
        )
        for i in range(10)
    ]
    previous = published(old)

    def broken(_year):
        raise OSError("ESPN offline")

    warnings = []
    events, fed = collect_feed_events(2026, {"NBA": ("espn", broken)}, previous, warnings)
    assert [event.event_id for event in events] == [event.event_id for event in old]
    assert fed == {"NBA"} and "fetch failed" in warnings[0]

    warnings = []
    events, _ = collect_feed_events(2026, {"NBA": ("espn", lambda _year: old[:3])}, previous, warnings)
    assert len(events) == 10 and "down from 10" in warnings[0]

    warnings = []
    events, _ = collect_feed_events(2026, {"NBA": ("espn", lambda _year: old[:9])}, previous, warnings)
    assert len(events) == 9 and warnings == []


def test_feed_league_replaces_reviewed_selection_and_unchanged_refresh_skips_write(monkeypatch, tmp_path):
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    nfl = [
        feeds.make_event(
            source="espn",
            league="NFL",
            sport="football",
            upstream_id=1,
            season="2026",
            title="Patriots at Seahawks",
            utc="2026-09-11T00:20Z",
            day="2026-09-10",
        )
    ]
    output = tmp_path / "published"
    reviewed = tmp_path / "reviewed"
    reviewed.mkdir()
    registry = ROOT / "data/reviewed/2026-nfl-community.json"
    (reviewed / registry.name).write_text(registry.read_text())
    path = refresh_open_schedules(
        2026, tmp_path / "working", output, reviewed, feeds={"NFL": ("espn", lambda _year: nfl)}
    )
    bundle = json.loads(path.read_text())
    assert [e["event_id"] for e in bundle["events"] if e["league"] == "NFL"] == ["espn-nfl-1"]
    assert "Published schedules for NFL" in bundle["coverage"]
    assert any(source.get("kind") == "espn" for source in bundle["sources"])
    stamp = path.stat().st_mtime_ns
    refresh_open_schedules(2026, tmp_path / "working", output, reviewed, feeds={"NFL": ("espn", lambda _year: nfl)})
    assert path.stat().st_mtime_ns == stamp


@pytest.mark.parametrize("league", sorted(feeds.FEEDS))
def test_every_feed_has_attribution(league):
    kind, fetch = feeds.FEEDS[league]
    assert kind in feeds.SOURCES and callable(fetch)
