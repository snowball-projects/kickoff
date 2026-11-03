import copy
import json
from pathlib import Path

import pytest

from kickoff import feeds
from kickoff.published import publish_sports
from kickoff.reviewed_countries import fill_reviewed_countries, reviewed_country_facts
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.web import _event_payload
from tests.test_feeds import espn_game
from tests.test_published import bundle

ROOT = Path(__file__).resolve().parents[1]


def appointment(fact):
    return feeds.make_event(
        source="espn",
        upstream_id=fact["event_id"].rsplit("-", 1)[1],
        league=fact["league"],
        sport="golf",
        season=fact["start_date"][:4],
        title=fact["title"],
        day=fact["start_date"],
        utc=None,
        end_day=fact["end_date"],
        venue=fact["venue"],
        source_url="https://www.espn.com/golf/",
    )


def test_country_registry_is_offline_exact_and_keeps_direct_source_facts():
    _, facts = reviewed_country_facts()
    fact = next(row for row in facts.values() if row["league"] == "PGA_TOUR")
    event = appointment(fact)
    evidence, sources = fill_reviewed_countries([event])
    assert event.country == fact["country"]
    assert event.country_source_url == fact["source_url"]
    assert event.country_checked_date == fact["checked_date"]
    assert evidence[0]["countries_added"][0]["sha256"] == fact["sha256"]
    assert sources[0]["kind"] == "espn"
    event.country = "MX"
    event.country_source_url = "https://direct-source.test/"
    assert fill_reviewed_countries([event]) == ([], [])
    assert event.country == "MX"
    assert event.country_source_url == "https://direct-source.test/"


@pytest.mark.parametrize(
    "field, value",
    [
        ("title", "Renamed"),
        ("venue", "Changed course"),
        ("calendar_date", "2028-01-01"),
        ("end_calendar_date", "2028-01-04"),
        ("league", "LPGA_TOUR"),
    ],
)
def test_changed_appointment_does_not_reuse_country(field, value):
    _, facts = reviewed_country_facts()
    fact = next(row for row in facts.values() if row["league"] == "PGA_TOUR")
    event = appointment(fact)
    setattr(event, field, value)
    evidence, sources = fill_reviewed_countries([event])
    assert event.country is None
    assert sources[0]["kind"] == "espn"
    withheld = evidence[0]["countries_withheld"][0]
    assert withheld["event_id"] == event.event_id
    assert withheld["source_url"] == fact["source_url"]
    assert withheld["checked_date"] == fact["checked_date"]
    assert withheld["sha256"] == fact["sha256"]
    assert "country" not in withheld


def test_physical_motogp_and_wec_hosts_and_unconfirmed_future_prologue():
    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    before = {e.event_id: copy.deepcopy(e) for e in events}
    fill_reviewed_countries(events)
    for event in events:
        if event.league == "MOTOGP" and "Misano" in event.venue:
            assert event.country == "IT"  # San Marino GP is physically in Italy.
        if event.league == "WEC" and "Barcelona" in event.title:
            assert event.country == "ES"  # Sponsor/title geography is not used.
        assert event.title == before[event.event_id].title
        assert event.calendar_date == before[event.event_id].calendar_date
        assert event.source_url == before[event.event_id].source_url
    future, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2027)
    fill_reviewed_countries(future)
    prologue = next(e for e in future if e.league == "WEC" and e.title == "Prologue")
    assert prologue.country is None


def test_unstated_future_courses_are_not_filled():
    _, facts = reviewed_country_facts()
    for identity in ("espn-pga_tour-401916376", "espn-lpga_tour-401929350", "espn-dp_world_tour-401921653"):
        assert identity not in facts


@pytest.mark.parametrize(
    "location, country",
    [
        ("London, Great Britain", "GB"),
        ("Beijing, China PR", "CN"),
        ("Seoul, Korea Republic", "KR"),
        ("Paris, France", "FR"),
        ("Hong Kong, Hong Kong, China", None),
        ("Paris", None),
        ("London, Unknown", None),
        ("London, England", "GB"),
        ("Monte-Carlo, Monaco", "MC"),
        ("Cluj-Napoca, Romania", "RO"),
        ("Umag, Croatia", "HR"),
        ("Marrakech, Morocco", "MA"),
    ],
)
def test_tennis_reads_explicit_top_level_venue_country_only(location, country):
    row = espn_game("99", "2026-10-28T17:00Z", "Home", "Away")
    row["competitions"][0].pop("venue")
    row["venue"] = {"displayName": location}
    event = feeds._espn_event(
        row, league="ATP", sport="tennis", zone=feeds.EASTERN, fallback_url="https://www.espn.com/tennis/"
    )
    assert event.country == country
    assert event.venue == location


