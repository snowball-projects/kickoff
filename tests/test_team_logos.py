"""Daily image lookup is offline; weekly candidates are complete and source-linked."""

import json
from copy import deepcopy
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds, team_logos
from kickoff import team_logo_refresh as weekly
from kickoff.textutils import espn_logo_url
from kickoff.web import _event_payload

RAW = "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png"
URL = f"{weekly.CORE}/baseball/leagues/mlb/seasons/2025/teams/1?lang=en&region=us"


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


def pair(event=None, *, logo=True):
    row = team_logos.cohort(event or fixture(), (event or fixture()).participants[0])
    key = team_logos.cohort_key(row)
    return (
        {"schema_version": "1", "logos": {key: espn_logo_url(RAW)} if logo else {}},
        {
            "schema_version": "1",
            "teams": {
                key: {
                    **row,
                    "status": "logo" if logo else "missing_image",
                    "source_url": URL,
                    "checked_date": "2026-11-02",
                }
            },
        },
    )


@pytest.fixture(autouse=True)
def offline_registry(monkeypatch):
    registry, receipts = pair()
    monkeypatch.setattr(team_logos, "logo_registry", lambda: (registry["logos"], receipts["teams"]))


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


@pytest.mark.parametrize(
    "league,season,expected",
    [("EPL", "2024-25", 2024), ("NHL", "20242025", 2025), ("MLB", "2025", 2025), ("EPL", "2026-29", None)],
)
def test_true_competition_season(league, season, expected):
    assert team_logos.competition_season(fixture(league=league, season=season)) == expected


def test_daily_registry_is_offline_and_preserves_all_other_facts(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Daily lookup must never request metadata"))
    event = fixture()
    event.home_participant = deepcopy(event.home_participant)
    before = _event_payload(event)
    (result,) = team_logos.enrich_team_logos([event])
    assert result["status"] == "logo"
    assert event.home_participant == event.participants[0]
    assert event.participants[0].metadata["logo_checked_date"] == "2026-11-02"
    after = _event_payload(event)
    for participant in after["participants"]:
        for key in team_logos.LOGO_FIELDS:
            participant.pop(key, None)
    assert before == after


def test_missing_registry_cohort_keeps_text_without_network(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Missing cohorts are text"))
    event = fixture(name="New identity")
    before = deepcopy(event.to_dict())
    assert team_logos.enrich_team_logos([event])[0]["status"] == "unregistered"
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


def roster(monkeypatch, teams, *, pages=1):
    calls = []

    def get(url):
        calls.append(url)
        parsed = urlsplit(url)
        if parsed.path.endswith("/teams"):
            page = int(parse_qs(parsed.query).get("page", ["1"])[0])
            rows = teams if pages == 1 else teams[page - 1 : page]
            return {
                "count": len(teams),
                "pageCount": pages,
                "pageIndex": page,
                "items": [{"$ref": f"http://sports.core.api.espn.com{parsed.path}/{row['id']}"} for row in rows],
            }
        identity = parsed.path.rsplit("/", 1)[-1]
        return next(row for row in teams if row["id"] == identity)

    monkeypatch.setattr(weekly, "fetch_json", get)
    return calls


def test_weekly_resolves_every_page_and_unique_short_name(monkeypatch):
    calls = roster(
        monkeypatch,
        [
            {"id": "1", "displayName": "Other", "logos": []},
            {"id": "2", "displayName": "Baltimore Orioles", "shortDisplayName": "Orioles", "logos": [{"href": RAW}]},
        ],
        pages=2,
    )
    event = fixture(name="Original source spelling")
    logo, source, status = weekly.Resolver().resolve(team_logos.cohort(event, event.participants[0]))
    assert status == "logo" and logo == espn_logo_url(RAW)
    assert source.endswith("/teams/2?lang=en&region=us")
    assert any("page=2" in url for url in calls)
    assert all("/seasons/2025/teams" in url for url in calls)


def test_weekly_ambiguous_and_unmatched_names_never_guess(monkeypatch):
    roster(
        monkeypatch,
        [
            {"id": "1", "displayName": "United", "logos": [{"href": RAW}]},
            {"id": "2", "displayName": "United", "logos": [{"href": RAW}]},
        ],
    )
    resolver = weekly.Resolver()
    for name, expected in [("United", "ambiguous_name"), ("Some FC", "unmatched_name")]:
        event = fixture(name=name, short=None)
        assert resolver.resolve(team_logos.cohort(event, event.participants[0]))[2] == expected


def test_historical_id_image_and_rebrand_names(monkeypatch):
    event = fixture(source="espn", identity="1", name="Original Franchise", short="Franchise")
    row = team_logos.cohort(event, event.participants[0])

    def get(url):
        if url.startswith(weekly.CORE):
            return {"id": "1", "displayName": "Original Franchise", "logos": []}
        return {
            "team": {
                "id": "1",
                "displayName": "New Franchise",
                "shortDisplayName": "Franchise",
                "logos": [{"href": RAW}],
            }
        }

    monkeypatch.setattr(weekly, "fetch_json", get)
    assert weekly.Resolver().resolve(row)[::2] == (None, "missing_image")
    monkeypatch.setattr(
        weekly, "fetch_json", lambda url: {"id": "1", "displayName": "Original Franchise", "logos": [{"href": RAW}]}
    )
    assert weekly.Resolver().resolve(row)[0] == espn_logo_url(RAW)


@pytest.mark.parametrize(
    "payload", [[], {}, {"id": "1", "logos": []}, {"id": "1", "displayName": "Orioles", "logos": [None]}]
)
def test_weekly_malformed_team_is_failure(payload):
    with pytest.raises((ValueError, AttributeError)):
        weekly._team(payload, "1", URL)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout"),
        HTTPError(URL, 503, "offline", None, None),
        EOFError("truncated"),
        ValueError("invalid JSON"),
    ],
)
def test_weekly_failure_leaves_both_old_files_unchanged(monkeypatch, tmp_path, error):
    first, second = tmp_path / "logos.json", tmp_path / "receipts.json"
    first.write_text("old registry")
    second.write_text("old receipts")
    row = team_logos.cohort(fixture(), fixture().participants[0])
    monkeypatch.setattr(weekly, "published_cohorts", lambda _: {team_logos.cohort_key(row): row})
    monkeypatch.setattr(weekly.Resolver, "resolve", lambda *_: (_ for _ in ()).throw(error))
    with pytest.raises(type(error)):
        weekly.refresh_team_logos(first, second)
    assert first.read_text() == "old registry" and second.read_text() == "old receipts"


