"""Reviewed IWF facts: offline publication, exact cohort joins and honest provenance."""

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from kickoff import weightlifting_startlists as startlists
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.web import _event_payload
from tests.test_weightlifting_startlists import event, setup_catalog

ROOT = Path(__file__).resolve().parents[1]


def reviewed_fixture(monkeypatch, tmp_path):
    config, _, _ = setup_catalog(monkeypatch, tmp_path)
    config["books"][0].update(format="reviewed-roster", snapshot_file="receipts/example.json")
    sessions = [
        {
            "event_id": "session",
            "categories": [{"gender": "women", "weight_class": "48", "group": "A"}],
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
        "source_url": "https://iwf.sport/official-startbook-v1.1.pdf",
        "revision": "Start book v1.1",
        "checked_date": "2026-11-04",
        "collection_method": "Reviewed official factual roster; no daily PDF check",
        "hash_scope": startlists.ROSTER_HASH_SCOPE,
        "sha256": startlists.roster_hash(sessions),
        "session_count": 1,
        "athlete_count": 2,
        "sessions": sessions,
    }
    path = tmp_path / "receipts/example.json"
    path.parent.mkdir()
    path.write_text(json.dumps(snapshot))
    return snapshot, path


def test_reviewed_roster_is_offline_keeps_actual_checkdate_and_canonical_hash_scope(monkeypatch, tmp_path):
    snapshot, _ = reviewed_fixture(monkeypatch, tmp_path)
    item = event("session")
    before = item.to_dict()

    class NoFreshening(datetime):
        @classmethod
        def now(cls, *_):
            raise AssertionError("A reviewed snapshot must not acquire today's check date")

    monkeypatch.setattr(startlists, "datetime", NoFreshening)

    def no_network(_):
        raise AssertionError("Reviewed snapshots must publish without network access")

    sources, evidence = startlists.StartListLoader(no_network).enrich([item], tmp_path, 2026)
    assert len(item.participants) == 2
    after = item.to_dict()
    after["participants"] = []
    assert after == before
    for proof in [sources[0], evidence[0]]:
        assert proof["checked_date"] == "2026-11-04"
        assert proof["sha256"] == snapshot["sha256"]
        assert proof["hash_scope"] == startlists.ROSTER_HASH_SCOPE
        assert "not raw PDF bytes" in proof["hash_scope"]
        assert proof["revision"] == "Start book v1.1"
    assert item.participants[0].metadata["country_code"] == "DE"
    assert "country_code" not in item.participants[1].metadata
    assert item.participants[1].metadata["start_list_nation"] == "WRT"
    assert all(p["start_list_checked_date"] == "2026-11-04" for p in _event_payload(item)["participants"])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["sessions"][0]["entries"].pop(),
        lambda p: p["sessions"][0]["entries"][1].update(lot="101"),
        lambda p: p["sessions"][0]["entries"][0].update(weight="53"),
        lambda p: p["sessions"][0]["entries"][0].update(total=0),
        lambda p: p["sessions"][0]["entries"][0].update(birth_date="private"),
        lambda p: p["sessions"][0].update(event_id="different-session"),
        lambda p: p["sessions"][0]["categories"][0].update(group="B"),
        lambda p: p.update(athlete_count=1),
        lambda p: p.update(session_count=2),
        lambda p: p.update(hash_scope="raw PDF bytes"),
        lambda p: p.update(checked_date="unknown"),
    ],
)
def test_invalid_reviewed_cohort_is_omitted_atomically_without_changing_schedule(monkeypatch, tmp_path, mutation):
    snapshot, path = reviewed_fixture(monkeypatch, tmp_path)
    mutation(snapshot)
    snapshot["sha256"] = startlists.roster_hash(snapshot["sessions"])
    path.write_text(json.dumps(snapshot))
    item = event("session")
    before = deepcopy(item.to_dict())
    assert startlists.StartListLoader().enrich([item], tmp_path, 2026) == ([], [])
    assert item.to_dict() == before


def test_missing_or_unreadable_reviewed_roster_cannot_abort_schedule(monkeypatch, tmp_path):
    _, path = reviewed_fixture(monkeypatch, tmp_path)
    real_read = Path.read_text

    def denied_read(self, *args, **kwargs):
        if self == path:
            raise OSError("Unavailable reviewed roster")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied_read)
    item = event("session")
    before = deepcopy(item.to_dict())
    assert startlists.StartListLoader().enrich([item], tmp_path, 2026) == ([], [])
    assert item.to_dict() == before


