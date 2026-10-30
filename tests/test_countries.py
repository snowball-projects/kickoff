import copy
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kickoff import feeds
from kickoff.countries import COUNTRY_LEAGUES, venue_country
from kickoff.open_schedules import refresh_open_schedules
from kickoff.reviewed_schedules import load_reviewed_schedules, reviewed_events
from kickoff.web import _event_payload
from tests.test_feeds import espn_game
from tests.test_reviewed_schedules import fake_open_read

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "source, expected",
    [
        ("USA", "US"),
        ("Japan", "JP"),
        (" JP ", "JP"),
        ("England", "GB"),
        ("Northern Ireland", "GB"),
        ("Türkiye", "TR"),
        ("Macau", "MO"),
        ("Puerto Rico", "PR"),
        ("Dominican Republic", "DO"),
        ("Croatia", "Croatia"),
        ("Rwanda", "Rwanda"),
        (None, None),
        ("", None),
        ("TBD", None),
        ("TBA", None),
        ("unknown", None),
    ],
)
def test_explicit_venue_countries_normalize_without_geographic_inference(source, expected):
    assert venue_country(source) == expected


@pytest.mark.parametrize("source", [42, {}, []])
def test_non_string_countries_are_rejected_where_produced(source):
    with pytest.raises(ValueError, match="country"):
        venue_country(source)


@pytest.mark.parametrize("league", sorted(COUNTRY_LEAGUES))
def test_espn_reads_only_the_venue_country_and_exports_its_receipt(league):
    row = espn_game("9", "2026-10-28T17:00Z", "Japan", "France")
    row["competitions"][0]["venue"]["address"] = {"city": "Paris", "country": "Japan"}
    url = f"{feeds.ESPN}/existing/scoreboard?dates=20261028"
    event = feeds._espn_event(row, league=league, sport="soccer", zone=feeds.EASTERN, fallback_url=url, input_url=url)
    assert event.country == "JP"
    assert event.country_source_url == url
    assert event.country_checked_date == datetime.now(UTC).date().isoformat()
    public = _event_payload(event)
    assert public["country"] == "JP"
    assert public["country_source_url"] == url
    assert public["country_checked_date"] == event.country_checked_date
    assert event.home_participant.name == "Japan"
    assert event.away_participant.name == "France"
    row["competitions"][0]["venue"]["address"].pop("country")
    empty = feeds._espn_event(row, league=league, sport="soccer", zone=feeds.EASTERN, fallback_url=url, input_url=url)
    assert empty.country is empty.country_source_url is empty.country_checked_date is None
    assert "country_checked_date" not in _event_payload(empty)


@pytest.mark.parametrize("league", ["NBA", "NFL", "NHL", "MLB", "NASCAR_CUP", "INDYCAR"])
def test_excluded_espn_leagues_do_not_gain_countries(league):
    row = espn_game("9", "2026-10-28T17:00Z", "Japan", "France")
    row["competitions"][0]["venue"]["address"] = {"country": "USA"}
    event = feeds._espn_event(
        row, league=league, sport="soccer", zone=feeds.EASTERN, fallback_url="https://example.com"
    )
    assert event.country is event.country_source_url is event.country_checked_date is None


@pytest.mark.parametrize("country, expected", [("Spain", "ES"), ("Croatia", "Croatia"), ("Rwanda", "Rwanda")])
def test_live_espn_fetchers_preserve_explicit_country_names_and_request_url(monkeypatch, country, expected):
    row = espn_game("9", "2026-10-28T17:00Z", "Home", "Away")
    row["competitions"][0]["venue"]["address"] = {"country": country}
    urls = []

    def get_json(url, **_):
        urls.append(url)
        if "openligadb" in url:
            return [{"matchDateTimeUTC": "2026-10-28T17:00Z"}]
        return {"events": [copy.deepcopy(row)]}

    monkeypatch.setattr(feeds, "get_json", get_json)
    for league in ["UFC", "PGA_TOUR", "UEFA_CHAMPIONS_LEAGUE"]:
        (event,) = feeds.FEEDS[league][1](2026)
        assert event.country == expected
        assert event.country_source_url == urls[-1]
        assert "/scoreboard?dates=" in event.country_source_url


