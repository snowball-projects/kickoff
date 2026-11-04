"""Seven-day publication retention and the source requests selected by that cutoff."""

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds
from kickoff.published import PublishedWindow, load_published_window, publish_sports
from tests.test_published import bundle

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def window_for(*leagues):
    return PublishedWindow(NOW, {(year, league): {"events": []} for year in (2025, 2026, 2027) for league in leagues})


def event(identity, day, **changes):
    return {**bundle()["events"][0], "event_id": identity, "calendar_date": day, "end_calendar_date": day, **changes}


def test_old_events_are_verbatim_even_without_results_and_when_new_sources_disagree():
    old = event("old", "2026-10-27", facts_checked_date="2026-01-01", result={"complete": False, "rows": []})
    no_result = event("missing", "2026-10-01")
    boundary = event("boundary", "2026-10-28")
    spanning = event("span", "2026-10-01", end_calendar_date="2026-11-01")
    original = deepcopy([old, no_result, boundary, spanning])
    window = PublishedWindow(NOW, {(2026, "NFL"): {"events": original}})
    fresh = [{**e, "title": "Source correction"} for e in (old, boundary, spanning)]
    merged = {e["event_id"]: e for e in window.merge(fresh, 2026)}
    assert merged["old"] == old and merged["missing"] == no_result
    assert merged["boundary"]["title"] == merged["span"]["title"] == "Source correction"
    assert window.bundles[2026, "NFL"]["events"] == original
    assert "result" not in merged["missing"]
    merged["old"]["result"]["rows"].append("caller mutation")
    assert original[0]["result"]["rows"] == []


def test_old_identity_stays_in_its_published_year_if_a_new_source_moves_it():
    old = event("old", "2025-12-20")
    window = PublishedWindow(NOW, {(2025, "NFL"): {"events": [old]}})
    moved = {**old, "calendar_date": "2026-11-01", "end_calendar_date": "2026-11-01"}
    assert window.merge([moved], 2026) == []
    assert window.merge([], 2025) == [old]


@pytest.mark.parametrize("source,league", [("f1db", "F1"), ("espn", "NASCAR_CUP")])
def test_only_results_only_sources_retain_stored_results_before_lookup(source, league):
    from kickoff.web import _event_payload

    item = feeds.make_event(
        source=source,
        league=league,
        sport="motorsport",
        upstream_id="race",
        season="2026",
        title="Race",
        day="2026-10-31",
        utc=None,
        event_type="race",
    )
    previous = {
        **_event_payload(item),
        "status": "finished",
        "result": {"kind": "podium", "complete": True, "rows": []},
    }
    window = PublishedWindow(NOW, {(2026, league): {"events": [previous]}})
    window.restore_results([item])
    assert item.result == (previous["result"] if source == "f1db" else None)


@pytest.mark.parametrize("damage", ["missing", "json", "count", "generation"])
def test_only_unreadable_or_unchecked_league_rebuilds_in_full(tmp_path, damage):
    original = bundle()
    original["events"] = [event("nfl", "2026-10-01"), event("nba", "2026-10-01", sport="basketball", league="NBA")]
    publish_sports([original], tmp_path)
    bodies = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    name = "2026-basketball-nba.json"
    if damage == "missing":
        del bodies[name]
    elif damage == "json":
        bodies[name] = b"{broken"
    else:
        payload = json.loads(bodies[name])
        if damage == "count":
            payload["events"] = []
        else:
            payload["updated_at"] = "old generation"
        bodies[name] = json.dumps(payload).encode()
    window = load_published_window(bodies.__getitem__, NOW)
    assert window.since("NFL", 2026) == date(2026, 10, 28)
    assert window.since("NBA", 2026) == date.min
    assert set(window.events) == {"nfl"}


