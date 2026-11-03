"""The manually reviewed image list is source-linked; daily lookup stays offline."""

import json
from copy import deepcopy
from datetime import date
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds, team_logos
from kickoff.models import Participant
from kickoff.textutils import espn_logo_url
from kickoff.web import _event_payload

RAW = "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png"
URL = "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/seasons/2025/teams/1?lang=en&region=us"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"Duplicate committed key: {key}"
        result[key] = value
    return result


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
    key = team_logos.team_key(event, event.participants[0])
    monkeypatch.setattr(
        team_logos,
        "logo_registry",
        lambda: {
            event.league: {
                key: {
                    "names": [event.participants[0].name],
                    "logo_url": espn_logo_url(RAW),
                    "source_url": URL,
                    "checked_date": "2026-11-02",
                }
            }
        },
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
        {"identity": "111"},
        {"name": "Rebranded Orioles"},
    ],
)
def test_missing_or_different_source_identity_keeps_text_without_network(monkeypatch, changes):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Missing teams are text"))
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
    later.participants[0].metadata.update(
        logo_url=espn_logo_url(RAW.replace("/500/", "/500/scoreboard/")),
        logo_source_url=URL + "&a=2",
        logo_checked_date="2026-11-03",
    )
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


def test_committed_image_list_has_inline_source_receipts_and_unique_valid_identities():
    config = files("kickoff").joinpath("config")
    registry = json.loads(config.joinpath("team_logos.json").read_text(), object_pairs_hook=unique_object)
    assert set(registry) == {"schema_version", "logos"} and registry["schema_version"] == "2"
    assert not config.joinpath("team_logo_receipts.json").is_file()
    assert registry["logos"]
    for league, teams in registry["logos"].items():
        assert league and teams
        for key, record in teams.items():
            source, kind, identity = key.split(":", 2)
            assert source in {"espn", "openfootball", "mlb", "nhl"} and kind in {"id", "name"} and identity
            assert set(record) == {"names", "logo_url", "source_url", "checked_date"}
            assert record["names"] and all(isinstance(name, str) and name for name in record["names"])
            assert record["names"] == sorted(set(record["names"]))
            if kind == "name":
                assert record["names"] == [identity]
            logo = record["logo_url"]
            assert logo and logo == espn_logo_url(logo)
            assert record["source_url"].startswith(
                ("https://site.api.espn.com/apis/site/v2/sports/", "https://sports.core.api.espn.com/v2/sports/")
            )
            assert date.fromisoformat(record["checked_date"]).isoformat() == record["checked_date"]
            path = parse_qs(urlsplit(logo).query)["img"][0]
            if path.casefold().startswith("/i/teamlogos/countries/"):
                for name in record["names"]:
                    if source == "openfootball" and league == "FIFA_WORLD_CUP":
                        from kickoff.world_cup import TEAM_COUNTRIES

                        country = TEAM_COUNTRIES[name]
                    else:
                        sport = "rugby" if league in feeds.RUGBY_LEAGUES else "soccer"
                        reviewed = feeds._espn_national_teams().get(f"{sport}/{identity}")
                        assert source == "espn" and kind == "id" and reviewed, key
                        country = reviewed["country_code"]
                    participant = Participant(
                        name=name, entity_type="national_team", metadata={"country_code": country}
                    )
                    assert team_logos.participant_logo(participant, logo) == logo


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


COUNTRY_RAW = "https://a.espncdn.com/i/teamlogos/countries/500/can.png"


@pytest.fixture
def audited_country_image(monkeypatch):
    monkeypatch.setattr(
        team_logos,
        "country_images",
        lambda: {
            "/i/teamlogos/countries/500/can.png": {
                "country_code": "CA",
                "source_url": "https://example.test/audited-canadian-image",
                "checked_date": "2026-11-03",
            }
        },
    )


@pytest.mark.parametrize(
    "entity,country,receipt,allowed",
    [
        ("team", "CA", True, False),
        ("club", "CA", True, False),
        ("national_team", "CA", True, True),
        ("national_team", "NZ", True, False),
        ("national_team", None, True, False),
        ("national_team", "CA", False, True),
    ],
)
def test_country_assets_require_independent_national_identity_and_audited_match(
    audited_country_image, entity, country, receipt, allowed
):
    participant = Participant(
        name="Source team name",
        entity_type=entity,
        metadata={
            "country_code": country,
            **(
                {"country_source_url": "https://example.test/country", "country_checked_date": "2026-11-01"}
                if receipt
                else {}
            ),
        },
    )
    assert team_logos.participant_logo(participant, COUNTRY_RAW) == (espn_logo_url(COUNTRY_RAW) if allowed else None)
    assert team_logos.participant_logo(participant, RAW) == espn_logo_url(RAW)


