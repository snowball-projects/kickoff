"""Offline identity, season and optional-image contracts; no guessed team IDs."""

from copy import deepcopy
from dataclasses import replace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds, team_logos
from kickoff.models import Participant
from kickoff.textutils import espn_logo_url
from kickoff.web import _event_payload

RAW = "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png"


@pytest.fixture(autouse=True)
def clear_metadata_caches():
    for function in (
        team_logos._optional_json,
        team_logos._core_team,
        team_logos._season_teams,
        team_logos._name_index,
    ):
        function.cache_clear()

    yield
    for function in (
        team_logos._optional_json,
        team_logos._core_team,
        team_logos._season_teams,
        team_logos._name_index,
    ):
        function.cache_clear()


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
        expected.replace("%2Fi%2Fteamlogos%2Fmlb%2F500%2Fbal.png", "https%3A%2F%2Fevil.test%2Fa.png"),
    ]:
        assert espn_logo_url(bad) is None


@pytest.mark.parametrize(
    "league,source,season,expected",
    [
        ("EPL", "openfootball", "2024-25", 2024),
        ("EPL", "openfootball", "2026-27", 2026),
        ("NHL", "nhl", "20242025", 2025),
        ("MLB", "mlb", "2025", 2025),
    ],
)
def test_actual_competition_season_not_calendar_bundle_year(league, source, season, expected):
    assert team_logos.competition_season(fixture(league=league, source=source, season=season)) == expected


def roster(monkeypatch, *, teams, pages=1):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/teams"):
            page = int(query.get("page", ["1"])[0])
            subset = teams if pages == 1 else teams[page - 1 : page]
            return {
                "count": len(teams),
                "pageCount": pages,
                "items": [
                    {"$ref": f"http://sports.core.api.espn.com{parsed.path}/{team['id']}?lang=en&region=us"}
                    for team in subset
                ],
            }
        identity = parsed.path.rsplit("/", 1)[-1]
        return next((team for team in teams if team["id"] == identity), None)

    monkeypatch.setattr(feeds, "get_json", get)
    return calls


def test_name_matching_uses_every_core_page_and_source_short_names(monkeypatch):
    calls = roster(
        monkeypatch,
        teams=[
            {"id": "1", "displayName": "Other Team", "logos": []},
            {"id": "2", "displayName": "Baltimore Orioles", "shortDisplayName": "Orioles", "logos": [{"href": RAW}]},
        ],
        pages=2,
    )
    event = fixture(name="Original source spelling", short="Orioles")
    before = deepcopy(_event_payload(event))
    (observation,) = team_logos.enrich_team_logos([event])
    assert observation["status"] == "logo"
    assert observation["participant_id"] == "110"  # Official source ID is never replaced by ESPN's2.
    assert any("page=2" in url for url in calls)
    assert all("/seasons/2025/teams" in url for url in calls)
    assert event.home_participant.entity_type == "team" and "country_code" not in event.home_participant.metadata
    after = _event_payload(event)
    for participant in after["participants"]:
        for key in team_logos.LOGO_FIELDS:
            participant.pop(key, None)
    assert after == before
    assert event.home_participant.metadata["logo_source_url"].endswith("/teams/2?lang=en&region=us")


def test_ambiguous_or_unmatched_names_never_guess_a_logo(monkeypatch):
    roster(
        monkeypatch,
        teams=[
            {"id": "1", "displayName": "United", "logos": [{"href": RAW}]},
            {"id": "2", "displayName": "United", "logos": [{"href": RAW}]},
        ],
    )
    events = [fixture(name="United", short=None), fixture(name="Some FC", short=None)]
    observations = team_logos.enrich_team_logos(events)
    assert {row["status"] for row in observations} == {"ambiguous_name", "unmatched_name"}
    assert all("logo_url" not in p.metadata for event in events for p in event.participants)