@pytest.mark.parametrize("body", [b"{broken", b"null", b'{"schema_version":"1","seasons":null}'])
def test_unreadable_manifest_rebuilds_without_interpreting_state(body):
    window = load_published_window(lambda _: body, NOW)
    assert window.bundles == {} and window.since("NFL", 2026) == date.min


def test_force_full_does_not_read_published_files_and_removes_generated_refresh_state(monkeypatch, tmp_path):
    from tests.test_public_refresh import runner

    original = bundle()
    original["events"] = [event("new", "2026-10-01")]
    windows = []

    def collect(year, output, reviewed, **options):
        windows.append(options["window"])
        path = output / f"{year}.json"
        path.write_text(json.dumps(original))
        return path

    def no_baseline(_):
        pytest.fail("force_full may not read published files")

    monkeypatch.setattr(runner, "refresh_open_schedules", collect)
    (tmp_path / "refresh-state.json").write_text("obsolete state")
    runner.refresh([2026], tmp_path, tmp_path, force_full=True, read_bytes=no_baseline, clock=lambda: NOW)
    assert windows[0].since("NFL", 2026) == date.min
    assert not (tmp_path / "refresh-state.json").exists()
    assert json.loads((tmp_path / "2026-football-nfl.json").read_text())["events"] == original["events"]


def test_college_football_uses_remaining_weeks_bowls_cfp_both_groups_and_one_next_season_check(monkeypatch):
    calls = []
    window = window_for("COLLEGE_FOOTBALL")

    def get(url, **_):
        q = parse_qs(urlsplit(url).query)
        calls.append(q)
        if q["limit"] != ["1"]:
            assert "week" in q and "seasontype" in q and len(q["dates"][0]) == 4
            return {"events": []}
        calendar = [
            {
                "value": "2",
                "entries": [
                    {"value": "1", "startDate": "2026-09-01", "endDate": "2026-09-07"},
                    {"value": "9", "startDate": "2026-10-25", "endDate": "2026-11-01"},
                    {"value": "10", "startDate": "2026-11-02", "endDate": "2026-11-08"},
                ],
            },
            {
                "value": "3",
                "entries": [
                    {"value": "1", "startDate": "2026-12-13", "endDate": "2027-01-28"},
                    {"value": "999", "startDate": "2026-12-18", "endDate": "2027-01-28"},
                ],
            },
        ]
        return {"events": [], "leagues": [{"season": {"year": 2026}, "calendar": calendar}]}

    monkeypatch.setattr(feeds, "get_json", get)
    assert feeds.espn_team_events(2025, "COLLEGE_FOOTBALL", window=window) == []
    feeds.espn_team_events(2026, "COLLEGE_FOOTBALL", window=window)
    feeds.espn_team_events(2027, "COLLEGE_FOOTBALL", window=window)
    weekly = [q for q in calls if "week" in q]
    assert len(weekly) == 8
    assert {(q["seasontype"][0], q["week"][0]) for q in weekly} == {("2", "9"), ("2", "10"), ("3", "1"), ("3", "999")}
    assert {q["groups"][0] for q in weekly} == {"80", "81"}
    assert [q["dates"][0] for q in calls if q["limit"] == ["1"]] == ["2026", "2027"]


@pytest.mark.parametrize("league", ["NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL"])
def test_college_basketball_uses_calendar_and_known_postseason_days_without_empty_days(monkeypatch, league):
    window = window_for(league)
    window.events["postseason"] = event("postseason", "2027-03-20", league=league, is_postseason=True)
    calls = []

    def get(url, **_):
        q = parse_qs(urlsplit(url).query)
        calls.append(q)
        if q["limit"] == ["1"]:
            calendar = ["2026-10-27T08:00Z", "2026-10-28T08:00Z", "2026-11-04T08:00Z", "2027-03-01T08:00Z"]
            return {
                "events": [],
                "leagues": [{"season": {"year": 2027}, "calendar": calendar if q["dates"] == ["2027"] else []}],
            }
        return {"events": []}

    monkeypatch.setattr(feeds, "get_json", get)
    for year in (2025, 2026, 2027):
        feeds.espn_team_events(year, league, window=window)
    assert [q["dates"][0] for q in calls if q["limit"] == ["1"]] == ["2027", "2028"]
    assert sorted(q["dates"][0] for q in calls if q["limit"] != ["1"]) == [
        "20261028",
        "20261104",
        "20270301",
        "20270320",
    ]