def test_unknown_country_asset_never_infers_country_from_its_filename(audited_country_image):
    participant = Participant(
        name="Canada",
        entity_type="national_team",
        metadata={
            "country_code": "CA",
            "country_source_url": "https://example.test/country",
            "country_checked_date": "2026-11-01",
        },
    )
    assert team_logos.participant_logo(participant, COUNTRY_RAW.replace("can.png", "canada.png")) is None
    assert team_logos.participant_logo(participant, COUNTRY_RAW.replace("countries/", "COUNTRIES/")) is None


def test_unsafe_supplied_country_image_is_removed_from_both_sides_and_falls_back(audited_country_image):
    event = fixture()
    event.participants[0].metadata = {
        "logo_url": espn_logo_url(COUNTRY_RAW),
        "logo_source_url": URL,
        "logo_checked_date": "2026-11-03",
        "other_fact": "retain",
    }
    event.home_participant = deepcopy(event.participants[0])
    team_logos.enrich_team_logos([event])
    assert event.participants[0] == event.home_participant
    assert event.participants[0].metadata["logo_url"] == espn_logo_url(RAW)
    assert event.participants[0].metadata["logo_checked_date"] == "2026-11-02"
    assert event.participants[0].metadata["other_fact"] == "retain"


def test_unsafe_country_image_cannot_leak_through_export_without_enrichment(audited_country_image):
    event = fixture(name="Canterbury", identity="other")
    event.participants[0].metadata = {
        "logo_url": espn_logo_url(COUNTRY_RAW),
        "logo_source_url": URL,
        "logo_checked_date": "2026-11-03",
        "country_code": "NZ",
    }
    event.home_participant = deepcopy(event.participants[0])
    before = deepcopy(event.to_dict())
    assert "logo_url" not in _event_payload(event)["participants"][0]
    team_logos.enrich_team_logos([event])
    for target in [event.participants[0], event.home_participant]:
        assert all(field not in target.metadata for field in team_logos.LOGO_FIELDS)
        assert target.metadata["country_code"] == "NZ"
    after = event.to_dict()
    for collection in [before["participants"], [before["home_participant"]]]:
        for participant in collection:
            for field in team_logos.LOGO_FIELDS:
                participant["metadata"].pop(field)
    assert after == before


def test_reviewed_national_identity_precedes_source_image_selection(monkeypatch, audited_country_image):
    event = fixture(name="Canada", sport="rugby", league="SIX_NATIONS", source="espn", identity="11")
    event.facts_checked_date = "2026-11-03"
    monkeypatch.setattr(
        feeds,
        "_espn_national_teams",
        lambda: {
            "rugby/11": {
                "country_code": "CA",
                "source_url": "https://example.test/independent-country",
                "checked_date": "2026-11-01",
            }
        },
    )
    feeds._espn_participants(
        event, [{"homeAway": "home", "team": {"id": "11", "displayName": "Canada", "logo": COUNTRY_RAW}}], False, URL
    )
    participant = event.participants[0]
    assert participant.entity_type == "national_team" and participant.metadata["country_code"] == "CA"
    assert participant.metadata["logo_url"] == espn_logo_url(COUNTRY_RAW)
    assert _event_payload(event)["participants"][0]["logo_url"] == espn_logo_url(COUNTRY_RAW)


def test_committed_country_asset_mapping_has_explicit_sourced_country_facts():
    from kickoff.web import NATIONAL_COUNTRY_CODES

    payload = json.loads(
        files("kickoff").joinpath("config/espn-country-images.json").read_text(), object_pairs_hook=unique_object
    )
    assert set(payload) == {"assets"}
    assert payload["assets"]
    for path, row in payload["assets"].items():
        assert set(row) == {"country_code", "source_url", "checked_date"}
        assert path.startswith("/i/teamlogos/countries/")
        assert espn_logo_url("https://a.espncdn.com" + path)
        assert row["country_code"] in NATIONAL_COUNTRY_CODES
        assert row["source_url"].startswith("https://")
        assert date.fromisoformat(row["checked_date"]).isoformat() == row["checked_date"]