def test_partial_weekly_success_and_incomplete_pagination_never_write(monkeypatch, tmp_path):
    rows = [team_logos.cohort(fixture(name=name), fixture(name=name).participants[0]) for name in ["A", "B"]]
    monkeypatch.setattr(weekly, "published_cohorts", lambda _: {team_logos.cohort_key(row): row for row in rows})

    def resolve(self, row):
        if row["name"] == "B":
            raise ValueError("incomplete response")
        return espn_logo_url(RAW), URL, "logo"

    monkeypatch.setattr(weekly.Resolver, "resolve", resolve)
    first, second = tmp_path / "a", tmp_path / "b"
    first.write_text("original")
    second.write_text("original")
    with pytest.raises(ValueError):
        weekly.refresh_team_logos(first, second)
    assert first.read_text() == second.read_text() == "original"
    monkeypatch.setattr(weekly, "fetch_json", lambda _: {"count": 2, "pageCount": 1, "items": []})
    with pytest.raises(ValueError, match="Incomplete"):
        weekly.Resolver().season_index("baseball/mlb", 2025)


def test_only_expected_404_is_explicit_absence(monkeypatch):
    def fail(code):
        def get(*_):
            raise HTTPError(URL, code, "missing", None, None)

        monkeypatch.setattr(feeds, "get_json", get)

    fail(404)
    assert weekly.fetch_json(URL) is None
    for code in [400, 403, 500]:
        fail(code)
        with pytest.raises(HTTPError):
            weekly.fetch_json(URL)


def test_registry_validation_requires_matching_pair_sources_dates_and_season():
    registry, receipts = pair()
    weekly.validate_registry(registry, receipts)
    key = next(iter(receipts["teams"]))
    for field, value in [
        ("source_url", "https://unapproved.test"),
        ("checked_date", "yesterday"),
        ("competition_season", 2024),
        ("name", "Different"),
        ("status", "missing_image"),
    ]:
        broken = deepcopy(receipts)
        broken["teams"][key][field] = value
        with pytest.raises(ValueError):
            weekly.validate_registry(registry, broken)
    with pytest.raises(ValueError):
        weekly.validate_registry(registry, {"schema_version": "1", "teams": {}})
    for invalid_url in [None, "https://unapproved.test/logo.png", RAW]:
        with pytest.raises(ValueError):
            weekly.validate_registry({"schema_version": "1", "logos": {key: invalid_url}}, receipts)