@pytest.mark.parametrize("country", ["Croatia", "Rwanda"])
def test_new_explicit_country_names_do_not_abort_publication(monkeypatch, tmp_path, country):
    row = espn_game("9", "2026-10-28T17:00Z", "Home", "Away")
    row["competitions"][0]["venue"]["address"] = {"country": country}
    monkeypatch.setattr(feeds, "get_json", lambda *_args, **_kwargs: {"events": [row]})
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    output = refresh_open_schedules(2026, tmp_path, ROOT / "data/reviewed", feeds={"UFC": feeds.FEEDS["UFC"]})
    bundle = json.loads(output.read_text())
    event = next(event for event in bundle["events"] if event["event_id"] == "espn-ufc-9")
    assert event["country"] == country
    assert event["country_source_url"].endswith("/mma/ufc/scoreboard?dates=2026&limit=500")
    assert event["country_checked_date"] == datetime.now(UTC).date().isoformat()


def test_reviewed_countries_retain_pinned_sources_and_leave_unstated_locations_empty():
    events, sources, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    scoped = [event for event in events if event.league in COUNTRY_LEAGUES]
    known = [event for event in scoped if event.country]
    assert Counter(event.league for event in known) == {
        "UFC": 42,
        "PFL": 16,
        "ONE": 16,
        "RIZIN": 9,
        "PGA_TOUR": 9,
        "LPGA_TOUR": 26,
        "GOLF_MAJORS_MEN": 4,
        "GOLF_MAJORS_WOMEN": 5,
    }
    receipts = {source["url"]: source for source in sources}
    for event in known:
        assert event.country_source_url == event.source_url
        assert event.country_checked_date == receipts[event.source_url]["country_checked_date"] == "2026-10-29"
        assert "country_input_url" in receipts[event.source_url]
    by_id = {event.event_id: event for event in scoped}
    assert by_id["ufc-333"].country == "AE"
    assert by_id["rizin-2026-new-years-eve"].country == "JP"
    assert by_id["pfl-2026-global-05"].country == "GB"
    assert by_id["boxing-navarrete-foster-1"].country is None  # source names San Antonio, no country
    assert next(e for e in scoped if e.title == "Hilton Grand Vacations Tournament of Champions").country == "US"
    assert next(e for e in scoped if e.title == "The Players Championship").country == "US"  # explicit P17=Q30


def test_exactly_the_sixteen_lpga_us_state_locations_have_us_country():
    expected = {
        "hilton-grand-vacations-tournament-of-champions",
        "fortinet-founders-cup",
        "ford-championship",
        "aramco-championship",
        "jm-eagle-la-championship",
        "mizuho-americas-open",
        "kroger-queen-city-championship",
        "shoprite-lpga-classic",
        "dow-championship",
        "meijer-lpga-classic",
        "standard-portland-classic",
        "fm-championship",
        "walmart-nw-arkansas-championship",
        "lotte-championship",
        "the-annika",
        "cme-group-tour-championship",
    }
    payload = json.loads((ROOT / "data/reviewed/2026-golf.json").read_text())
    source = next(source for source in payload["sources"] if source["id"] == "wikipedia-2026-golf-lpga-tour")
    assert source["revision"] == "1372529225"
    assert source["sha256"] == "dfa131764846ffa80430cd4b8cb67c8532506d6078ea01e5c32432f611efe2ca"
    assert source["license"] == "CC BY-SA 4.0"
    events = reviewed_events(payload, 2026)[0]
    lpga = [event for event in events if event.league == "LPGA_TOUR"]
    us = [event for event in lpga if event.country == "US"]
    assert {event.event_id.removeprefix("wikipedia-golf-2026-lpga-tour-") for event in us} == expected
    assert len(lpga) == 26 and all(event.country for event in lpga)
    for event in us:
        public = _event_payload(event)
        assert public["country"] == "US"
        assert public["country_source_url"] == source["url"]
        assert public["country_checked_date"] == source["country_checked_date"] == "2026-10-29"
    # Existing international LPGA countries and reviewed PGA gaps stay intact.
    assert {event.country for event in lpga if event not in us} == {
        "TH",
        "SG",
        "CN",
        "MX",
        "GB",
        "CA",
        "KR",
        "MY",
        "JP",
    }
    assert sum(event.country is None for event in events if event.league == "PGA_TOUR") == 32


@pytest.mark.parametrize(
    "fields",
    [
        {"country": 42},
        {"country_source_url": "https://example.com/new-source"},
        {"country_checked_date": "today"},
    ],
)
def test_reviewed_country_requires_a_valid_value_and_its_own_source_date(fields):
    payload = json.loads((ROOT / "data/reviewed/2026-golf.json").read_text())
    payload["events"][0].update(fields)
    with pytest.raises(ValueError):
        reviewed_events(payload, 2026)
