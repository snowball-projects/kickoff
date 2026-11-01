"""Reviewed country identities cross the public boundary without guessing club flags."""

import json

import pytest

from kickoff import feeds
from kickoff.countries import venue_country
from kickoff.models import Participant
from kickoff.open_schedules import refresh_open_schedules
from kickoff.published import publish_sports
from kickoff.web import _event_payload, _participant_payload
from tests.test_reviewed_schedules import ROOT, fake_open_read


def match(sport, identity, name):
    return feeds._espn_event(
        {
            "id": "identity-test",
            "name": f"{name} vs Opponent",
            "date": "2026-11-01T15:00:00Z",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "team": {"id": identity, "displayName": name}},
                        {"homeAway": "away", "team": {"id": "unreviewed", "displayName": "Opponent"}},
                    ]
                }
            ],
        },
        sport=sport,
        league="SIX_NATIONS" if sport == "rugby" else "UEFA_NATIONS_LEAGUE",
        zone=feeds.EASTERN,
        fallback_url="https://www.espn.com/",
    )


@pytest.mark.parametrize(
    "sport,identity,name,code",
    [
        ("rugby", "4", "Wales", "GB-WLS"),
        ("rugby", "289246", "Wales Women", "GB-WLS"),
        ("soccer", "586", "Northern Ireland", "GB-NIR"),
        ("soccer", "18272", "Kosovo", "XK"),
        ("soccer", "448", "England", "GB-ENG"),
        ("soccer", "580", "Scotland", "GB-SCT"),
    ],
)
def test_reviewed_core_identity_preserves_name_and_source_provenance(sport, identity, name, code):
    event = match(sport, identity, name)
    participant = _event_payload(event)["home_participant"]
    assert participant["name"] == name and participant["participant_id"] == identity
    assert participant["entity_type"] == "national_team" and participant["country_code"] == code
    assert participant["country_source_url"].startswith(f"https://sports.core.api.espn.com/v2/sports/{sport}/")
    assert f"/teams/{identity}?" in participant["country_source_url"]
    assert participant["country_checked_date"] == "2026-11-01"
    assert participant["country_source_kind"] == "espn"
    assert _event_payload(event)["participants"][0] == participant
    assert _event_payload(event)["away_participant"]["entity_type"] == "team"


@pytest.mark.parametrize(
    "sport,identity,name",
    [
        ("rugby", "32", "British and Irish Lions"),
        ("rugby", "25893", "Western Force"),
        ("rugby", "1-not-reviewed", "England"),
        ("football", "4", "Wales"),
        ("soccer", "4", "Wales"),
    ],
)
def test_names_logos_or_another_sports_ids_never_classify_unreviewed_teams(sport, identity, name):
    participant = _participant_payload(match(sport, identity, name).home_participant)
    assert participant["entity_type"] == "team"
    assert not {key for key in participant if key.startswith("country_")}


def test_only_reviewed_country_fields_publish_and_venue_subdivisions_stay_separate():
    for code in ("ZZ", "XX", "GB-ABC", "Wales", None):
        participant = _participant_payload(
            Participant(
                name="Unknown",
                entity_type="national_team",
                metadata={
                    "country_code": code,
                    "country_source_url": "private",
                    "private": "secret",
                },
            )
        )
        assert "country_code" not in participant and "country_source_url" not in participant
        assert "secret" not in json.dumps(participant)
    for name in ("England", "Scotland", "Wales", "Northern Ireland"):
        assert venue_country(name) == "GB"


@pytest.mark.parametrize(
    "identity,name,code,kind",
    [
        ("289268", "Hong Kong", "HK", "world_rugby"),
        ("289555", "Samoa Women", "WS", "rugby_world_cup"),
        ("289340", "Scotland Women", "GB-SCT", "rugby_world_cup"),
        ("289550", "Estonia", "EE", "rugby_europe"),
    ],
)
def test_official_positive_country_identity_keeps_conflicting_core_fact_private(identity, name, code, kind):
    reviewed = feeds._espn_national_teams()[f"rugby/{identity}"]
    assert reviewed["conflicting_core_metadata"]["isNational"] is False
    participant = _participant_payload(match("rugby", identity, name).home_participant)
    assert participant["name"] == name and participant["entity_type"] == "national_team"
    assert participant["country_code"] == code and participant["country_source_kind"] == kind
    assert participant["country_source_url"] == reviewed["source_url"]
    assert "conflicting_core_metadata" not in participant and "source_sha256" not in participant


def test_official_identity_attribution_survives_collector_and_sport_split(monkeypatch, tmp_path):
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    monkeypatch.setattr(feeds, "get_json", lambda _: {"events": []})
    source_event = match("rugby", "289268", "Hong Kong")
    bundle = json.loads(
        refresh_open_schedules(
            2026,
            tmp_path / "bundles",
            ROOT / "data/reviewed",
            feeds={"SIX_NATIONS": ("espn", lambda _: [source_event])},
        ).read_text()
    )
    manifest = json.loads(publish_sports([bundle], tmp_path / "published").read_text())
    notice = next(source for source in bundle["sources"] if source["kind"] == "world_rugby")
    assert notice["license"] == "Identity facts; no open data license granted"
    assert notice["license_url"] == "https://www.world.rugby/terms-and-conditions"
    assert notice in manifest["seasons"]["2026"]["sources"]
    rugby = json.loads((tmp_path / "published/2026-rugby.json").read_text())
    assert notice in rugby["sources"] and rugby["data_licenses"]["world_rugby"] == notice["license"]
    assert rugby["events"][0]["home_participant"]["country_source_url"] == notice["url"]
    for path in (tmp_path / "published").glob("2026-*.json"):
        if path.name != "2026-rugby.json":
            assert all(source["kind"] != "world_rugby" for source in json.loads(path.read_text())["sources"])
