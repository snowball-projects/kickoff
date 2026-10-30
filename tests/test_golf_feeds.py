"""ESPN-only golf coverage using trimmed, source-linked date facts."""

import json

import pytest

from kickoff import feeds
from kickoff.open_schedules import refresh_open_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read


def golf_feeds(monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/espn-golf.json").read_text())
    calls = []

    def get_json(url):
        calls.append(url)
        tour = "lpga" if "/lpga/" in url else "pga"
        assert url == fixture["sources"][tour]
        return fixture["feeds"][tour]

    monkeypatch.setattr(feeds, "get_json", get_json)
    return calls


def test_both_tours_keep_full_spans_and_all_nine_majors_once(monkeypatch, tmp_path):
    calls = golf_feeds(monkeypatch)
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    path = refresh_open_schedules(
        2026,
        tmp_path,
        ROOT / "data/reviewed",
        feeds={league: feeds.FEEDS[league] for league in ("PGA_TOUR", "LPGA_TOUR")},
    )
    bundle = json.loads(path.read_text())
    golf = [e for e in bundle["events"] if e["sport"] == "golf"]
    assert len(golf) == len({e["event_id"] for e in golf}) == 15
    assert len(calls) == 2
    assert {e["source"] for e in golf} == {"espn"}
    assert {e["league"] for e in golf} == {"PGA_TOUR", "LPGA_TOUR"}
    assert all(e["source_url"].startswith("https://www.espn.com/golf/leaderboard?") for e in golf)
    assert all(e["start_time_utc"] is None and e["end_calendar_date"] > e["calendar_date"] for e in golf)
    assert not any("Sentry" in e["title"] for e in golf)
    assert sum(e["competition_phase"] == "championship" and e["league"] == "PGA_TOUR" for e in golf) == 4
    assert sum(e["competition_phase"] == "championship" and e["league"] == "LPGA_TOUR" for e in golf) == 5
    assert all(e["is_postseason"] for e in golf if e["competition_phase"] == "championship")
    assert "LPGA Tour" in bundle["coverage"]
    assert "No license granted" in bundle["data_licenses"]["espn"]
    assert not any("golf" in s["url"].lower() for s in bundle["sources"] if s.get("kind") != "espn")
    by_id = {e["event_id"]: e for e in golf}
    three = by_id["espn-lpga_tour-401835157"]
    monday = by_id["espn-pga_tour-401811953"]
    cross = by_id["espn-lpga_tour-401835135"]
    assert (three["calendar_date"], three["end_calendar_date"]) == ("2026-05-29", "2026-05-31")
    assert (monday["calendar_date"], monday["end_calendar_date"]) == ("2026-06-25", "2026-06-29")
    assert (cross["calendar_date"], cross["end_calendar_date"]) == ("2026-01-29", "2026-02-01")
    # Scoreboard venue countries are absent. Never reuse obsolete Wikipedia
    # countries or infer them from an event's title.
    assert all(e["country"] is None for e in golf)


@pytest.mark.parametrize("league", ["PGA_TOUR", "LPGA_TOUR"])
def test_major_classification_does_not_depend_on_the_year_or_dates(monkeypatch, league):
    golf_feeds(monkeypatch)
    events = feeds.FEEDS[league][1](2026)
    for e in events:
        assert feeds.espn_calendar_phase(league, "new-id", "2027", e.title) == e.competition_phase
    for name in ["Open", "Sony Open in Hawaii", "ISPS HANDA Women's Scottish Open", "CPKC Women's Open"]:
        assert feeds.espn_calendar_phase(league, "new-id", "2027", name) == "regular_season"


def test_reviewed_golf_schedules_and_final_date_markers_are_gone():
    for path in (ROOT / "data/reviewed").glob("*.json"):
        registry = json.loads(path.read_text())
        assert all(e["sport"] != "golf" and e.get("date_scope") != "final_date" for e in registry["events"])
    assert not (ROOT / "data/reviewed/2026-golf.json").exists()


def test_lpga_empty_calendar_placeholder_is_not_a_tournament(monkeypatch):
    # An actual empty row in the 2025 LPGA season, checked 2026-10-30:
    # https://site.api.espn.com/apis/site/v2/sports/golf/lpga/scoreboard?dates=2025&limit=500
    fixture = json.loads((ROOT / "tests/fixtures/espn-golf.json").read_text())
    payload = fixture["feeds"]["lpga"]
    expected = len(payload["events"])
    payload["events"].append({})
    monkeypatch.setattr(feeds, "get_json", lambda _: payload)
    assert len(feeds.FEEDS["LPGA_TOUR"][1](2026)) == expected


@pytest.mark.parametrize("bad_row", [None, {"id": "undated", "name": "Not a dated schedule"}])
def test_incomplete_nonempty_golf_rows_still_fail_the_refresh(monkeypatch, bad_row):
    monkeypatch.setattr(feeds, "get_json", lambda _: {"events": [bad_row]})
    with pytest.raises((KeyError, AttributeError)):
        feeds.FEEDS["LPGA_TOUR"][1](2026)


def test_lpga_without_an_event_link_uses_the_lpga_leaderboard(monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/espn-golf.json").read_text())
    row = fixture["feeds"]["lpga"]["events"][0]
    row["links"] = []
    monkeypatch.setattr(feeds, "get_json", lambda _: {"events": [row]})
    (event,) = feeds.FEEDS["LPGA_TOUR"][1](2026)
    assert event.source_url == "https://www.espn.com/golf/leaderboard/_/tour/lpga"
