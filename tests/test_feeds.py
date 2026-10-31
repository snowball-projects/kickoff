import pytest

from kickoff import feeds


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
    assert event.title == "World Series · Game 6"
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


@pytest.mark.parametrize("league", sorted(feeds.FEEDS))
def test_every_feed_has_attribution(league):
    kind, fetch = feeds.FEEDS[league]
    assert kind in feeds.SOURCES and callable(fetch)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-10-17T19:00-06:00", "2026-10-18T01:00:00Z"),
        ("2026-01-01T00:15+05:30", "2025-12-31T18:45:00Z"),
        ("2026-12-31T23:45-03:00", "2027-01-01T02:45:00Z"),
        ("2026-10-17T23:30Z", "2026-10-17T23:30:00Z"),
        ("2026-10-17T23:30:12.345+00:00", "2026-10-17T23:30:12Z"),
    ],
)
def test_source_offsets_convert_to_utc(value, expected):
    assert feeds._iso_utc(value) == expected
    event = feeds.make_event(
        source="espn",
        league="NBA",
        sport="basketball",
        upstream_id=1,
        season="2026",
        title="Offset game",
        utc=value,
        day="2026-10-17",
    )
    assert event.start_time_utc == expected


@pytest.mark.parametrize("value", ["2026-10-17", "2026-10-17T19:00:00"])
def test_source_timestamps_without_offsets_are_rejected(value):
    with pytest.raises(ValueError, match="timezone offset"):
        feeds._iso_utc(value)
    with pytest.raises(ValueError, match="timezone offset"):
        feeds._local_date(value, feeds.EASTERN)
