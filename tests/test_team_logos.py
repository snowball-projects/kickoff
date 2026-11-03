"""The manually reviewed image list is source-linked; daily lookup stays offline."""

import json
from copy import deepcopy
from datetime import date
from importlib.resources import files

import pytest

from kickoff import feeds, team_logos
from kickoff.models import Participant
from kickoff.textutils import espn_logo_url
from kickoff.web import _event_payload

RAW = "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png"
URL = "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/seasons/2025/teams/1?lang=en&region=us"


def fixture(
    *,
    league="MLB",
    sport="baseball",
    source="mlb",
    season="2025",
    name="Baltimore Orioles",
    short="Orioles",
    identity="110",
):
    event = feeds.make_event(
        source=source,
        league=league,
        sport=sport,
        upstream_id="game",
        season=season,
        title="Source game",
        utc=None,
        day="2025-06-01",
        home=name,
        away=None,
    )
    event.home_participant.participant_id = identity
    event.home_participant.short_name = short
    return event


@pytest.fixture(autouse=True)
def offline_registry(monkeypatch):
    event = fixture()
    key = team_logos.cohort_key(event, event.participants[0])
    monkeypatch.setattr(
        team_logos,
        "logo_registry",
        lambda: ({key: espn_logo_url(RAW)}, {key: {"source_url": URL, "checked_date": "2026-11-02"}}),
    )


def test_fixed_source_image_dimensions_and_strict_round_trip():
    expected = "https://a.espncdn.com/combiner/i?img=%2Fi%2Fteamlogos%2Fmlb%2F500%2Fbal.png&w=56&h=56"
    assert espn_logo_url(RAW) == expected
    assert espn_logo_url(expected) == expected
    for bad in [
        RAW + "?tracking=1",
        RAW.replace("https:", "http:"),
        expected.replace("w=56", "w=500"),
        expected + "&url=https://evil.test",
        "https://a.espncdn.com/i/teamlogos/../private.png",
    ]:
        assert espn_logo_url(bad) is None


def test_daily_registry_is_offline_and_preserves_all_other_facts(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Daily lookup must never request metadata"))
    event = fixture()
    event.home_participant = deepcopy(event.home_participant)
    before = _event_payload(event)
    assert team_logos.enrich_team_logos([event]) is None
    assert event.home_participant == event.participants[0]
    assert event.participants[0].metadata["logo_checked_date"] == "2026-11-02"
    after = _event_payload(event)
    for participant in after["participants"]:
        for key in team_logos.LOGO_FIELDS:
            participant.pop(key, None)
    assert before == after


@pytest.mark.parametrize(
    "changes",
    [
        {"league": "Other"},
        {"source": "espn"},
        {"season": "2024"},
        {"identity": "111"},
        {"name": "Rebranded Orioles"},
        {"short": "New short name"},
    ],
)
def test_missing_or_different_source_identity_keeps_text_without_network(monkeypatch, changes):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Missing cohorts are text"))
    event = fixture(**changes)
    before = deepcopy(event.to_dict())
    assert team_logos.enrich_team_logos([event]) is None
    assert before == event.to_dict()


def test_each_supplied_receipt_wins_and_can_cover_bare_same_cohort(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Supplied images need no requests"))
    earlier = fixture()
    earlier.participants[0].metadata = {
        "logo_url": espn_logo_url(RAW),
        "logo_source_url": URL + "&a=1",
        "logo_checked_date": "2025-11-02",
    }
    later = deepcopy(earlier)
    later.participants[0].metadata.update(logo_source_url=URL + "&a=2", logo_checked_date="2026-11-03")
    bare = fixture()
    before = [deepcopy(event.to_dict()) for event in [earlier, later]]
    team_logos.enrich_team_logos([bare, earlier, later])
    assert [event.to_dict() for event in [earlier, later]] == before
    assert bare.participants[0].metadata == later.participants[0].metadata


def test_individual_sports_and_athletes_do_not_receive_or_publish_team_images(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("No individual image lookups"))
    golf = fixture(sport="golf", league="PGA_TOUR")
    athlete = fixture()
    athlete.participants = [
        Participant(name="Baltimore Orioles", participant_id="110", short_name="Orioles", entity_type="athlete")
    ]
    athlete.home_participant = None
    team_logos.enrich_team_logos([golf, athlete])
    assert not golf.participants[0].metadata and not athlete.participants[0].metadata
    golf.participants[0].metadata.update(
        logo_url=espn_logo_url(RAW), logo_source_url=URL, logo_checked_date="2026-11-03"
    )
    assert "logo_url" not in _event_payload(golf)["participants"][0]


def test_committed_image_list_has_exact_source_receipts_and_unique_valid_keys():
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, f"Duplicate committed key: {key}"
            result[key] = value
        return result

    config = files("kickoff").joinpath("config")
    registry = json.loads(config.joinpath("team_logos.json").read_text(), object_pairs_hook=unique_object)
    receipts = json.loads(config.joinpath("team_logo_receipts.json").read_text(), object_pairs_hook=unique_object)
    assert set(registry) == {"schema_version", "logos"} and registry["schema_version"] == "1"
    assert set(receipts) == {"schema_version", "teams"} and receipts["schema_version"] == "1"
    logos, sources = registry["logos"], receipts["teams"]
    assert logos and logos.keys() == sources.keys()
    for key, logo in logos.items():
        identity = json.loads(key)
        assert isinstance(identity, list) and len(identity) == 6
        league, source, season, participant_id, name, short_name = identity
        assert all(isinstance(value, str) and value for value in (league, source, season, name))
        assert all(value is None or isinstance(value, str) for value in (participant_id, short_name))
        assert key == json.dumps(identity, ensure_ascii=True, separators=(",", ":"))
        assert logo and logo == espn_logo_url(logo)
        receipt = sources[key]
        assert set(receipt) == {"source_url", "checked_date"}
        assert receipt["source_url"].startswith(
            ("https://site.api.espn.com/apis/site/v2/sports/", "https://sports.core.api.espn.com/v2/sports/")
        )
        assert date.fromisoformat(receipt["checked_date"]).isoformat() == receipt["checked_date"]


def test_logo_only_enrichment_adds_espn_source_and_license(monkeypatch, tmp_path):
    from kickoff import open_schedules
    from kickoff.published import publish_sports
    from tests.test_reviewed_schedules import fake_open_read

    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    monkeypatch.setattr(open_schedules, "fill_missing_start_times", lambda *_: [])

    def enrich(events):
        event = next(e for e in events if e.source == "openfootball" and e.participants)
        team_logos._apply(event, event.participants[0], espn_logo_url(RAW), URL, "2026-11-03")
        # No report is returned; attribution must follow actual emitted facts.

    monkeypatch.setattr(open_schedules, "enrich_team_logos", enrich)
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True).read_text())
    assert "espn" in bundle["data_licenses"]
    assert any(source["kind"] == "espn" for source in bundle["sources"])
    publish_sports([bundle], tmp_path / "public")
    enriched = next(event for event in bundle["events"] if any(p.get("logo_url") for p in event["participants"]))
    league_file = next(
        path
        for path in (tmp_path / "public").glob("2026-*.json")
        if any(e["event_id"] == enriched["event_id"] for e in json.loads(path.read_text())["events"])
    )
    public = json.loads(league_file.read_text())
    assert "espn" in public["data_licenses"]
    assert any(source["kind"] == "espn" for source in public["sources"])
