import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from kickoff.reviewed_schedules import load_reviewed_schedules, reviewed_events

ROOT = Path(__file__).resolve().parents[1]


def registry(year=2026):
    return json.loads((ROOT / f"data/reviewed/{year}-climbing-sessions.json").read_text())


def one_round():
    payload = registry()
    row = next(r for r in payload["events"] if r["id"].endswith("keqiao-2026-women-s-boulder-qualification"))
    payload["events"] = [row]
    payload["sources"] = [s for s in payload["sources"] if s["id"] == row["source_id"]]
    return payload


def test_world_cup_rounds_replace_spans_and_keep_gender_discipline_and_local_instants():
    events, _ = reviewed_events(registry(), 2026)
    cups = [e for e in events if e.league == "IFSC_WORLD_CUP"]
    assert len({e.source_url for e in cups}) == 13
    assert all(e.event_type == "session" and e.calendar_date == e.end_calendar_date for e in cups)
    keqiao = [e for e in cups if "/world-climbing-series-keqiao-2026" in e.source_url]
    assert len(keqiao) == 6
    assert Counter(e.round_or_stage for e in keqiao) == {"qualification": 2, "semi-final": 2, "final": 2}
    women = next(e for e in keqiao if "Women" in e.tags and e.round_or_stage == "qualification")
    assert women.start_time_local == "2026-05-01T09:00:00+08:00"
    assert women.start_time_utc == "2026-05-01T01:00:00Z"
    assert women.timezone == "Asia/Shanghai"
    assert {t for e in keqiao for t in e.tags} == {"session", "Men", "Women", "Boulder"}
    all_events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    assert len([e for e in all_events if e.sport == "climbing"]) == len(events)
    assert not any(e.event_id == "world-climbing-series-2026-keqiao" for e in all_events)


def test_retained_sessions_keep_identities_and_resolved_clocks_without_false_precision():
    events, _ = reviewed_events(registry(), 2026)
    slc = [e for e in events if e.event_id.startswith("world-climbing-series-2026-salt-lake-city-")]
    santiago = [e for e in events if e.event_id.startswith("world-climbing-series-2026-santiago-")]
    assert len(slc) == 6 and len(santiago) == 10
    unknown = next(e for e in slc if "Women" in e.tags and e.round_or_stage == "qualification")
    assert unknown.start_time_utc is unknown.start_time_local is None
    assert unknown.timezone == "America/Denver" and "Time withheld" in unknown.subtitle
    speed = next(e for e in santiago if "Men" in e.tags and "Speed" in e.tags and e.round_or_stage == "qualification")
    assert speed.start_time_local == "2026-10-23T17:20:00-03:00"
    assert speed.start_time_utc == "2026-10-23T20:20:00Z"
    final = next(e for e in santiago if "Men" in e.tags and "Lead" in e.tags and e.round_or_stage == "final")
    assert final.start_time_local == "2026-10-25T19:00:00-03:00"
    shared = next(e for e in santiago if "Speed" in e.tags and e.round_or_stage == "final")
    assert shared.start_time_scope == "shared_session" and shared.start_time_utc == "2026-10-24T21:00:00Z"
    innsbruck = [e for e in events if e.source_url.endswith("world-climbing-series-innsbruck-2026")]
    assert len(innsbruck) == 12
    assert {e.start_time_local for e in innsbruck if e.round_or_stage == "final" and "Boulder" in e.tags} == {
        "2026-06-18T19:30:00+02:00",
        "2026-06-19T19:30:00+02:00",
    }


