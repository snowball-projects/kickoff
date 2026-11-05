"""Offline source excerpts and completeness regressions for the requested ESPN batch."""

import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from kickoff import feeds, team_logos
from kickoff.textutils import espn_logo_url
from kickoff.validation import validate_batch
from kickoff.web import _event_payload, _participant_payload

FIXTURE = json.loads((Path(__file__).parent / "fixtures/espn-remaining-leagues.json").read_text())
CASES = FIXTURE["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: f"{case['league']}-{case['slug']}")
def test_source_stages_and_supplied_facts_survive_public_export(monkeypatch, case):
    row = case["event"]
    league = case["league"]
    year = int(row["date"][:4])

    def get(url, **_):
        prefix = parse_qs(urlsplit(url).query)["dates"][0]
        return {
            "events": [row] if prefix == str(year) and "week=" not in url else [],
            "leagues": [{"calendar": [{"value": "2", "entries": [{"value": "1", "endDate": "2026-12-31"}]}]}],
        }

    monkeypatch.setattr(feeds, "get_json", get)
    (event,) = feeds.espn_team_events(year, league)
    assert validate_batch([event]) == []
    assert event.facts_checked_date and event.facts_source_url
    assert (
        event.start_time_utc is not None
        if row["competitions"][0].get("timeValid", True)
        else event.start_time_utc is None
    )
    public = _event_payload(event)
    assert public["city"] == (row["competitions"][0].get("venue") or {}).get("address", {}).get("city")
    for participant in event.participants:
        original = next(c for c in row["competitions"][0]["competitors"] if c["homeAway"] == participant.role)
        assert participant.entity_type == "team"  # club logo never establishes nationality
        exported = _participant_payload(participant)
        assert exported["logo_url"] == espn_logo_url(original["team"]["logo"])
        assert exported["logo_checked_date"] == event.facts_checked_date
        assert exported["logo_source_url"] == event.facts_source_url
        assert "country_code" not in exported
        assert participant.short_name == original["team"]["shortDisplayName"]
    assert "raw_source_payload" not in public
    slug = case["slug"]
    if league == "WSL" or slug in {"torneo-apertura", "torneo-clausura", "regular-season", "showdown-cup"}:
        assert event.competition_phase == "regular_season"
    elif slug == "league-phase":
        assert event.competition_phase == "league_phase"
    elif slug == "group-stage":
        assert event.competition_phase == "group_stage"
    elif slug == "preseason":
        assert event.competition_phase == "preseason"
    elif slug in {"final", "playoffs---championship"} or slug.endswith("---finals"):
        assert event.competition_phase == "final"
    elif slug == "post-season":
        assert event.competition_phase == "postseason"
    else:
        assert event.competition_phase == "knockout"


def test_ufl_discovers_all_weeks_and_unions_missing_games_with_no_duplicates(monkeypatch):
    row = next(case["event"] for case in CASES if case["league"] == "UFL")
    annual = {**row, "id": "annual", "date": "2026-03-28T00:00Z"}
    missing = {**row, "id": "weekly-only", "date": "2026-04-01T00:00Z"}
    calls = []

    def get(url, **_):
        query = parse_qs(urlsplit(url).query)
        calls.append(query)
        if query["dates"] == ["2026"] and "week" not in query:
            return {
                "events": [annual],
                "leagues": [
                    {
                        "calendar": [
                            {
                                "value": "2",
                                "entries": [
                                    {"value": "1", "endDate": "2026-12-31"},
                                    {"value": "27", "endDate": "2026-12-31"},
                                ],
                            },
                            {"value": "3", "entries": [{"value": "2", "endDate": "2026-12-31"}]},
                        ]
                    }
                ],
            }
        if query.get("week") == ["27"]:
            sparse = copy.deepcopy(annual)
            for team in sparse["competitions"][0]["competitors"]:
                team["team"].pop("logo", None)
                team.pop("records", None)
            return {"events": [sparse, missing]}
        return {"events": [], "leagues": [{"calendar": []}]}

    monkeypatch.setattr(feeds, "get_json", get)
    events = feeds.espn_team_events(2026, "UFL")
    assert {e.event_id for e in events} == {"espn-ufl-annual", "espn-ufl-weekly-only"}
    assert {tuple(q["week"]) for q in calls if "week" in q} == {("1",), ("27",), ("2",)}
    assert not any(q["dates"] == ["2025"] for q in calls)
    assert all("seasontype=" in e.facts_source_url for e in events)
    retained = next(e for e in events if e.event_id == "espn-ufl-annual")
    assert all(p.metadata.get("logo_url") for p in retained.participants)
    assert all("seasontype=" not in p.metadata["logo_source_url"] for p in retained.participants)


def test_ufl_missing_calendar_fails_instead_of_publishing_known_incomplete_index(monkeypatch):
    monkeypatch.setattr(
        feeds, "get_json", lambda _, **_options: {"events": [next(c["event"] for c in CASES if c["league"] == "UFL")]}
    )
    with pytest.raises(ValueError, match="Missing UFL weekly calendar"):
        feeds.espn_team_events(2026, "UFL")


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.test/x.png",
        "http://a.espncdn.com/i/teamlogos/a.png",
        "https://a.espncdn.com.evil.test/i/teamlogos/a.png",
        "https://a.espncdn.com/i/teamlogos/a.png?tracking=1",
        None,
    ],
)
def test_logo_public_boundary_rejects_unapproved_origins_and_querystrings(value):
    assert espn_logo_url(value) is None