def test_reviewed_world_cup_country_identity_needs_no_extra_metadata(monkeypatch, audited_country_image):
    from tests.test_world_cup import parse

    event = parse(team1="Canada")
    participant = event.participants[0]
    assert participant.entity_type == "national_team" and participant.metadata == {"country_code": "CA"}
    before = _event_payload(event)
    key = team_logos.team_key(event, participant)
    monkeypatch.setattr(
        team_logos,
        "logo_registry",
        lambda: {
            event.league: {
                key: {
                    "names": [participant.name],
                    "logo_url": espn_logo_url(COUNTRY_RAW),
                    "source_url": URL,
                    "checked_date": "2026-11-03",
                }
            }
        },
    )
    team_logos.enrich_team_logos([event])
    after = _event_payload(event)
    assert after["participants"][0]["logo_url"] == espn_logo_url(COUNTRY_RAW)
    for field in team_logos.LOGO_FIELDS:
        after["participants"][0].pop(field)
    assert before == after


def test_raw_source_national_hint_cannot_promote_unreviewed_identity(monkeypatch, audited_country_image):
    event = fixture(name="Canada", sport="rugby", league="RUGBY_TESTS", source="espn", identity="unreviewed")
    event.facts_checked_date = "2026-11-03"
    monkeypatch.setattr(feeds, "_espn_national_teams", lambda: {})
    feeds._espn_participants(
        event,
        [
            {
                "homeAway": "home",
                "team": {
                    "id": "unreviewed",
                    "displayName": "Canada",
                    "isNational": True,
                    "country": {"abbreviation": "CA"},
                    "logo": COUNTRY_RAW,
                },
            }
        ],
        False,
        URL,
    )
    participant = event.participants[0]
    assert participant.entity_type == "team" and not participant.metadata
    assert "logo_url" not in _event_payload(event)["participants"][0]


@pytest.mark.parametrize(
    "identity,name,asset,country",
    [
        ("25933", "Canterbury", "can", None),
        ("25942", "Northland", "nor", None),
        ("25920", "Perpignan", "usa", None),
        ("25940", "Manawatu", "man", None),
        ("289337", "Vannes", "van", None),
        ("289482", "Austria", "aus", "AT"),
        ("289551", "Slovakia", "slo", "SK"),
        ("289268", "Hong Kong", "hon", "HK"),
        ("289432", "Montenegro", "mon", "ME"),
    ],
)
def test_audited_collisions_are_blocked_at_ingestion_enrichment_and_export(monkeypatch, identity, name, asset, country):
    event = fixture(name=name, sport="rugby", league="RUGBY_TESTS", source="espn", identity=identity)
    event.facts_checked_date = "2026-11-03"
    unsafe = f"https://a.espncdn.com/i/teamlogos/countries/500/{asset}.png"
    feeds._espn_participants(
        event,
        [{"homeAway": "home", "score": "17", "team": {"id": identity, "displayName": name, "logo": unsafe}}],
        True,
        URL,
    )
    participant = event.participants[0]
    assert participant.entity_type == ("national_team" if country else "team")
    assert participant.metadata.get("country_code") == country
    assert "logo_url" not in participant.metadata
    before = _event_payload(event)
    participant.metadata.update(logo_url=espn_logo_url(unsafe), logo_source_url=URL, logo_checked_date="2026-11-03")
    event.home_participant = deepcopy(participant)
    assert _event_payload(event) == before  # Also safe with enrich_times=False.
    monkeypatch.setattr(team_logos, "logo_registry", lambda: {})
    team_logos.enrich_team_logos([event])
    assert event.home_participant == participant
    assert _event_payload(event) == before
    assert all(field not in participant.metadata for field in team_logos.LOGO_FIELDS)
    assert participant.final_score == 17


def test_audited_slovenia_image_remains_available():
    event = fixture(name="Slovenia", sport="rugby", league="RUGBY_TESTS", source="espn", identity="289427")
    event.facts_checked_date = "2026-11-03"
    raw = "https://a.espncdn.com/i/teamlogos/countries/500/slo.png"
    feeds._espn_participants(
        event, [{"homeAway": "home", "team": {"id": "289427", "displayName": "Slovenia", "logo": raw}}], False, URL
    )
    public = _event_payload(event)["participants"][0]
    assert public["country_code"] == "SI" and public["logo_url"] == espn_logo_url(raw)


