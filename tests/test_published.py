import json
from copy import deepcopy

import pytest

from kickoff.published import publish_sports


def bundle(year=2026):
    return {
        "season": year,
        "available_seasons": [2026, 2027],
        "updated_at": "2026-10-31T00:00:00Z",
        "providers": [],
        "coverage": "Fixture coverage",
        "exclusions": [],
        "data_licenses": {"espn": "No license granted", "wikipedia": "CC BY-SA 4.0"},
        "data_license_notice": "Wikipedia adaptations are CC BY-SA 4.0.",
        "sources": [
            {"kind": "espn", "name": "ESPN", "url": "https://www.espn.com/"},
            {
                "kind": "wikipedia",
                "name": "Wikipedia contributors",
                "url": "https://en.wikipedia.org/w/index.php?oldid=123",
                "revision": "123",
            },
        ],
        "input_evidence": [
            {"kind": "espn", "url": "https://site.api.espn.com/", "sha256": "a" * 64},
            {"kind": "wikipedia", "url": "https://en.wikipedia.org/w/index.php?oldid=123", "sha256": "b" * 64},
        ],
        "events": [
            {
                "event_id": "football",
                "source": "espn",
                "sport": "football",
                "league": "NFL",
                "event_type": "game",
                "competition_phase": "regular_season",
                "tags": [],
                "participants": [],
                "title": "NFL game",
                "calendar_date": f"{year}-11-01",
                "source_url": "https://www.espn.com/nfl/",
            },
            {
                "event_id": "combat",
                "source": "wikipedia",
                "sport": "combat",
                "league": "PFL",
                "event_type": "card",
                "competition_phase": "regular_season",
                "tags": ["Men"],
                "participants": [],
                "title": "PFL",
                "calendar_date": f"{year}-11-01",
                "source_url": "https://en.wikipedia.org/w/index.php?oldid=123",
            },
        ],
    }


def test_split_preserves_every_fact_and_specific_license_with_metadata_only_index(tmp_path):
    original = bundle()
    path = publish_sports([original], tmp_path)
    manifest = json.loads(path.read_text())
    year = manifest["seasons"]["2026"]
    assert manifest["available_seasons"] == [2026]
    assert "events" not in year
    assert year["all_events"] == 2
    assert year["leagues"] == [
        {"value": "NFL", "count": 1, "sport": "football"},
        {"value": "PFL", "count": 1, "sport": "combat"},
    ]
    published = []
    for item in year["sports"]:
        sport = json.loads((tmp_path / item["file"]).read_text())
        assert len(sport["events"]) == item["count"]
        assert {e["sport"] for e in sport["events"]} == {item["value"]}
        published.extend(sport["events"])
        if item["value"] == "combat":
            assert sport["data_licenses"] == {"wikipedia": "CC BY-SA 4.0"}
            assert sport["sources"][0]["revision"] == "123"
            assert sport["input_evidence"][0]["kind"] == "wikipedia"
        else:
            assert sport["data_licenses"] == {"espn": "No license granted"}
            assert sport["sources"][0]["kind"] == "espn"
    assert sorted(published, key=lambda e: e["event_id"]) == sorted(original["events"], key=lambda e: e["event_id"])
    assert year["sources"] == original["sources"]
    index = (tmp_path / "index.html").read_text()
    assert "2026-football-nfl.json" in index and "2026-combat-pfl.json" in index
    assert "manifest.json" in index and "Licenses" in index
    assert not (tmp_path / "2026.json").exists()


def test_republication_removes_old_owned_outputs_and_has_no_sport_or_year_caps(tmp_path):
    (tmp_path / "2026.json").write_text("old monolith")
    (tmp_path / "1999-unused.json").write_text("old sport")
    (tmp_path / ".gitkeep").touch()
    publish_sports([bundle(2026), bundle(2027)], tmp_path)
    assert not (tmp_path / "2026.json").exists()
    assert not (tmp_path / "1999-unused.json").exists()
    assert (tmp_path / ".gitkeep").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["available_seasons"] == [2026, 2027]
    assert sum(year["all_events"] for year in manifest["seasons"].values()) == 4


def test_optional_enrichment_evidence_contains_only_this_sports_matched_facts(tmp_path):
    original = bundle()
    original["input_evidence"].append(
        {
            "kind": "espn",
            "url": "https://site.api.espn.com/mixed.json",
            "sha256": "c" * 64,
            "clocks_added": [{"event_id": "combat", "time_source_url": "https://www.espn.com/fight/"}],
            "team_facts_added": [{"event_id": "football", "team_source_url": "https://www.espn.com/nfl/"}],
        }
    )
    original["events"][1]["start_time_source"] = "espn"
    publish_sports([original], tmp_path)
    football = json.loads((tmp_path / "2026-football-nfl.json").read_text())
    combat = json.loads((tmp_path / "2026-combat-pfl.json").read_text())
    football_receipt = next(row for row in football["input_evidence"] if row["url"].endswith("mixed.json"))
    combat_receipt = next(row for row in combat["input_evidence"] if row["url"].endswith("mixed.json"))
    assert football_receipt["clocks_added"] == []
    assert football_receipt["team_facts_added"] == original["input_evidence"][-1]["team_facts_added"]
    assert combat_receipt["team_facts_added"] == []
    assert combat_receipt["clocks_added"] == original["input_evidence"][-1]["clocks_added"]
    assert len(original["input_evidence"][-1]["clocks_added"]) == 1


