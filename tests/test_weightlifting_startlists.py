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


# Independent live80 participant facts/order, excluding country citations that can gain a structured source.
LIVE80 = {
    "WEIGHTLIFTING_EUROPE": (36, 368, "13badf40f59797405ed8b18c4c752b1510021bcdba8b7421fe77f6f067d69b8d"),
    "WEIGHTLIFTING_ASIA": (17, 164, "081f5e13aaaee8d4edfe356c7ee422a20b3fbab25dbcae9f17f580fe9f8a0bae"),
    "WEIGHTLIFTING_PAN_AMERICA": (16, 168, "3610142d5934aaa0615b8b4cffd7bec649d6d88672365ecfc22506c4ebb6ec42"),
    "IWF_WORLDS": (50, 528, "ffa240a940da5f7824a755ca422b42385d4c9cb7fc739929c25c9bd4f51a1bf9"),
    "IWF_JUNIOR_WORLDS": (28, 271, "853b089e5cddff5dbc250669633665880a4d02b6ac17bde106a08898fcb379d1"),
    "WEIGHTLIFTING_AFRICA": (15, 126, "3a53689ea7ce6381b9112fa9369ff353055801b35a27f34f2b4b45edf63bfc2e"),
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
    # Citation-only source changes must not alter athlete facts, flags or ordering.
    factual = {
        identity: [
            {key: value for key, value in row.items() if key not in {"country_source_url", "country_checked_date"}}
            for row in rows
        ]
        for identity, rows in public.items()
    }
    assert hashlib.sha256(json.dumps(factual, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
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


def test_all_six_catalog_entries_are_static_and_country_codes_use_structured_sources():
    config = startlists.catalog()
    assert len(config["books"]) == 6 and all(book["format"] == "reviewed-roster" for book in config["books"])
    assert not any("link_pattern" in book for book in config["books"])
    countries = config["country_codes"]
    assert len(countries) == 139
    directory = "https://iwf.sport/focus-on-iwf/federations/?federation=all"
    for nation, row in countries.items():
        if nation == "ENG":
            assert row["code"] == "GB-ENG"
            assert row["source_url"] == "https://www.glasgow2026.com/teams/england"
            assert row["checked_date"] == "2026-11-04"
        elif nation == "GIB":
            assert row["code"] == "GI"
            assert row["source_url"] == "https://www.glasgow2026.com/results/detailed/#/athlete-details/37497"
            assert row["checked_date"] == "2026-11-04"
        else:
            assert row["source_url"] == directory
            assert row["checked_date"] == "2026-11-04"
    assert {nation: countries[nation]["code"] for nation in ["ALG", "GER", "LES", "SLO", "SVK", "TPE"]} == {
        "ALG": "DZ",
        "GER": "DE",
        "LES": "LS",
        "SLO": "SI",
        "SVK": "SK",
        "TPE": "TW",
    }


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


def test_cutoff_keeps_pending_worlds_rosters_from_the_complete_snapshot(monkeypatch, tmp_path):
    from datetime import datetime, timezone

    from kickoff import open_schedules
    from kickoff.published import PublishedWindow
    from tests.test_reviewed_schedules import fake_open_read

    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    window = PublishedWindow(
        datetime(2026, 11, 4, tzinfo=timezone.utc),
        {(2026, "IWF_WORLDS"): {"events": []}},
    )
    payload = json.loads(
        open_schedules.refresh_open_schedules(
            2026,
            tmp_path,
            ROOT / "data/reviewed",
            feeds={},
            start_list_loader=startlists.StartListLoader(),
            window=window,
        ).read_text()
    )
    pending = [e for e in payload["events"] if e["league"] == "IWF_WORLDS" and e["calendar_date"] >= "2026-11-05"]
    assert len(pending) == 16
    assert sum(len(e["participants"]) for e in pending) == 166
    assert all(p["start_list_source_url"] for e in pending for p in e["participants"])