def test_nba_months_and_champions_league_year_replace_old_queries(monkeypatch):
    calls = []
    monkeypatch.setattr(feeds, "get_json", lambda url, **_: calls.append(url) or {"events": []})
    window = window_for("NBA", "UEFA_CHAMPIONS_LEAGUE")
    feeds.nba_events(2025, window=window)
    feeds.nba_events(2026, window=window)
    feeds.ucl_events(2025, window=window)
    feeds.ucl_events(2026, window=window)
    assert [parse_qs(urlsplit(u).query)["dates"][0] for u in calls] == ["202610", "202611", "202612", "2026"]
    assert all("/scoreboard?" in u for u in calls)


def test_nhl_starts_at_cutoff_and_stops_when_source_has_no_next_week(monkeypatch):
    calls = []

    def get(url, **_):
        calls.append(url)
        return {"gameWeek": [], **({"nextStartDate": "2026-11-04"} if url.endswith("2026-10-28") else {})}

    monkeypatch.setattr(feeds, "get_json", get)
    window = window_for("NHL")
    feeds.nhl_events(2025, window=window)
    feeds.nhl_events(2026, window=window)
    assert [u.rsplit("/", 1)[-1] for u in calls] == ["2026-10-28", "2026-11-04"]


def test_mlb_and_annual_espn_sources_skip_old_years(monkeypatch):
    calls = []

    def get(url, **_):
        calls.append(url)
        return {"dates": []} if urlsplit(url).hostname == "statsapi.mlb.com" else {"events": []}

    monkeypatch.setattr(feeds, "get_json", get)
    window = window_for("MLB", "ATP")
    feeds.mlb_events(2025, window=window)
    feeds.mlb_events(2026, window=window)
    feeds.FEEDS["ATP"][1](2025, window=window)
    feeds.FEEDS["ATP"][1](2026, window=window)
    assert len(calls) == 2
    assert parse_qs(urlsplit(calls[0]).query)["startDate"] == ["2026-10-28"]
    assert parse_qs(urlsplit(calls[1]).query)["dates"] == ["2026"]


def test_f1_reads_only_races_that_reach_past_cutoff_and_keeps_old_sessions_exact(monkeypatch, tmp_path):
    from kickoff import open_schedules as schedules
    from tests.test_reviewed_schedules import fake_open_read

    old_path = "src/data/seasons/2026/races/01"
    new_path = "src/data/seasons/2026/races/02"
    old = event(
        "old-race",
        "2026-10-01",
        season="2026",
        league="F1",
        sport="motorsport",
        source="f1db",
        source_url=f"https://github.com/f1db/f1db/blob/{'b' * 40}/{old_path}/race.yml",
    )
    cup = event("old-cup", "2026-06-01", season="2026", league="FIFA_WORLD_CUP", source="openfootball")
    window = PublishedWindow(NOW, {(2026, "F1"): {"events": [old]}, (2026, "FIFA_WORLD_CUP"): {"events": [cup]}})
    calls = []

    def read(url):
        calls.append(url)
        if "/contents/" in url:
            return json.dumps([{"type": "dir", "path": path} for path in (old_path, new_path)]).encode()
        if url.endswith(new_path + "/race.yml"):
            return b"id: 2\nround: 2\ndate: 2026-11-10\ntime: 12:00\ngrandPrixId: test\ncircuitId: monaco\n"
        return fake_open_read(url)

    monkeypatch.setattr(schedules, "FOOTBALL", {})
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: ([], [], []))
    monkeypatch.setattr(schedules, "read_url", read)
    path = schedules.refresh_open_schedules(2026, tmp_path, window=window)
    events = {e["event_id"]: e for e in json.loads(path.read_text())["events"]}
    assert events["old-race"] == old and events["old-cup"] == cup
    assert "f1db-2-race" in events and "f1db-2-race" in window.f1_contexts
    assert not any(old_path + "/race.yml" in url or "worldcup.json" in url for url in calls)


