import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from kickoff.open_schedules import refresh_open_schedules
from kickoff.reviewed_schedules import load_reviewed_schedules, reviewed_events
from tests.test_reviewed_schedules import fake_open_read

ROOT = Path(__file__).resolve().parents[1]


def registry(year=2026):
    return json.loads((ROOT / f"data/reviewed/{year}-weightlifting.json").read_text())


def test_worlds_include_every_split_group_and_one_event_per_real_session():
    payload = registry()
    rows = [r for r in payload["events"] if r["league"] == "IWF_WORLDS"]
    assert len(rows) == 50
    categories = [c for r in rows for c in r["categories"]]
    assert len(categories) == 51
    assert len({(c["gender"], c["weight_class"], c["group"]) for c in categories}) == 51
    men = {
        w: {c["group"] for c in categories if c["gender"] == "men" and c["weight_class"] == w}
        for w in ["60", "65", "70", "75", "85", "95", "110", "+110"]
    }
    assert men == {
        "60": {"A", "B"},
        "65": set("ABCD"),
        "70": {"A"},
        "75": set("ABCD"),
        "85": set("ABCD"),
        "95": set("ABCD"),
        "110": set("ABC"),
        "+110": set("ABC"),
    }
    combined = next(r for r in rows if len(r["categories"]) == 2)
    assert combined["title"].endswith("Women's 53 kg, Group D / Women's 57 kg, Group B")
    assert (combined["start_date"], combined["local_time"]) == ("2026-10-29", "11:00")
    unsplit = next(r for r in rows if "Men's 70 kg" in r["title"])
    assert "Group" not in unsplit["title"]
    events, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)[:2]
    assert not any(e.event_id == "iwf-worlds-2026" for e in events)
    assert all(e.event_type == "session" for e in events if e.league == "IWF_WORLDS")


def test_coverage_has_official_receipts_all_groups_and_distinct_masters_platforms():
    payload = registry()
    events, sources = reviewed_events(payload, 2026)
    assert Counter(e.league for e in events) == {
        "IWF_WORLDS": 50,
        "IWF_JUNIOR_WORLDS": 28,
        "IWF_YOUTH_WORLDS": 22,
        "WEIGHTLIFTING_EUROPE": 36,
        "WEIGHTLIFTING_ASIA": 17,
        "WEIGHTLIFTING_AFRICA": 15,
        "WEIGHTLIFTING_PAN_AMERICA": 16,
        "WEIGHTLIFTING_OCEANIA": 21,
        "WEIGHTLIFTING_COMMONWEALTH_GAMES": 15,
        "WEIGHTLIFTING_ASIAN_GAMES": 21,
        "MASTERS_WORLDS": 111,
    }
    assert all(e.start_time_utc and e.start_time_local and e.timezone for e in events)
    assert all(r["source_url"] and r["checked_date"] == "2026-10-28" for r in payload["events"])
    assert all(s["license"] == "Schedule facts; no data license granted" and s["hash_scope"] for s in sources)
    masters = [r for r in payload["events"] if r["league"] == "MASTERS_WORLDS"]
    assert sum(len(r["categories"]) for r in masters) == 167
    assert len({(r["start_date"], r["local_time"], r["title"].split("Platform ")[-1]) for r in masters}) == 111
    assert any("Group B" in r["title"] for r in masters)
    assert any(
        "53" in r["title"] and "58" in r["title"] and len(r["categories"]) == 2
        for r in payload["events"]
        if r["league"] == "WEIGHTLIFTING_COMMONWEALTH_GAMES"
    )
    asia = next(
        e for e in events if e.league == "WEIGHTLIFTING_ASIAN_GAMES" and e.title.endswith("Men's 110 kg, Group A")
    )
    assert asia.start_time_local == "2026-09-29T12:30:00+09:00"
    junior = next(e for e in events if e.league == "IWF_JUNIOR_WORLDS" and "Men's 60 kg, Group B" in e.title)
    assert junior.start_time_utc == "2026-05-02T08:00:00Z"  # Egypt summer time.


def test_2027_preserves_confirmed_dates_and_withholds_month_placeholders():
    payload = registry(2027)
    events, sources = reviewed_events(payload, 2027)
    assert len(events) == len(sources) == 6
    assert all(e.start_time_utc is e.start_time_local is None and e.timezone for e in events)
    masters = next(e for e in events if e.league == "MASTERS_WORLDS")
    assert (masters.calendar_date, masters.end_calendar_date) == ("2027-05-17", "2027-05-25")
    assert any("conflict" in s.get("coverage_notes", "").lower() for s in sources)
    assert not any(e.league in {"IWF_WORLDS", "IWF_JUNIOR_WORLDS", "IWF_YOUTH_WORLDS"} for e in events)
    assert len([x for x in payload["exclusions"] if x.get("announced_month")]) == 3
    assert all(x["source_url"] and x["checked_date"] for x in payload["exclusions"])
    assert not any("OLYMPIC" in e.league for e in events)


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p["sources"][0].update(url="https://example.org/unreviewed"),
        lambda p: p["sources"][0].update(license="CC0 1.0"),
        lambda p: p["events"][0].update(local_time="09:00+04:00"),
        lambda p: p["events"][0].update(local_time="25:00"),
        lambda p: p["events"][0].update(event_timezone="Unknown/Zone"),
        lambda p: p["events"][0].update(checked_date="2026-10"),
    ],
)
def test_weightlifting_rejects_unreviewed_source_or_false_clock_precision(change):
    payload = copy.deepcopy(registry())
    change(payload)
    with pytest.raises((ValueError, RuntimeError)):
        reviewed_events(payload, 2026)


def test_public_refresh_keeps_weightlifting_clocks_and_source_terms(monkeypatch, tmp_path):
    monkeypatch.setattr("kickoff.open_schedules.read_url", fake_open_read)
    path = refresh_open_schedules(2026, tmp_path, ROOT / "data/reviewed")
    bundle = json.loads(path.read_text())
    events = [e for e in bundle["events"] if e["sport"] == "weightlifting"]
    assert len(events) == 352
    assert all(e["start_time_utc"] and e["source_url"] for e in events)
    assert bundle["data_licenses"]["weightlifting"] == "Schedule facts; no data license granted"
    assert not any(
        "weightlifting" in e.get("sport", "")
        for component in bundle["components"]
        for e in json.loads((tmp_path / component["path"]).read_text())["events"]
    )