def test_weekly_always_resolves_published_images_afresh(monkeypatch, tmp_path):
    registry, receipts = pair()
    row = next(iter(receipts["teams"].values()))
    monkeypatch.setattr(weekly, "published_cohorts", lambda _: {team_logos.cohort_key(row): row})
    calls = []

    def resolve(self, cohort):
        calls.append(cohort)
        return None, URL, "missing_image"

    monkeypatch.setattr(weekly.Resolver, "resolve", resolve)
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text(json.dumps(registry))
    b.write_text(json.dumps(receipts))
    assert weekly.refresh_team_logos(a, b) == (1, 0)
    assert len(calls) == 1 and json.loads(a.read_text())["logos"] == {}


def test_published_corpus_checks_membership_counts_and_ignores_existing_logos(monkeypatch):
    public = _event_payload(fixture())
    public["participants"][0].update(logo_url=RAW, logo_source_url="old", logo_checked_date="old")
    manifest = {
        "available_seasons": [2025],
        "seasons": {"2025": {"all_events": 1, "updated_at": "now", "sports": [{"file": "2025-mlb.json", "count": 1}]}},
    }
    bundle = {"season": 2025, "updated_at": "now", "events": [public]}
    monkeypatch.setattr(weekly, "fetch_json", lambda url: manifest if url.endswith("manifest.json") else bundle)
    (row,) = weekly.published_cohorts().values()
    assert "logo_url" not in row and row["competition_season"] == 2025
    bundle["events"] = []
    with pytest.raises(ValueError, match="Incomplete"):
        weekly.published_cohorts()


def test_logo_only_enrichment_adds_espn_source_and_license(monkeypatch, tmp_path):
    from kickoff import open_schedules
    from tests.test_reviewed_schedules import fake_open_read

    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    monkeypatch.setattr(open_schedules, "fill_missing_start_times", lambda *_: [])

    def enrich(events):
        event = next(e for e in events if e.source == "openfootball" and e.participants)
        team_logos._apply(event, event.participants[0], espn_logo_url(RAW), URL, "2026-11-03")
        return [{"logo_url": espn_logo_url(RAW)}]

    monkeypatch.setattr(open_schedules, "enrich_team_logos", enrich)
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True).read_text())
    assert "espn" in bundle["data_licenses"]
    assert any(source["kind"] == "espn" for source in bundle["sources"])


@pytest.mark.parametrize("mutation", ["duplicate", "missing_page", "changed_count", "bad_reference", "missing_team"])
def test_weekly_incomplete_roster_is_failure(monkeypatch, mutation):
    base = weekly._core_url("baseball/mlb", 2025)

    def get(url):
        if urlsplit(url).path.endswith("/teams"):
            page = int(parse_qs(urlsplit(url).query).get("page", ["1"])[0])
            if page == 2 and mutation == "missing_page":
                return None
            identity = "1" if mutation == "duplicate" else str(page)
            return {
                "count": 3 if page == 2 and mutation == "changed_count" else 2,
                "pageCount": 2,
                "pageIndex": page,
                "items": [
                    {
                        "$ref": "https://unapproved.test/1"
                        if mutation == "bad_reference"
                        else f"{base.split('?')[0]}/{identity}"
                    }
                ],
            }
        if mutation == "missing_team":
            return None
        return {"id": urlsplit(url).path.rsplit("/", 1)[-1], "displayName": "Team", "logos": []}

    monkeypatch.setattr(weekly, "fetch_json", get)
    with pytest.raises(ValueError):
        weekly.Resolver().season_index("baseball/mlb", 2025)


def test_checked_in_registry_is_valid_public_fact_pair():
    from importlib.resources import files

    config = files("kickoff").joinpath("config")
    registry = json.loads(config.joinpath("team_logos.json").read_text())
    receipts = json.loads(config.joinpath("team_logo_receipts.json").read_text())
    weekly.validate_registry(registry, receipts)
    assert len(registry["logos"]) > 0
    assert all("/home/" not in json.dumps(payload) for payload in (registry, receipts))