def test_corrupted_canonical_roster_hash_cannot_publish_new_facts(monkeypatch, tmp_path):
    snapshot, path = reviewed_fixture(monkeypatch, tmp_path)
    snapshot["sessions"][0]["entries"][0]["name"] = "Changed without review hash"
    path.write_text(json.dumps(snapshot))
    assert startlists.StartListLoader().enrich([event("session")], tmp_path, 2026) == ([], [])


@pytest.mark.parametrize(
    "league,count,athletes,revision,combined_count,combined_categories",
    [
        (
            "IWF_WORLDS",
            50,
            528,
            "Start book v1.1, 26 October 2026",
            12,
            {"Women's 53 kg, Group D", "Women's 57 kg, Group B"},
        ),
        (
            "IWF_JUNIOR_WORLDS",
            28,
            271,
            "Start book v1.1, 1 May 2026",
            10,
            {"Women's 48 kg, Group B", "Women's 53 kg, Group B"},
        ),
        (
            "WEIGHTLIFTING_AFRICA",
            15,
            126,
            "Start book, printed 13 May 2026 15:52:28",
            12,
            {"Women's 48 kg, Group A", "Women's 53 kg, Group A"},
        ),
    ],
)
def test_current_reviewed_rosters_keep_every_athlete_session_and_original_schedule(
    league, count, athletes, revision, combined_count, combined_categories
):
    book = next(b for b in startlists.catalog()["books"] if b["league"] == league)
    parsed, snapshot = startlists.reviewed_start_book(book, ROOT / "data/reviewed")
    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    events = [e for e in events if e.league == league]
    originals = {e.event_id: e.to_dict() for e in events}
    sources, evidence = startlists.StartListLoader(lambda _: pytest.fail("No network for reviewed IWF facts")).enrich(
        events, ROOT / "data/reviewed", 2026
    )
    assert len(parsed) == len(events) == count
    assert sum(len(s.entries) for s in parsed) == athletes
    assert evidence[0]["athletes"] == athletes and evidence[0]["sessions"] == count
    assert snapshot["revision"] == revision
    assert sources[0]["checked_date"] == "2026-11-04"
    assert len({p.participant_id for e in events for p in e.participants}) == athletes
    combined = [
        e for e in events if len(next(s for s in snapshot["sessions"] if s["event_id"] == e.event_id)["categories"]) > 1
    ]
    assert len(combined) == 1 and len(combined[0].participants) == combined_count
    assert {p.metadata["start_list_category"] for p in combined[0].participants} == combined_categories
    allowed = {"lot", "name", "nation", "weight", "total"}
    assert all(set(entry) == allowed for row in snapshot["sessions"] for entry in row["entries"])
    for e in events:
        after = e.to_dict()
        after["participants"] = []
        assert after == originals[e.event_id]
        for p in _event_payload(e)["participants"]:
            assert "birth_date" not in p and "metadata" not in p and "raw_pdf" not in p


def test_african_statistics_discrepancy_does_not_invent_entries_or_drop_timetable_sessions():
    book = next(b for b in startlists.catalog()["books"] if b["league"] == "WEIGHTLIFTING_AFRICA")
    parsed, snapshot = startlists.reviewed_start_book(book, ROOT / "data/reviewed")
    discrepancy = snapshot["source_count_discrepancy"]
    assert discrepancy["statistics"] == 141 and discrepancy["timetable_and_rosters"] == 126
    assert {row["nation"]: (row["statistics"], row["rosters"]) for row in discrepancy["nation_differences"]} == {
        "EGY": (21, 16),
        "GRE": (6, 0),
        "LBA": (8, 4),
    }
    assert len(parsed) == 15 and sum(len(row.entries) for row in parsed) == 126
    assert "withdraw" not in discrepancy["reason"].lower()
    assert any(e.nation == "les" for row in parsed for e in row.entries)
    assert startlists.catalog()["country_codes"]["LES"]["code"] == "LS"
    assert "WRT" not in startlists.catalog()["country_codes"]
