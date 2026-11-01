"""Reviewed full-title eligibility, pinned Zuffa cards and published provenance."""

import copy
import json
from collections import Counter

import pytest

from kickoff.open_schedules import refresh_open_schedules
from kickoff.reviewed_schedules import BOXING_LICENSE, load_reviewed_schedules, reviewed_events
from tests.test_reviewed_schedules import ROOT, fake_open_read


def registry(year=2026):
    return json.loads((ROOT / f"data/reviewed/{year}-boxing-titles.json").read_text())


def test_full_title_list_keeps_single_belt_defenses_and_original_identity():
    rows, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    boxing = [row for row in rows if row.league == "BOXING_MAJOR"]
    single = next(row for row in boxing if "Muratalla" in row.title and "Cruz" in row.title)
    assert single.calendar_date == "2026-01-24"
    original = next(row for row in boxing if row.event_id == "boxing-navarrete-foster-1")
    assert original.title == "Emanuel Navarrete vs. O'Shaquie Foster"
    assert original.calendar_date == "2026-10-24"
    assert original.country == "US"
    assert all(row.facts_checked_date == "2026-10-31" for row in boxing)
    assert all(row.start_time_utc is row.start_time_local is row.timezone is None for row in boxing)
    assert all(row.subtitle is None for row in boxing)


def test_no_interim_secondary_silver_or_withdrawn_sanction_bouts_slip_into_title_coverage():
    names = "\n".join(row["title"] for row in registry()["events"])
    for excluded in ["Baumstarh", "Bustillos", "Neider Valdez", "Endry Saavedra", "Brandon Glanton"]:
        assert excluded not in names
    old = json.loads((ROOT / "data/reviewed/2026-combat-iwf.json").read_text())
    assert all(row["league"] != "BOXING_MAJOR" for row in old["events"])
    assert not any(row["league"] == "BOXING_MAJOR" for row in old["exclusions"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["events"][0].update(titles=[]),
        lambda p: p["events"][0].update(checked_date="today"),
        lambda p: p["events"][0].update(end_date="2026-01-25"),
        lambda p: p["events"][0]["titles"][0].update(body="IBO"),
        lambda p: p["events"][0]["titles"][0].update(level="interim"),
        lambda p: p["events"][0]["titles"][0].update(level="regular"),
        lambda p: p["events"][0]["titles"][0].update(level="silver"),
        lambda p: p["events"][0]["titles"][0].update(source_url="https://example.com/unreviewed"),
        lambda p: p["events"][0]["titles"][0].update(evidence=""),
        lambda p: p["events"][0].update(local_time="20:00"),
    ],
)
def test_eligibility_and_evidence_are_checked_where_reviewed_data_is_produced(mutate):
    payload = copy.deepcopy(registry())
    mutate(payload)
    with pytest.raises(ValueError):
        reviewed_events(payload, 2026)


def test_zuffa_counts_every_published_card_including_linked_copromotions():
    payload = json.loads((ROOT / "data/reviewed/2026-zuffa-boxing.json").read_text())
    events, sources = reviewed_events(payload, 2026)
    assert len(events) == 14
    assert len([row for row in events if row.event_id.startswith("zuffa-boxing-")]) == 12
    assert (
        len(
            [
                row
                for row in events
                if row.event_id.startswith("zuffa-fury-") or row.event_id.startswith("zuffa-garcia-")
            ]
        )
        == 2
    )
    assert {row.calendar_date for row in events if "Boxing 12:" in row.title} == {"2026-11-07"}
    assert all(row.start_time_utc is row.start_time_local is row.timezone is None for row in events)
    assert len({row.event_id for row in events}) == len(events)
    assert Counter(row.country for row in events) == {"US": 9, "GB": 4, "IE": 1}
    assert all(
        source["license"] == "CC BY-SA 4.0" and f"oldid={source['revision']}" in source["url"] for source in sources
    )
    assert all(row.country_source_url == row.source_url and row.country_checked_date == "2026-10-31" for row in events)
    assert not any(row.league == "ZUFFA_BOXING" for row in load_reviewed_schedules(ROOT / "data/reviewed", 2027)[0])