def test_non_espn_names_do_not_use_an_external_participant_id_as_espn_id(monkeypatch):
    calls = roster(monkeypatch, teams=[{"id": "999", "displayName": "Some Other Team", "logos": [{"href": RAW}]}])
    event = fixture(name="Baltimore Orioles", short="Orioles", identity="999")
    assert team_logos.enrich_team_logos([event])[0]["status"] == "unmatched_name"
    assert "logo_url" not in event.home_participant.metadata
    assert calls


def test_historical_direct_id_uses_its_season_image_without_current_rebrand(monkeypatch):
    old = "https://a.espncdn.com/guid/6381f392-8ff3-3be9-af92-3beeaa1361ef/logos/default.png"
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        assert "/seasons/2025/teams/126075" in url
        return {"id": "126075", "displayName": "Houston Roughnecks", "logos": [{"href": old}]}

    monkeypatch.setattr(feeds, "get_json", get)
    event = fixture(
        league="UFL", sport="football", source="espn", name="Houston Roughnecks", short="Roughnecks", identity="126075"
    )
    team_logos.enrich_team_logos([event, event])
    assert len(calls) == 1
    assert event.home_participant.metadata["logo_url"] == espn_logo_url(old)


def test_scoreboard_images_need_no_metadata_request_or_nationality_guess(monkeypatch):
    monkeypatch.setattr(
        feeds, "get_json", lambda *a, **k: pytest.fail("Supplied source image must avoid metadata lookup")
    )
    event = fixture(league="NFL", sport="football", source="espn", identity="1")
    event.home_participant.metadata = {
        "logo_url": espn_logo_url(RAW),
        "logo_source_url": f"{feeds.ESPN}/football/nfl/scoreboard?week=1",
        "logo_checked_date": "2026-11-03",
    }
    assert team_logos.enrich_team_logos([event])[0]["status"] == "logo"
    assert event.home_participant.entity_type == "team" and "country_code" not in event.home_participant.metadata