def test_football_leagues_have_independent_files_without_changing_sport_or_facts(tmp_path):
    original = bundle()
    nfl = original["events"][0]
    original["events"].extend(
        [
            {**nfl, "event_id": "college", "league": "COLLEGE_FOOTBALL", "title": "College game"},
            {**nfl, "event_id": "ufl", "league": "UFL", "title": "UFL game"},
        ]
    )
    publish_sports([original], tmp_path)
    year = json.loads((tmp_path / "manifest.json").read_text())["seasons"]["2026"]
    football = [item for item in year["sports"] if item["value"] == "football"]
    assert football == [
        {
            "value": "football",
            "count": 1,
            "file": "2026-football-college-football.json",
            "leagues": ["COLLEGE_FOOTBALL"],
        },
        {"value": "football", "count": 1, "file": "2026-football-nfl.json", "leagues": ["NFL"]},
        {"value": "football", "count": 1, "file": "2026-football-ufl.json", "leagues": ["UFL"]},
    ]
    published = []
    for item in year["sports"]:
        payload = json.loads((tmp_path / item["file"]).read_text())
        assert sorted({event["league"] for event in payload["events"]}) == item["leagues"]
        published.extend(payload["events"])
    assert sorted(published, key=lambda event: event["event_id"]) == sorted(
        original["events"], key=lambda event: event["event_id"]
    )
    index = (tmp_path / "index.html").read_text()
    for item in football:
        assert f'href="{item["file"]}"' in index


def test_each_sport_publishes_one_file_per_league_with_all_facts_and_receipts(tmp_path):
    original = bundle()
    template = original["events"][0]
    original["events"] = [
        {**template, "event_id": league, "league": league, "sport": sport}
        for sport, league in [("basketball", "NBA"), ("basketball", "WNBA"), ("soccer", "EPL"), ("soccer", "FA_CUP")]
    ]
    original["input_evidence"].append(
        {
            "kind": "espn",
            "url": "https://site.api.espn.com/optional-facts.json",
            "sha256": "c" * 64,
            "team_facts_added": [
                {"event_id": event["event_id"], "team_source_url": event["source_url"]} for event in original["events"]
            ],
        }
    )
    publish_sports([original], tmp_path)
    year = json.loads((tmp_path / "manifest.json").read_text())["seasons"]["2026"]
    assert year["all_events"] == 4
    assert len(year["sports"]) == 4
    published = []
    index = (tmp_path / "index.html").read_text()
    for item in year["sports"]:
        payload = json.loads((tmp_path / item["file"]).read_text())
        assert len(item["leagues"]) == 1
        assert payload["events"] == [event for event in original["events"] if event["league"] == item["leagues"][0]]
        assert payload["data_licenses"] == {"espn": "No license granted"}
        assert payload["input_evidence"][0] == original["input_evidence"][0]
        assert payload["input_evidence"][1]["team_facts_added"] == [
            row for row in original["input_evidence"][-1]["team_facts_added"] if row["event_id"] == item["leagues"][0]
        ]
        assert f'href="{item["file"]}"' in index
        published.extend(payload["events"])
    assert sorted(published, key=lambda event: event["event_id"]) == sorted(
        original["events"], key=lambda event: event["event_id"]
    )


@pytest.mark.parametrize("league,sport,kind", [("MLB", "baseball", "mlb"), ("NHL", "hockey", "nhl")])
def test_espn_image_source_keeps_license_with_official_schedule_bundle(tmp_path, league, sport, kind):
    original = bundle()
    original["sources"].append({"kind": kind, "name": "Official schedule", "url": "https://example.org/"})
    original["data_licenses"][kind] = "Official factual schedule terms"
    original["events"] = [
        {
            **original["events"][0],
            "source": kind,
            "league": league,
            "sport": sport,
            "participants": [
                {
                    "name": "Source team",
                    "role": "home",
                    "logo_url": "https://a.espncdn.com/combiner/i?img=%2Fi%2Fteamlogos%2Fmlb%2F500%2Fbal.png&w=56&h=56",
                    "logo_source_url": f"https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{kind}/seasons/2025/teams/1",
                    "logo_checked_date": "2026-11-03",
                }
            ],
        }
    ]
    publish_sports([original], tmp_path)
    payload = json.loads((tmp_path / f"2026-{sport}-{league.lower()}.json").read_text())
    assert {source["kind"] for source in payload["sources"]} == {kind, "espn"}
    assert set(payload["data_licenses"]) == {kind, "espn"}
    assert payload["events"] == original["events"]


@pytest.mark.parametrize("complete", [False, True])
def test_weightlifting_result_omits_start_rows_after_reuse_without_mutating_inputs(tmp_path, complete):
    original = bundle()
    roster = {
        "name": "Start-list athlete",
        "entity_type": "athlete",
        "entry_total_kg": 180,
        "start_list_source_url": "https://example.org/start-list",
    }
    other = {"name": "Other participant", "entity_type": "athlete"}
    row = {
        **original["events"][0],
        "event_id": "session",
        "sport": "weightlifting",
        "league": "IWF_WORLDS",
        "status": "finished",
        "participants": [roster, other],
        "result": {"kind": "weightlifting", "complete": complete, "rows": [{"name": "Actual result"}]},
    }
    pending = {**row, "event_id": "pending", "result": None}
    original["events"] = [row, pending, {**row, "event_id": "other-sport", "sport": "other"}]
    before = deepcopy(original)
    publish_sports([original], tmp_path)
    events = json.loads((tmp_path / "2026-weightlifting-iwf-worlds.json").read_text())["events"]
    assert events[0] == {**row, "participants": [other]}
    assert events[1] == pending
    assert json.loads((tmp_path / "2026-other-iwf-worlds.json").read_text())["events"][0]["participants"] == [
        roster,
        other,
    ]
    assert original == before