def test_youth_para_continental_and_mixed_events_keep_their_actual_identities():
    events, _ = reviewed_events(registry(), 2026)
    youth = [e for e in events if e.league == "IFSC_YOUTH_WORLDS"]
    assert len(youth) == 32
    assert all({"U17", "U19"} & set(e.tags) and {"Men", "Women"} & set(e.tags) for e in youth)
    assert {e.league for e in events} >= {
        "IFSC_WORLD_CUP",
        "IFSC_YOUTH_WORLDS",
        "IFSC_PARA_WORLD_CUP",
        "CLIMBING_EUROPE",
        "CLIMBING_ASIA",
        "CLIMBING_OCEANIA",
        "CLIMBING_PAN_AMERICA",
        "CLIMBING_CONTINENTAL_CUP",
        "CLIMBING_YOUTH_CONTINENTAL_CUP",
        "CLIMBING_CHALLENGER",
        "CLIMBING_NATIONS_GRAND_FINALE",
        "CLIMBING_ASIAN_GAMES",
        "CLIMBING_ASIAN_BEACH_GAMES",
    }
    assert any(e.title.startswith("European Youth Championships") for e in events if e.league == "CLIMBING_EUROPE")
    assert any(e.title.startswith("European Para Championships") for e in events if e.league == "CLIMBING_EUROPE")
    mixed = [e for e in events if e.source_url.endswith("world-climbing-series-krakow-2026") and "Mixed" in e.title]
    assert len(mixed) == 2
    assert all({"Men", "Women", "Speed"} <= set(e.tags) for e in mixed)
    unknown = next(
        e
        for e in events
        if e.source_url.endswith("world-climbing-series-wujiang-2026")
        and e.round_or_stage == "qualification"
        and "Lead" in e.tags
    )
    assert not {"Men", "Women"} & set(unknown.tags)
    assert "does not identify gender" in unknown.subtitle


def test_combined_event_stays_one_record_and_unknown_gender_is_not_invented():
    payload = one_round()
    payload["events"][0].update(disciplines=["Boulder", "Lead"], title="Women's Boulder & Lead Qualification")
    events, _ = reviewed_events(payload, 2026)
    assert len(events) == 1 and {"Boulder", "Lead", "Women"} <= set(events[0].tags)
    payload["events"][0].pop("gender")
    events, _ = reviewed_events(payload, 2026)
    assert not {"Men", "Women"} & set(events[0].tags)


def test_2027_dates_keep_published_disciplines_and_actual_qualifier_identity_without_guessed_rounds():
    payload = registry(2027)
    events, sources = reviewed_events(payload, 2027)
    assert all(e.start_time_utc is e.start_time_local is None and e.event_type == "tournament" for e in events)
    assert sum(e.league == "IFSC_WORLD_CUP" for e in events) == 13
    assert sum(e.league == "IFSC_PARA_WORLD_CUP" for e in events) == 5
    assert sum(e.league == "CLIMBING_OLYMPIC_QUALIFIERS" for e in events) == 4
    assert {e.league for e in events} >= {"IFSC_WORLDS", "IFSC_PARA_WORLDS", "IFSC_YOUTH_WORLDS", "CLIMBING_EUROPE"}
    worlds = next(e for e in events if e.league == "IFSC_WORLDS")
    assert (worlds.calendar_date, worlds.end_calendar_date) == ("2027-08-13", "2027-08-21")
    assert "October 17" in worlds.subtitle
    assert any(e.title.startswith("European Youth Championships") and "Lead" in e.tags for e in events)
    lima = next(e for e in events if e.league == "CLIMBING_PAN_AM_GAMES")
    assert (lima.calendar_date, lima.end_calendar_date) == ("2027-07-24", "2027-07-27")
    assert {"Men", "Women"} <= set(lima.tags)
    europe = next(e for e in events if e.league == "CLIMBING_EUROPEAN_GAMES")
    assert (europe.calendar_date, europe.end_calendar_date) == ("2027-06-24", "2027-06-27")
    assert {"Men", "Women", "Boulder", "Lead", "Speed"} <= set(europe.tags)
    assert not any(e.league == "CLIMBING_OLYMPICS" for e in events)
    assert any("Boulder" in e["competition"] and "confirmed" in e["reason"] for e in payload["exclusions"])
    assert all(r["source_url"] and r["checked_date"] == "2026-10-28" for r in payload["events"])
    assert all(s["checked_date"] == "2026-10-28" for s in sources)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["sources"][0].update(url="https://unreviewed.example/calendar"),
        lambda p: p["sources"][0].pop("kind"),
        lambda p: p["sources"][0].update(license="MIT"),
        lambda p: p["sources"][0].update(sha256=""),
        lambda p: p["sources"][0].update(checked_date="later"),
        lambda p: p["events"][0].update(local_time="25:00"),
        lambda p: p["events"][0].update(local_time="09:00+08:00"),
        lambda p: p["events"][0].update(event_timezone=None),
        lambda p: p["events"][0].update(timezone="Asia/Shanghai"),
        lambda p: p["events"][0].update(end_date="2026-05-02"),
        lambda p: p["events"][0].update(league="IWF_WORLDS"),
        lambda p: p["events"][0].update(disciplines=["Ice"]),
        lambda p: p["events"][0].update(disciplines=[]),
        lambda p: p["events"][0].update(local_time=None, notes=""),
        lambda p: p["events"][0].update(start_time_scope="guessed"),
        lambda p: p["events"][0].update(start_time_scope="shared_session", local_time=None),
        lambda p: p["events"][0].update(gender="combined"),
        lambda p: p["events"][0].update(genders=["men", "women"]),
        lambda p: p["events"][0].update(round_or_stage="practice"),
    ],
)
def test_climbing_registry_rejects_invalid_provenance_or_false_precision(mutate):
    payload = copy.deepcopy(one_round())
    mutate(payload)
    with pytest.raises(ValueError):
        reviewed_events(payload, 2026)