def test_untrusted_logo_metadata_does_not_escape_export(monkeypatch):
    case = CASES[0]
    row = copy.deepcopy(case["event"])
    event = feeds._espn_event(
        row, league=case["league"], sport="soccer", zone=feeds.EASTERN, fallback_url=case["url"], input_url=case["url"]
    )
    event.participants[0].metadata["logo_url"] = "https://evil.test/a.png"
    assert "logo_url" not in _participant_payload(event.participants[0])


def test_all_requested_usable_leagues_registered_and_cfl_withheld():
    assert len(feeds.ADDITIONAL_TEAM_LEAGUES) == 11
    assert set(feeds.ADDITIONAL_TEAM_LEAGUES) <= feeds.FEEDS.keys()
    assert "CFL" not in feeds.FEEDS


def test_ufl_unpublished_empty_year_needs_no_weekly_calendar(monkeypatch):
    monkeypatch.setattr(feeds, "get_json", lambda _, **_options: {"events": []})
    assert feeds.espn_team_events(2027, "UFL") == []


def test_ufl_stripped_calendar_cannot_silently_publish_a_partial_season(monkeypatch):
    row = next(c["event"] for c in CASES if c["league"] == "UFL")
    monkeypatch.setattr(feeds, "get_json", lambda _, **_options: {"events": [row], "leagues": [{"calendar": []}]})
    with pytest.raises(ValueError, match="Missing UFL weekly calendar entries"):
        feeds.espn_team_events(2026, "UFL")


def test_dated_g_league_bracket_slot_keeps_appointment_without_pseudo_teams(monkeypatch):
    row = next(c["event"] for c in CASES if c["event"]["id"] == "401932977")
    monkeypatch.setattr(feeds, "get_json", lambda url, **_options: {"events": [row] if "dates=2026&" in url else []})
    (event,) = feeds.espn_team_events(2026, "G_LEAGUE")
    assert event.title == "NBA G League"
    assert event.start_time_utc == "2026-12-19T17:30:00Z"
    assert event.venue == "Orange County Convention Center"
    assert event.participants == []
    assert event.home_participant is None and event.away_participant is None


def test_supplied_historical_logo_guid_paths_remain_available():
    url = "https://a.espncdn.com/guid/6381f392-8ff3-3be9-af92-3beeaa1361ef/logos/default.png"
    assert espn_logo_url(url).startswith("https://a.espncdn.com/combiner/i?img=%2Fguid%2F")


def test_missing_scoreboard_logo_uses_offline_registry_with_own_receipt(monkeypatch):
    row = copy.deepcopy(CASES[0]["event"])
    team = row["competitions"][0]["competitors"][0]["team"]
    source_logo = team.pop("logo")
    monkeypatch.setattr(
        feeds, "get_json", lambda value, **_options: {"events": [row] if "dates=2026&" in value else []}
    )
    (event,) = feeds.espn_team_events(2026, "FA_CUP")
    retained = next(p for p in event.participants if p.participant_id == team["id"])
    key = team_logos.team_key(event, retained)
    url = f"{feeds.ESPN}/soccer/eng.fa/teams/{team['id']}"
    monkeypatch.setattr(
        team_logos,
        "logo_registry",
        lambda: {
            event.league: {
                key: {
                    "names": [retained.name],
                    "logo_url": espn_logo_url(source_logo),
                    "source_url": url,
                    "checked_date": "2026-11-03",
                }
            }
        },
    )
    monkeypatch.setattr(feeds, "get_json", lambda *a, **k: pytest.fail("Daily enrichment is offline"))
    team_logos.enrich_team_logos([event])
    public = _participant_payload(retained)
    assert public["logo_url"] == espn_logo_url(source_logo)
    assert public["logo_source_url"] == url
    assert public["logo_checked_date"] == "2026-11-03"
