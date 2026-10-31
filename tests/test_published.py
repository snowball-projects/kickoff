import json

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
    assert "2026-football.json" in index and "2026-combat.json" in index
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
    football = json.loads((tmp_path / "2026-football.json").read_text())
    combat = json.loads((tmp_path / "2026-combat.json").read_text())
    football_receipt = next(row for row in football["input_evidence"] if row["url"].endswith("mixed.json"))
    combat_receipt = next(row for row in combat["input_evidence"] if row["url"].endswith("mixed.json"))
    assert football_receipt["clocks_added"] == []
    assert football_receipt["team_facts_added"] == original["input_evidence"][-1]["team_facts_added"]
    assert combat_receipt["team_facts_added"] == []
    assert combat_receipt["clocks_added"] == original["input_evidence"][-1]["clocks_added"]
    assert len(original["input_evidence"][-1]["clocks_added"]) == 1