def test_nfl_and_hydrated_mlb_keep_explicit_venue_country(monkeypatch):
    row = espn_game("99", "2026-11-15T14:30Z", "Home", "Away")
    row["competitions"][0]["venue"]["address"] = {"country": "Germany"}
    event = feeds._espn_event(
        row, league="NFL", sport="football", zone=feeds.EASTERN, fallback_url="https://www.espn.com/"
    )
    assert event.country == "DE"
    game = {
        "gamePk": 99,
        "gameDate": "2026-04-25T22:00Z",
        "gameType": "R",
        "status": {},
        "teams": {"home": {"team": {"name": "Home"}}, "away": {"team": {"name": "Away"}}},
        "venue": {"name": "Park", "location": {"country": "Mexico"}},
    }

    def get_json(url, **_):
        assert "hydrate=venue(location)" in url
        return {"dates": [{"games": [game]}]}

    monkeypatch.setattr(feeds, "get_json", get_json)
    (event,) = feeds.mlb_events(2026)
    assert event.country == "MX"
    assert "hydrate=venue(location)" in event.country_source_url


def test_country_only_source_evidence_survives_per_league_publication(tmp_path):
    original = bundle()
    _, facts = reviewed_country_facts()
    fact = next(row for row in facts.values() if row["league"] == "PGA_TOUR")
    event = appointment(fact)
    evidence, sources = fill_reviewed_countries([event])
    public = _event_payload(event)
    # ESPN country-only supplements must also be attributed for a native source.
    public.update(source="nhl", sport="hockey", league="NHL")
    original["events"] = [public]
    original["sources"] += sources + [{"kind": "nhl", "name": "NHL", "url": "https://www.nhl.com/"}]
    original["data_licenses"]["nhl"] = "No license granted"
    original["input_evidence"] = evidence
    publish_sports([original], tmp_path)
    published = json.loads((tmp_path / "2026-hockey-nhl.json").read_text())
    assert {s["kind"] for s in published["sources"]} == {"nhl", "espn"}
    assert set(published["data_licenses"]) == {"nhl", "espn"}
    assert published["events"][0]["country_source_url"] == fact["source_url"]
    assert published["input_evidence"][0]["countries_added"][0]["event_id"] == event.event_id


def test_changed_indycar_country_receipt_retains_citations_and_terms_only_in_its_league(tmp_path):
    _, facts = reviewed_country_facts()
    fact = facts["espn-indycar-202608164264"]
    event = appointment(fact)
    event.sport = "motorsport"
    # The published ESPN appointment supplies this venue; the reviewed fact had none.
    event.venue = "Streets of Markham"
    evidence, sources = fill_reviewed_countries([event])
    assert event.source == "espn"
    assert event.country is event.country_source_url is event.country_checked_date is None
    assert len(sources) == 1 and sources[0]["kind"] == "indycar"
    assert not evidence[0]["countries_added"]
    withheld = evidence[0]["countries_withheld"][0]
    assert withheld == {
        "event_id": event.event_id,
        "reason": "Appointment changed since country review",
        "source_url": "https://www.indycar.com/Schedule/2026/Markham",
        "checked_date": fact["checked_date"],
        "sha256": fact["sha256"],
    }
    original = bundle()
    public = _event_payload(event)
    unrelated = {**public, "event_id": "unrelated-nascar", "league": "NASCAR_CUP", "title": "Other race"}
    original["events"] = [public, unrelated]
    original["input_evidence"] = evidence
    original["sources"] += sources
    original["data_licenses"].update({source["kind"]: source["license"] for source in sources})
    publish_sports([original], tmp_path)
    indycar = json.loads((tmp_path / "2026-motorsport-indycar.json").read_text())
    assert indycar["input_evidence"] == evidence
    assert sources[0] in indycar["sources"]
    assert indycar["data_licenses"]["indycar"] == sources[0]["license"]
    assert (
        next(source for source in indycar["sources"] if source["kind"] == "indycar")["license_url"]
        == sources[0]["license_url"]
    )
    for row in indycar["events"]:
        assert row["country"] is None
        assert "country_source_url" not in row
        assert "country_checked_date" not in row
    nascar = json.loads((tmp_path / "2026-motorsport-nascar-cup.json").read_text())
    assert not nascar["input_evidence"]
    assert {source["kind"] for source in nascar["sources"]} == {"espn"}
    assert set(nascar["data_licenses"]) == {"espn"}