@pytest.mark.parametrize(
    "changes", [{"season": "2028"}, {"short": "New short name"}, {"season": "2028", "short": None}]
)
def test_reviewed_team_keeps_logo_across_seasons_and_short_name_changes(monkeypatch, changes):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Registry lookup is offline"))
    event = fixture(**changes)
    before = _event_payload(event)
    team_logos.enrich_team_logos([event])
    after = _event_payload(event)
    assert after["participants"][0]["logo_url"] == espn_logo_url(RAW)
    assert after["participants"][0]["logo_source_url"] == URL
    assert after["participants"][0]["logo_checked_date"] == "2026-11-02"
    for field in team_logos.LOGO_FIELDS:
        after["participants"][0].pop(field)
    assert after == before


def test_no_id_lookup_requires_the_exact_source_name_and_never_backs_up_an_id(monkeypatch):
    event = fixture(identity=None)
    key = team_logos.team_key(event, event.participants[0])
    assert key == "mlb:name:Baltimore Orioles"
    monkeypatch.setattr(
        team_logos,
        "logo_registry",
        lambda: {
            "MLB": {
                key: {
                    "names": ["Baltimore Orioles"],
                    "logo_url": espn_logo_url(RAW),
                    "source_url": URL,
                    "checked_date": "2026-11-02",
                }
            }
        },
    )
    changed = fixture(identity=None, name="baltimore Orioles")
    other_source = fixture(identity=None, source="espn")
    with_id = fixture()
    team_logos.enrich_team_logos([event, changed, other_source, with_id])
    assert event.participants[0].metadata["logo_url"] == espn_logo_url(RAW)
    assert all(not row.participants[0].metadata for row in [changed, other_source, with_id])


@pytest.mark.parametrize("changes", [{"season": "2026"}, {"name": "Rebranded Orioles"}, {"short": "Changed short"}])
def test_supplied_image_sharing_retains_season_and_exact_source_cohort_boundaries(monkeypatch, changes):
    monkeypatch.setattr(team_logos, "logo_registry", lambda: {})
    supplied = fixture()
    supplied.participants[0].metadata.update(
        logo_url=espn_logo_url(RAW), logo_source_url=URL, logo_checked_date="2026-11-02"
    )
    same = fixture()
    different = fixture(**changes)
    team_logos.enrich_team_logos([supplied, same, different])
    assert same.participants[0].metadata == supplied.participants[0].metadata
    assert different.participants[0].metadata == {}


@pytest.mark.parametrize(
    "identity,name",
    [
        ("112646", "DC Defenders"),
        ("112647", "Dallas Renegades"),
        ("126073", "Birmingham Stallions"),
        ("126075", "Houston Gamblers"),
    ],
)
def test_conflicting_ufl_branding_has_no_registry_fallback_but_keeps_own_image(monkeypatch, identity, name):
    registry = json.loads(files("kickoff").joinpath("config/team_logos.json").read_text())["logos"]
    assert f"espn:id:{identity}" not in registry["UFL"]
    monkeypatch.setattr(team_logos, "logo_registry", lambda: registry)
    event = fixture(league="UFL", sport="football", source="espn", identity=identity, name=name)
    team_logos.enrich_team_logos([event])
    assert event.participants[0].metadata == {}
    logo = espn_logo_url("https://a.espncdn.com/i/teamlogos/ufl/500/scoreboard/dc.png")
    event.participants[0].metadata.update(logo_url=logo, logo_source_url=URL, logo_checked_date="2026-11-02")
    before = deepcopy(event.to_dict())
    team_logos.enrich_team_logos([event])
    assert event.to_dict() == before


def test_id_lookup_accepts_only_reviewed_exact_full_names_not_short_name_variants(monkeypatch):
    event = fixture()
    key = team_logos.team_key(event, event.participants[0])
    monkeypatch.setattr(
        team_logos,
        "logo_registry",
        lambda: {
            "MLB": {
                key: {
                    "names": ["Baltimore Orioles", "Reviewed source name"],
                    "logo_url": espn_logo_url(RAW),
                    "source_url": URL,
                    "checked_date": "2026-11-02",
                }
            }
        },
    )
    reviewed = fixture(name="Reviewed source name", short="New short name", season="2028")
    punctuation = fixture(name="Reviewed-source name")
    short_only = fixture(name="Unreviewed name", short="Reviewed source name")
    team_logos.enrich_team_logos([reviewed, punctuation, short_only])
    assert reviewed.participants[0].metadata["logo_url"] == espn_logo_url(RAW)
    assert punctuation.participants[0].metadata == short_only.participants[0].metadata == {}