def test_offline_refresh_preserves_official_climbing_sources_and_metadata(monkeypatch, tmp_path):
    from kickoff.open_schedules import refresh_open_schedules
    from tests.test_reviewed_schedules import fake_open_read

    def read(url):
        body = fake_open_read(url)
        if "/2027/" in url:
            body = body.replace(b"seasons/2026/", b"seasons/2027/").replace(b"2026-03-01", b"2027-03-01")
        return body

    monkeypatch.setattr("kickoff.open_schedules.read_url", read)
    for year in [2026, 2027]:
        result = refresh_open_schedules(year, tmp_path / "published", ROOT / "data/reviewed")
        bundle = json.loads(result.read_text())
        published = [e for e in bundle["events"] if e["source"] == "world_climbing"]
        reviewed, sources = reviewed_events(registry(year), year)
        assert {e["event_id"] for e in published} == {e.event_id for e in reviewed}
        assert len([s for s in bundle["sources"] if s.get("kind") == "world_climbing"]) == len(sources)
        assert bundle["data_licenses"]["world_climbing"] == "Schedule facts; no data license granted"
        assert "World Climbing World Cup records" in bundle["coverage"]


def test_repeated_duration_rows_do_not_duplicate_ostermundigen_rounds():
    events, _ = reviewed_events(registry(), 2026)
    stop = [e for e in events if e.source_url.endswith("world-climbing-europe-series-ostermundigen-2026")]
    assert len(stop) == 6
    assert Counter(e.round_or_stage for e in stop) == {"qualification": 2, "semi-final": 2, "final": 2}
    assert all({"Men", "Women"} & set(e.tags) for e in stop)
    assert all(e.start_time_local.endswith("+02:00") for e in stop)


def test_santa_fe_uses_updated_organizer_rounds_and_host_timezone_without_invented_following_clocks():
    events, sources = reviewed_events(registry(), 2026)
    games = [e for e in events if e.league == "CLIMBING_SOUTH_AM_GAMES"]
    assert len(games) == 12
    assert {e.round_or_stage for e in games} == {"qualification", "final"}
    assert {e.calendar_date for e in games} == {f"2026-09-{day}" for day in [22, 23, 24, 25]}
    assert all(e.timezone == "America/Argentina/Cordoba" for e in games)
    women = next(e for e in games if "Women" in e.tags and "Boulder" in e.tags and e.round_or_stage == "final")
    assert women.start_time_local == "2026-09-22T17:00:00-03:00"
    assert women.start_time_utc == "2026-09-22T20:00:00Z"
    speed = [e for e in games if "Speed" in e.tags]
    assert len(speed) == 4 and all(e.start_time_scope == "shared_session" for e in speed)
    assert {e.start_time_local[11:16] for e in speed} == {"10:50", "11:15"}
    assert sum(e.start_time_utc is None for e in games) == 2
    assert any(s["url"].startswith("https://santafe2026.ar/") for s in sources)


def test_reviewed_climbing_hosts_keep_explicit_country_facts():
    from kickoff.reviewed_schedules import load_reviewed_schedules

    for year, count in [(2026, 441), (2027, 52)]:
        events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", year)
        climbing = [event for event in events if event.sport == "climbing"]
        assert len(climbing) == count
        assert all(event.country for event in climbing)
        prague = next((event for event in climbing if "Prague" in event.title), None)
        if prague:
            assert prague.country == "Czechia"
        for event in climbing:
            if "Rock Master" in (event.venue or ""):
                assert event.country == "Italy"
            if event.venue == "Los Angeles":
                assert event.country == "United States"