def test_openfootball_skips_old_season_files_and_checks_next_season_once(monkeypatch, tmp_path):
    from urllib.error import HTTPError

    from kickoff import open_schedules as schedules
    from tests.test_reviewed_schedules import fake_open_read

    window = window_for("EPL", "F1")
    cup = event("cup", "2026-06-01", season="2026", league="FIFA_WORLD_CUP", source="openfootball")
    window.events["cup"] = cup
    window.bundles[2026, "FIFA_WORLD_CUP"] = {"events": [cup]}
    calls = []

    def read(url):
        calls.append(url)
        if "/contents/" in url and "/2027/" in url:
            raise HTTPError(url, 404, "unpublished", {}, None)
        if url.endswith("2027-28/en.1.json"):
            raise HTTPError(url, 404, "unpublished", {}, None)
        if url.endswith("2026-27/en.1.json"):
            return json.dumps(
                {
                    "matches": [
                        {"date": day, "team1": "Home", "team2": "Away", "round": str(index)}
                        for index, day in enumerate(("2026-11-10", "2027-01-10"))
                    ]
                }
            ).encode()
        return fake_open_read(url)

    monkeypatch.setattr(schedules, "FOOTBALL", {"en.1": schedules.FOOTBALL["en.1"]})
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: ([], [], []))
    monkeypatch.setattr(schedules, "read_url", read)
    # A past F1 year needs no source lookup; the future empty directory is the next-season check.
    window.bundles[2026, "F1"] = {"events": [event("old-f1", "2026-01-01", season="2026", league="F1")]}
    for year in (2026, 2027):
        schedules.refresh_open_schedules(year, tmp_path, window=window)
    assert not any("2025-26/en.1.json" in url for url in calls)
    assert len([url for url in calls if url.endswith("2026-27/en.1.json")]) == 1
    assert len([url for url in calls if url.endswith("2027-28/en.1.json")]) == 1


def test_nba_monthly_slots_require_at_least_one_assigned_team(monkeypatch):
    from tests.test_feeds import espn_game

    empty = espn_game("slot", "2026-11-05T20:00Z", "TBD", "TBD")
    for competitor, identity in zip(empty["competitions"][0]["competitors"], ["-1", "-2"], strict=True):
        competitor["team"]["id"] = identity
    assigned = deepcopy(empty)
    assigned["id"] = "assigned"
    assigned["competitions"][0]["competitors"][0]["team"].update(id="1", displayName="Hawks")
    monkeypatch.setattr(feeds, "get_json", lambda url, **_: {"events": [empty, assigned]})
    assert [e.event_id for e in feeds.nba_events(2026)] == ["espn-nba-assigned"]


def test_weekly_fcs_index_does_not_relabel_fbs_playoff_slots(monkeypatch):
    from tests.test_feeds import espn_game

    row = espn_game("playoff", "2026-12-19T20:00Z", "TBD", "TBD")
    row["competitions"][0]["notes"] = [{"type": "event", "headline": "College Football Playoff First Round Game"}]
    monkeypatch.setattr(feeds, "_weekly_queries", lambda *a, **k: [("https://espn.com/weekly?dates=2026", 3, 999, 81)])
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: {"events": [row]})
    (item,) = feeds.espn_team_events(2026, "COLLEGE_FOOTBALL")
    assert "fbs" in item.tags and "fcs" not in item.tags
