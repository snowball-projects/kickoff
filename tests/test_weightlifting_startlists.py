"""Static source facts and regression fingerprints from the reviewed live80 publication."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from kickoff import weightlifting_startlists as startlists
from kickoff.feeds import make_event
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.web import _event_payload

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_source_requests(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Static start lists must make zero network requests")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)


def event(identity, league="WEIGHTLIFTING_EUROPE"):
    item = make_event(
        source="weightlifting",
        league=league,
        sport="weightlifting",
        upstream_id=identity,
        season="2026",
        title="Reviewed source session",
        utc=None,
        day="2026-04-19",
        event_type="session",
    )
    item.event_id = identity
    return item


def setup_catalog(monkeypatch, tmp_path):
    """A minimal reviewed snapshot fixture; no PDF parser or transport compatibility."""
    config = {
        "books": [
            {
                "league": "WEIGHTLIFTING_EUROPE",
                "year": 2026,
                "format": "reviewed-roster",
                "name": "Official example start list",
                "publisher": "EWF",
                "landing_url": "https://ewf.sport/meet",
                "snapshot_file": "receipts/example.json",
            }
        ],
        "country_codes": {"GER": {"code": "DE", "source_url": "https://iwf.sport/codes", "checked_date": "2026-11-03"}},
    }
    monkeypatch.setattr(startlists, "catalog", lambda: config)
    categories = [{"gender": "women", "weight_class": "48", "group": "A"}]
    sessions = [
        {
            "event_id": "session",
            "categories": categories,
            "athlete_count": 2,
            "entries": [
                {"lot": "101", "name": "Example Strong", "nation": "GER", "weight": "48", "total": 180},
                {"lot": "102", "name": "Example Refugee", "nation": "WRT", "weight": "48", "total": 160},
            ],
        }
    ]
    snapshot = {
        "league": "WEIGHTLIFTING_EUROPE",
        "year": 2026,
        "source_url": "https://ewf.sport/startbook-v1.pdf",
        "revision": "Reviewed start book v1",
        "checked_date": "2026-11-03",
        "collection_method": "Dated reviewed facts",
        "hash_scope": startlists.ROSTER_HASH_SCOPE,
        "sha256": startlists.roster_hash(sessions),
        "session_count": 1,
        "athlete_count": 2,
        "sessions": sessions,
    }
    (tmp_path / "2026-weightlifting.json").write_text(
        json.dumps({"events": [{"id": "session", "categories": categories}]})
    )
    path = tmp_path / "receipts/example.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(snapshot))
    return config, snapshot, path


def save_snapshot(snapshot, path):
    snapshot["sha256"] = startlists.roster_hash(snapshot["sessions"])
    path.write_text(json.dumps(snapshot))


def test_snapshot_only_loader_keeps_dates_and_every_schedule_fact(monkeypatch, tmp_path):
    _, _, _ = setup_catalog(monkeypatch, tmp_path)
    item = event("session")
    original = deepcopy(item.to_dict())
    loader = startlists.StartListLoader()
    sources, evidence = loader.enrich([item], tmp_path, 2026)
    assert len(item.participants) == 2
    assert item.participants[0].metadata["country_code"] == "DE"
    assert "country_code" not in item.participants[1].metadata
    assert sources[0]["checked_date"] == evidence[0]["checked_date"] == "2026-11-03"
    after = item.to_dict()
    after["participants"] = []
    assert after == original
    assert not hasattr(loader, "_read") and not hasattr(startlists, "parse_start_book")
    loader.enrich([item], tmp_path, 2026)
    assert loader.enrich([item], tmp_path, 2027) == ([], [])
    assert all(p.metadata["start_list_checked_date"] == "2026-11-03" for p in item.participants)


def test_partial_frozen_cohort_keeps_frozen_values_and_loads_only_other_snapshot_members(monkeypatch, tmp_path):
    _, snapshot, path = setup_catalog(monkeypatch, tmp_path)
    second = deepcopy(snapshot["sessions"][0])
    second["event_id"] = "second"
    second["categories"][0]["weight_class"] = "53"
    for row in second["entries"]:
        row["lot"] += "0"
        row["weight"] = "53"
    snapshot["sessions"].append(second)
    snapshot["session_count"] = 2
    snapshot["athlete_count"] = 4
    save_snapshot(snapshot, path)
    definitions = {"events": [{"id": row["event_id"], "categories": row["categories"]} for row in snapshot["sessions"]]}
    (tmp_path / "2026-weightlifting.json").write_text(json.dumps(definitions))
    frozen, fresh = event("session"), event("second")
    frozen.participants = [
        startlists.Participant(name="Existing frozen facts", entity_type="athlete", metadata={"entry_total_kg": 199})
    ]
    original = deepcopy(frozen.to_dict())
    _, evidence = startlists.StartListLoader().enrich([frozen, fresh], tmp_path, 2026, skip_ids={"session"})
    assert frozen.to_dict() == original
    assert len(fresh.participants) == 2 and evidence[0]["sessions"] == 1
    assert startlists.StartListLoader().enrich([frozen, fresh], tmp_path, 2026, skip_ids={"session", "second"}) == (
        [],
        [],
    )


def test_explicit_withheld_snapshot_session_stays_empty_and_does_not_hide_valid_session(monkeypatch, tmp_path):
    _, snapshot, path = setup_catalog(monkeypatch, tmp_path)
    omitted = {
        "event_id": "withheld",
        "categories": [{"gender": "men", "weight_class": "79", "group": "A"}],
        "athlete_count": 0,
        "entries": [],
        "issue": "Source class 71 contradicts published class79",
    }
    snapshot["sessions"].append(omitted)
    snapshot["session_count"] = 2
    save_snapshot(snapshot, path)
    (tmp_path / "2026-weightlifting.json").write_text(
        json.dumps(
            {"events": [{"id": row["event_id"], "categories": row["categories"]} for row in snapshot["sessions"]]}
        )
    )
    valid, withheld = event("session"), event("withheld")
    _, evidence = startlists.StartListLoader().enrich([valid, withheld], tmp_path, 2026)
    assert len(valid.participants) == 2 and withheld.participants == []
    assert evidence[0]["omitted_sessions"] == [{"event_id": "withheld", "reason": omitted["issue"]}]
    snapshot["sessions"][-1].pop("issue")
    save_snapshot(snapshot, path)
    valid = event("session")
    assert startlists.StartListLoader().enrich([valid, withheld], tmp_path, 2026) == ([], [])
    assert valid.participants == []


def test_public_export_keeps_only_requested_factual_fields(monkeypatch, tmp_path):
    setup_catalog(monkeypatch, tmp_path)
    item = event("session")
    startlists.StartListLoader().enrich([item], tmp_path, 2026)
    item.participants[0].metadata.update(birth_date="private", raw_pdf="private", unrelated="private")
    public = _event_payload(item)["participants"][0]
    assert public["entry_total_kg"] == 180 and public["country_code"] == "DE"
    assert all(key not in public for key in ["metadata", "birth_date", "raw_pdf", "unrelated"])
    for league in ["IWF_YOUTH_WORLDS", "MASTERS_WORLDS"]:
        other = deepcopy(item)
        other.league = league
        assert not any(key in _event_payload(other)["participants"][0] for key in startlists.ENTRY_FIELDS)


# Independent fingerprints of every public participant value/order in deployed live80.
LIVE80 = {
    "WEIGHTLIFTING_EUROPE": (36, 368, "5c46c51c207e1f7834ce1f219f3fc667ea01df5e39c592ae3c6966d86d328453"),
    "WEIGHTLIFTING_ASIA": (17, 164, "ea8c5d4d4bc53ca408eb80ea3b8a31aaa234e574312d807ec064a878047468d8"),
    "WEIGHTLIFTING_PAN_AMERICA": (16, 168, "fd1d409d90f9478b647de405aec8e3a91f3200084a62a861e62904ce6f184308"),
    "IWF_WORLDS": (50, 528, "c47de936b9f016c9af2941b5fab265062697e18b7fe89d1fd21cc7326ddad001"),
    "IWF_JUNIOR_WORLDS": (28, 271, "0fa2987b41b4a8374264f2a00a2a9587b853e03d0196f6a88adf4b412ae1137e"),
    "WEIGHTLIFTING_AFRICA": (15, 126, "a4eaf26bd129dee19f1aeaf98add9ea1eef4614ee4fb64eb5a70d1b15d07db3f"),
}


@pytest.mark.parametrize("league", LIVE80)
def test_all_live80_1625_athletes_dates_flags_and_public_values_are_exact(league):
    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    events = [e for e in events if e.league == league]
    originals = {e.event_id: e.to_dict() for e in events}
    sources, evidence = startlists.StartListLoader().enrich(events, ROOT / "data/reviewed", 2026)
    expected_sessions, expected_athletes, digest = LIVE80[league]
    public = {e.event_id: _event_payload(e)["participants"] for e in events}
    assert len(events) == expected_sessions and sum(map(len, public.values())) == expected_athletes
    assert hashlib.sha256(json.dumps(public, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
    assert sources[0]["checked_date"] == evidence[0]["checked_date"] == "2026-11-04"
    for item in events:
        after = item.to_dict()
        after["participants"] = []
        assert after == originals[item.event_id]
    if league == "WEIGHTLIFTING_ASIA":
        assert evidence[0]["omitted_sessions"] == [
            {
                "event_id": "asian-2026-men-s-79-kg",
                "reason": "Source athlete class disagrees with session: lot 96, class 71, page 13",
            }
        ]
    if league.startswith("WEIGHTLIFTING_") and league != "WEIGHTLIFTING_AFRICA":
        assert evidence[0]["source_raw_sha256"] != evidence[0]["sha256"]
        assert evidence[0]["source_raw_checked_date"] == "2026-11-04"


def test_all_six_catalog_entries_are_static_and_country_citations_are_unchanged():
    config = startlists.catalog()
    assert len(config["books"]) == 6 and all(book["format"] == "reviewed-roster" for book in config["books"])
    assert not any("link_pattern" in book for book in config["books"])
    assert (
        hashlib.sha256(json.dumps(config["country_codes"], sort_keys=True).encode()).hexdigest()
        == "66b94f632d6b0112253694dc533bf514c1dde1e78588079fe50d9c041e293e63"
    )


def test_publisher_calls_optional_loader_without_changing_schedule_or_primary_sources(monkeypatch, tmp_path):
    import json
    from pathlib import Path

    from kickoff import open_schedules
    from tests.test_reviewed_schedules import fake_open_read

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)

    class Loader:
        def __init__(self):
            self.calls = []

        def enrich(self, events, directory, year):
            self.calls.append((year, directory))
            chosen = next(item for item in events if item.league == "WEIGHTLIFTING_EUROPE")
            from kickoff.models import Participant

            chosen.participants = [
                Participant(
                    name="Confirmed Athlete",
                    entity_type="athlete",
                    metadata={
                        "entry_total_kg": 180,
                        "start_list_nation": "GER",
                        "start_list_source_url": "https://ewf.sport/startbook.pdf",
                        "start_list_checked_date": "2026-11-03",
                    },
                )
            ]
            return [
                {
                    "kind": "weightlifting",
                    "name": "Official entries",
                    "url": "https://ewf.sport/startbook.pdf",
                    "license": "Schedule facts; no data license granted",
                }
            ], [{"kind": "weightlifting", "url": "https://ewf.sport/startbook.pdf", "sha256": "a" * 64}]

    loader = Loader()
    result = json.loads(
        open_schedules.refresh_open_schedules(
            2026, tmp_path, root / "data/reviewed", start_list_loader=loader
        ).read_text()
    )
    assert loader.calls == [(2026, root / "data/reviewed")]
    assert any(p.get("entry_total_kg") == 180 for item in result["events"] for p in item["participants"])
    assert any(source["name"] == "Official entries" for source in result["sources"])
    assert any(proof["url"] == "https://ewf.sport/startbook.pdf" for proof in result["input_evidence"])