def test_publication_retains_boxing_sources_and_does_not_relicense_wikipedia(monkeypatch, tmp_path):
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    output = refresh_open_schedules(2026, tmp_path, ROOT / "data/reviewed", feeds={})
    bundle = json.loads(output.read_text())
    events = [row for row in bundle["events"] if row["sport"] == "boxing"]
    assert {row["league"] for row in events} == {"BOXING_MAJOR", "ZUFFA_BOXING"}
    assert bundle["data_licenses"]["boxing_ibf"] == BOXING_LICENSE
    assert bundle["data_licenses"]["wikipedia"] == "CC BY-SA 4.0"
    assert any(source["kind"].startswith("boxing_") for source in bundle["sources"])
    for kind in ["boxing_ibf", "wikipedia"]:
        published = [row for row in events if row["source"] == kind]
        assert published
        assert all(row["facts_source_url"] == row["source_url"] for row in published)
        assert all(row["facts_checked_date"] == "2026-10-31" for row in published)
    assert all(row["source_url"] and row["facts_checked_date"] == "2026-10-31" for row in events)
    for component in bundle["components"]:
        adapted = json.loads((tmp_path / component["path"]).read_text())
        assert all(row["source"] == "wikipedia" for row in adapted["events"])


@pytest.mark.parametrize(
    "year,count,genders,bodies",
    [
        (2026, 124, {"men": 74, "women": 50}, {"WBA": 47, "WBC": 49, "IBF": 43, "WBO": 42}),
        (2027, 2, {"men": 1, "women": 1}, {"WBA": 1, "WBO": 2}),
    ],
)
def test_complete_reviewed_census_has_unique_bouts_and_body_specific_evidence(year, count, genders, bodies):
    payload = registry(year)
    events, sources = reviewed_events(payload, year)
    rows = payload["events"]
    assert len(rows) == len(events) == count
    assert len({(r["start_date"], tuple(sorted(r["fighters"]))) for r in rows}) == count
    assert Counter(r["gender"] for r in rows) == genders
    assert Counter(title["body"] for row in rows for title in row["titles"]) == bodies
    notices = {s["id"]: s for s in sources}
    for row, event in zip(rows, events, strict=True):
        source = notices[row["source_id"]]
        assert row["start_date"] == row["end_date"]
        assert event.source_url == event.facts_source_url == source["url"]
        assert row["checked_date"] == event.facts_checked_date == "2026-10-31"
        assert source["input_url"] and len(source["sha256"]) == 64
        if source["kind"] == "wikipedia":
            assert source["license"] == "CC BY-SA 4.0"
            assert f"oldid={source['revision']}" in source["url"]
        else:
            assert source["kind"].startswith("boxing_") and source["publisher"]
            assert source["license"] == BOXING_LICENSE
    assert all(e["checked_date"] == "2026-10-31" and e["source_url"] for e in payload["exclusions"])


def test_classification_uses_belt_status_on_bout_date_and_does_not_infer_other_belts():
    rows = registry()["events"]

    def bodies(first, second):
        return {t["body"] for r in rows if first in r["title"] and second in r["title"] for t in r["titles"]}

    assert bodies("Gassiev", "Kadiru") == {"WBA"}
    assert bodies("Buatsi", "Hutchinson") == {"WBC"}
    assert bodies("Turhan", "Baumgardner") == {"IBF"}
    assert bodies("Bivol", "Eifert") == {"WBA", "IBF"}
    assert bodies("Bivol", "Smith") == {"WBA", "IBF", "WBO"}
    assert bodies("Fundora", "Zapotoczna") == {"WBC"}
    assert not bodies("Haney", "Paro")
    assert not bodies("Collazo", "Sandoval")
    assert not bodies("Figueroa", "Kameda")
    future = registry(2027)["events"]
    assert {r["start_date"] for r in future} == {"2027-01-09", "2027-01-23"}
    assert not any("Garner" in r["title"] or "Inoue" in r["title"] for r in future)