def test_optional_metadata_failure_preserves_schedule_and_caches_request(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        raise HTTPError(url, 503, "Unavailable", None, None)

    monkeypatch.setattr(feeds, "get_json", get)
    event = fixture()
    before = deepcopy(event.to_dict())
    result = team_logos.enrich_team_logos([event, replace(event, event_id="second")])
    assert len(calls) == 1
    assert result[0]["status"] == "unavailable_metadata"
    assert event.to_dict() == before


def test_identified_team_without_an_image_is_distinct_from_name_mismatch(monkeypatch):
    roster(monkeypatch, teams=[{"id": "1", "displayName": "Baltimore Orioles", "logos": []}])
    assert team_logos.enrich_team_logos([fixture()])[0]["status"] == "missing_image"


def test_no_image_lookup_for_individual_sports_or_unmapped_cricket(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("No invented league or team IDs"))
    individual = fixture(league="PGA_TOUR", sport="golf")
    individual.participants = [Participant(name="Individual player", entity_type="athlete")]
    cricket = fixture(league="IPL", sport="cricket", source="wikipedia", name="Named cricket team", identity=None)
    cricket.home_participant.role = None
    cricket.home_participant = None
    before = [deepcopy(event.to_dict()) for event in [individual, cricket]]
    assert team_logos.enrich_team_logos([individual, cricket])[0]["status"] == "unsupported_league"
    assert [event.to_dict() for event in [individual, cricket]] == before


def test_separate_internal_side_objects_receive_only_the_same_logo_metadata(monkeypatch):
    roster(monkeypatch, teams=[{"id": "1", "displayName": "Baltimore Orioles", "logos": [{"href": RAW}]}])
    event = fixture()
    event.home_participant = deepcopy(event.home_participant)
    team_logos.enrich_team_logos([event])
    assert event.home_participant == event.participants[0]
    public = _event_payload(event)
    assert "home_participant" not in public and "away_participant" not in public
    assert public["participants"][0]["logo_url"] == espn_logo_url(RAW)
    assert public["participants"][0]["logo_checked_date"]


def test_individual_image_metadata_cannot_cross_public_boundary():
    event = fixture(league="PGA_TOUR", sport="golf")
    event.home_participant.metadata = {
        "logo_url": RAW,
        "logo_source_url": f"{feeds.ESPN}/golf/pga/scoreboard",
        "logo_checked_date": "2026-11-03",
    }
    assert "logo_url" not in _event_payload(event)["participants"][0]
    from kickoff.web import _participant_payload

    event.home_participant.entity_type = "athlete"
    assert "logo_url" not in _participant_payload(event.home_participant)


def test_one_supplied_scoreboard_image_covers_its_identical_source_cohort(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Use the same identified source team image"))
    bare = fixture(league="NFL", sport="football", source="espn", identity="1")
    supplied = deepcopy(bare)
    supplied.event_id = "other-game"
    supplied.home_participant.metadata = {
        "logo_url": espn_logo_url(RAW),
        "logo_source_url": f"{feeds.ESPN}/football/nfl/scoreboard",
        "logo_checked_date": "2026-11-02",
    }
    team_logos.enrich_team_logos([bare, supplied])
    assert bare.home_participant.metadata == supplied.home_participant.metadata
    assert bare.home_participant.metadata["logo_checked_date"] == "2026-11-02"


def test_current_fallback_cannot_match_a_rebrand_only_by_short_name(monkeypatch):
    def get(url, **kwargs):
        if "sports.core.api.espn.com" in url:
            return {"id": "112647", "displayName": "Arlington Renegades", "shortDisplayName": "Renegades", "logos": []}
        return {
            "team": {
                "id": "112647",
                "displayName": "Dallas Renegades",
                "shortDisplayName": "Renegades",
                "logos": [{"href": RAW}],
            }
        }

    monkeypatch.setattr(feeds, "get_json", get)
    participant = Participant(name="Arlington Renegades", short_name="Renegades", participant_id="112647")
    match, _ = team_logos._by_source_id("football/ufl", 2025, participant)
    assert match is not None and team_logos.source_logo(match[0]) is None


def test_logo_only_enrichment_adds_espn_source_and_license(monkeypatch, tmp_path):
    import json

    from kickoff import open_schedules
    from tests.test_reviewed_schedules import fake_open_read

    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    monkeypatch.setattr(open_schedules, "fill_missing_start_times", lambda *_: [])

    def enrich(events):
        event = next(e for e in events if e.source == "openfootball" and e.participants)
        team_logos._apply(
            event,
            event.participants[0],
            espn_logo_url(RAW),
            f"{team_logos.CORE}/soccer/leagues/eng.1/seasons/2026/teams/1",
            "2026-11-03",
        )
        return [{"logo_url": espn_logo_url(RAW)}]

    monkeypatch.setattr(open_schedules, "enrich_team_logos", enrich)
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True).read_text())
    assert "espn" in bundle["data_licenses"]
    assert any(source["kind"] == "espn" for source in bundle["sources"])


def test_supplied_images_and_their_historical_receipts_take_priority_over_cohort_reuse(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Each event already has its own source image"))
    earlier = fixture(league="NFL", sport="football", source="espn", identity="1")
    earlier.home_participant.metadata = {
        "logo_url": espn_logo_url(RAW),
        "logo_source_url": f"{feeds.ESPN}/football/nfl/scoreboard?week=1",
        "logo_checked_date": "2026-11-02",
    }
    later = deepcopy(earlier)
    later.event_id = "later-game"
    later.home_participant.metadata = {
        "logo_url": espn_logo_url(RAW.replace("bal.png", "other.png")),
        "logo_source_url": f"{feeds.ESPN}/football/nfl/scoreboard?week=2",
        "logo_checked_date": "2026-11-03",
    }
    expected = [deepcopy(e.to_dict()) for e in [earlier, later]]
    team_logos.enrich_team_logos([earlier, later])
    assert [e.to_dict() for e in [earlier, later]] == expected
