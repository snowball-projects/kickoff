"""Offline integration of source authority, retained facts and optional lookups."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from urllib.error import HTTPError

import pytest

from kickoff import open_schedules as schedules
from kickoff.incremental import RefreshPlan, event_from_public
from kickoff.refresh_state import Baseline, SourceUnit
from kickoff.web import _event_payload
from tests.test_incremental import event as public_event
from tests.test_reviewed_schedules import fake_open_read

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


@pytest.fixture
def offline(monkeypatch):
    requests = []
    state = {
        "revision": "a" * 40,
        "old_rows": [
            {
                "date": "2026-05-01",
                "team1": "Old Home",
                "team2": "Old Away",
                "round": "Round 1",
                "score": {"ft": [1, 0]},
            },
            {
                "date": "2025-09-01",
                "team1": "Other Home",
                "team2": "Other Away",
                "round": "Round 2",
                "score": {"ft": [0, 0]},
            },
        ],
    }
    monkeypatch.setattr(schedules, "FOOTBALL", {"en.1": schedules.FOOTBALL["en.1"]})
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: ([], [], []))
    monkeypatch.setattr(schedules, "fill_reviewed_countries", lambda _: ([], []))

    def read(url):
        requests.append(url)
        if "/commits/" in url:
            return json.dumps({"sha": state["revision"]}).encode()
        if url.endswith("2025-26/en.1.json"):
            return json.dumps({"matches": state["old_rows"]}).encode()
        if url.endswith("2026-27/en.1.json"):
            return json.dumps(
                {"matches": [{"date": "2026-11-10", "team1": "New Home", "team2": "New Away", "round": "Round 1"}]}
            ).encode()
        return fake_open_read(url)

    monkeypatch.setattr(schedules, "read_url", read)
    return requests, state


def run(tmp_path, name, plan=None, **kwargs):
    return json.loads(schedules.refresh_open_schedules(2026, tmp_path / name, plan=plan, **kwargs).read_text())


def published_baseline(bundle, units, frozen):
    return Baseline(
        manifest={"available_seasons": [2026]}, bundles={"2026.json": bundle}, units=units, frozen_ids=frozenset(frozen)
    )


def test_plan_none_retains_legacy_feed_callback_signature(offline, tmp_path):
    calls = []

    def fetch(year):
        calls.append(year)
        return []

    run(tmp_path, "legacy", feeds={"NFL": ("espn", fetch)})
    assert calls == [2026]


def test_old_complete_file_reuses_logical_key_across_head_change_with_exact_receipts(offline, tmp_path):
    requests, state = offline
    cold = RefreshPlan(Baseline(reason="first_run"), NOW)
    first = run(tmp_path, "first", cold)
    key = "github:openfootball/football.json:2025-26/en.1.json"
    unit = cold.units[key]
    assert len(unit.event_ids) == 2 and unit.closed and unit.complete and not unit.unresolved
    receipt = next(r for r in first["input_evidence"] if r["url"] == unit.source_url)
    assert receipt["league"] == "EPL" and receipt["checked_date"] == unit.observed_at[:10]
    assert sum(e["event_id"] in unit.event_ids for e in first["events"]) == 1
    # Full normalized footprint includes the other year, enabling honest closure.
    outside = schedules.football_events({"matches": state["old_rows"]}, "en.1", "2025-26", "https://example.org")[1]
    baseline = published_baseline(first, cold.units, unit.event_ids)
    baseline.bundles["2025.json"] = {**first, "season": 2025, "events": [_event_payload(outside)]}
    baseline.manifest["available_seasons"] = [2025, 2026]
    old = next(e for e in first["events"] if e["event_id"] in unit.event_ids)
    requests.clear()
    state["revision"] = "b" * 40
    warm = RefreshPlan(baseline, NOW)
    second = run(tmp_path, "second", warm)
    assert not any(url.endswith("2025-26/en.1.json") for url in requests)
    assert any("b" * 40 in url for url in requests if url.endswith("2026-27/en.1.json"))
    assert next(e for e in second["events"] if e["event_id"] == old["event_id"]) == old
    assert warm.units[key].observed_at == unit.observed_at
    old_receipts = [r for r in first["input_evidence"] if r["url"] == unit.source_url]
    assert old_receipts and all(r in second["input_evidence"] for r in old_receipts)
    assert any(s.get("revision") == "a" * 40 for s in second["sources"])
    assert len(second["input_evidence"]) == len({json.dumps(r, sort_keys=True) for r in second["input_evidence"]})


def test_prefilter_footprint_retains_undated_cancelled_and_missing_result_ids(offline, tmp_path):
    _, state = offline
    state["old_rows"] += [
        {"team1": "Undated", "team2": "Away", "round": "Round 3"},
        {"date": "2026-05-02", "team1": "Cancelled", "team2": "Away", "round": "Round 4", "status": "canceled"},
        {"date": "2026-05-03", "team1": "Postponed", "team2": "Away", "round": "Round 5", "status": "postponed"},
        {"date": "2026-05-04", "team1": "Unfinished", "team2": "Away", "round": "Round 6"},
    ]
    plan = RefreshPlan(Baseline(reason="first"), NOW)
    run(tmp_path, "footprint", plan)
    unit = plan.units["github:openfootball/football.json:2025-26/en.1.json"]
    assert len(unit.event_ids) == 6
    assert set(unit.unresolved.values()) == {"undated", "canceled", "postponed", "missing_final_score"}
    assert unit.complete and unit.closed
    assert plan.try_reuse(unit.key) is None


def test_f1_primary_footprint_is_complete_but_never_closed_by_past_race_date(offline, tmp_path):
    plan = RefreshPlan(Baseline(reason="first"), NOW)
    run(tmp_path, "f1", plan)
    key = "github:f1db/f1db:src/data/seasons/2026/races"
    assert plan.units[key].children == ("github:f1db/f1db:src/data/seasons/2026/races/01/race.yml",)
    child = plan.units[plan.units[key].children[0]]
    assert child.event_ids == ("f1db-1234-race",)
    assert child.unresolved == {"f1db-1234-race": "missing_confirmed_result"}
    assert child.complete and not child.closed and not plan.units[key].closed
    assert not any("results.yml" in url for url in offline[0])


def test_frozen_events_never_enter_targeted_time_lookup_and_public_merge_wins(offline, monkeypatch, tmp_path):
    cold = run(tmp_path, "cold")
    old = next(e for e in cold["events"] if e["league"] == "EPL")
    plan = RefreshPlan(published_baseline(cold, {}, [old["event_id"]]), NOW)
    looked_up = []

    def clocks(events, year):
        looked_up.extend(e.event_id for e in events)
        for e in events:
            e.facts_checked_date = "2099-01-01"
        return []

    monkeypatch.setattr(schedules, "fill_missing_start_times", clocks)
    warm = run(tmp_path, "warm", plan, enrich_times=True)
    assert old["event_id"] not in looked_up and looked_up
    assert next(e for e in warm["events"] if e["event_id"] == old["event_id"]) == old


def test_successful_feed_empty_observation_removes_old_visible_unfrozen_row_and_keeps_hidden_locator(offline, tmp_path):
    row = public_event("old-nfl", status="scheduled")
    source = SourceUnit(
        "nfl-request", "https://example.org/nfl", "2026-11-03", ("old-nfl",), complete=True, closed=False
    )
    plan = RefreshPlan(published_baseline({"season": 2026, "events": [row]}, {source.key: source}, []), NOW)

    def fetch(year, *, plan):
        plan.observe(
            SourceUnit(
                source.key,
                source.source_url,
                "2026-11-04",
                ("old-nfl",),
                {"old-nfl": "postponed"},
                complete=True,
                closed=False,
            )
        )
        plan.receipts[source.key] = {"url": source.source_url, "sha256": "c" * 64, "league": "NFL", "kind": "espn"}
        return []

    result = run(tmp_path, "empty", plan, feeds={"NFL": ("espn", fetch)})
    assert "old-nfl" not in {e["event_id"] for e in result["events"]}
    assert plan.units[source.key].unresolved == {"old-nfl": "postponed"}
    assert any(r.get("league") == "NFL" for r in result["input_evidence"])


def test_cross_feed_duplicate_rejected_before_frozen_merge_can_hide_it(offline, tmp_path):
    first = run(tmp_path, "first")
    existing = next(e for e in first["events"] if e["league"] == "EPL")
    impostor = event_from_public({**existing, "source": "espn", "league": "NFL"})
    plan = RefreshPlan(published_baseline(first, {}, [existing["event_id"]]), NOW)
    with pytest.raises(ValueError, match="Duplicate event identity"):
        run(tmp_path, "duplicate", plan, feeds={"NFL": ("espn", lambda year, *, plan: [impostor])})


def test_only_private_confirmed_result_flag_registers_result_freeze_candidates(offline, tmp_path):
    complete = event_from_public(
        public_event(
            "complete", result={"kind": "podium"}, is_regular_season=True, start_time_local="2026-11-01T12:00:00-05:00"
        ),
        result_complete=True,
    )
    partial = event_from_public(
        public_event(
            "partial", result={"kind": "podium"}, is_regular_season=True, start_time_local="2026-11-01T12:00:00-05:00"
        )
    )
    plan = RefreshPlan(Baseline(reason="first"), NOW)
    run(tmp_path, "results", plan, feeds={"NFL": ("espn", lambda year, *, plan: [complete, partial])})
    assert plan.confirmed_results == {"complete"}


def test_reviewed_observation_uses_historical_check_date_and_removal_is_authoritative(offline, monkeypatch, tmp_path):
    row = event_from_public(
        public_event(
            "reviewed",
            sport="motorsport",
            league="MOTOGP",
            event_type="race",
            source="wikipedia",
            source_url="https://example.org/reviewed",
            status="past schedule",
        )
    )
    notice = {
        "id": "reviewed-source",
        "url": row.source_url,
        "kind": "wikipedia",
        "checked_date": "2026-09-01",
        "license": "CC BY-SA 4.0",
    }
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: ([deepcopy(row)], [notice], []))
    cold = RefreshPlan(Baseline(reason="first"), NOW)
    first = run(tmp_path, "reviewed", cold)
    unit = cold.units["reviewed:2026:reviewed-source"]
    assert unit.observed_at == "2026-09-01" and not unit.closed
    warm = RefreshPlan(published_baseline(first, cold.units, []), NOW)
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: ([], [], []))
    result = run(tmp_path, "removed", warm)
    assert "reviewed" not in {e["event_id"] for e in result["events"]}
    assert warm.current[unit.key].observed_at == "2026-09-01"
    assert warm.units[unit.key].unresolved == {"reviewed": "missing_confirmed_result"}


def test_real_startbook_loader_skips_entire_frozen_cohort_without_network(offline, monkeypatch, tmp_path):
    from kickoff.weightlifting_startlists import StartListLoader
    from tests.test_weightlifting_startlists import event, setup_catalog

    reviewed = tmp_path / "reviewed"
    reviewed.mkdir()
    setup_catalog(monkeypatch, reviewed)
    item = event("session")
    item.source_url = "https://ewf.sport/session"
    sources, evidence = StartListLoader().enrich([item], reviewed, 2026)
    old = _event_payload(item)
    notice = {
        "id": "session-source",
        "url": item.source_url,
        "kind": "weightlifting",
        "checked_date": "2026-09-01",
        "license": "Schedule facts; no data license granted",
    }
    fresh = event("session")
    fresh.source_url = item.source_url
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: ([deepcopy(fresh)], [notice], []))
    previous = {
        "season": 2026,
        "events": [old],
        "sources": sources,
        "input_evidence": evidence,
        "data_licenses": {"weightlifting": "Schedule facts; no data license granted"},
    }
    plan = RefreshPlan(published_baseline(previous, {}, ["session"]), NOW)
    result = run(tmp_path, "book", plan, reviewed_dir=reviewed, start_list_loader=StartListLoader())
    assert next(e for e in result["events"] if e["event_id"] == "session") == old
    assert sources[0] in result["sources"] and evidence[0] in result["input_evidence"]


def test_mixed_startbook_receives_full_cohort_but_frozen_public_athletes_keep_old_facts(offline, monkeypatch, tmp_path):
    from kickoff.models import Participant
    from tests.test_weightlifting_startlists import event

    rows = [event("first"), event("second")]
    for row in rows:
        row.source_url = "https://ewf.sport/session"

    def athlete(name, total, checked):
        return Participant(
            name,
            name,
            entity_type="athlete",
            metadata={
                "entry_total_kg": total,
                "start_list_category": "Women's48kgA",
                "start_list_nation": "WRT",
                "start_list_guest": False,
                "start_list_source_url": "https://ewf.sport/book.pdf",
                "start_list_checked_date": checked,
            },
        )

    rows[0].participants = [athlete("Old athlete", 111, "2026-10-01")]
    old = _event_payload(rows[0])
    notices = [
        {
            "id": "book",
            "url": rows[0].source_url,
            "checked_date": "2026-10-01",
            "kind": "weightlifting",
            "license": "Schedule facts; no data license granted",
        }
    ]
    monkeypatch.setattr(schedules, "load_reviewed_schedules", lambda *_: (deepcopy(rows), notices, []))

    class Book:
        def __init__(self):
            self.calls = []

        def enrich(self, cohort, reviewed_dir, year, *, skip_ids):
            self.calls.append(([e.event_id for e in cohort], skip_ids))
            if not all(e.event_id in skip_ids for e in cohort):
                for e in cohort:
                    e.participants = [athlete("Fresh athlete", 222, "2026-11-04")]
            return [], []

    loader = Book()
    plan = RefreshPlan(published_baseline({"season": 2026, "events": [old]}, {}, ["first"]), NOW)
    output = run(tmp_path, "mixed-book", plan, start_list_loader=loader)
    assert loader.calls == [(["first", "second"], frozenset({"first"}))]
    by_id = {e["event_id"]: e for e in output["events"]}
    assert by_id["first"] == old
    assert by_id["second"]["participants"][0]["entry_total_kg"] == 222


def test_retained_metadata_is_limited_to_relevant_league_and_publication_year(offline, tmp_path):
    first = run(tmp_path, "metadata-first")
    old = next(e for e in first["events"] if e["league"] == "EPL")
    removed = public_event("removed-nba", league="NBA", sport="basketball", source="nba", status="scheduled")
    other_year = public_event("other-year", league="NBA", sport="basketball", source="nba")
    source = SourceUnit("nba", "https://example.org/nba", "2026-11-03", ("removed-nba",), complete=True)
    baseline = Baseline(
        manifest={"available_seasons": [2025, 2026]},
        bundles={
            "epl.json": {
                "season": 2026,
                "events": [old],
                "sources": [{"kind": "openfootball", "url": "https://example.org/retained-epl"}],
                "input_evidence": [
                    {"kind": "openfootball", "url": "https://example.org/retained-file", "sha256": "f" * 64}
                ],
                "data_licenses": {"retained_identity_kind": "Original terms"},
            },
            "nba.json": {
                "season": 2026,
                "events": [removed],
                "sources": [{"kind": "nba", "url": "https://example.org/removed-league"}],
            },
            "2025.json": {
                "season": 2025,
                "events": [other_year],
                "sources": [{"kind": "nba", "url": "https://example.org/other-year"}],
            },
        },
        units={source.key: source},
        frozen_ids=frozenset({old["event_id"], "other-year"}),
    )
    plan = RefreshPlan(baseline, NOW)

    def fetch(year, *, plan):
        plan.observe(SourceUnit(source.key, source.source_url, "2026-11-04", complete=True, closed=False))
        return []

    output = run(tmp_path, "metadata-second", plan, feeds={"NBA": ("espn", fetch)})
    urls = {s["url"] for s in output["sources"]}
    assert "https://example.org/retained-epl" in urls
    assert "https://example.org/removed-league" not in urls and "https://example.org/other-year" not in urls
    assert output["data_licenses"]["retained_identity_kind"] == "Original terms"
    assert any(r["url"] == "https://example.org/retained-file" for r in output["input_evidence"])


def test_future_file_404_cannot_authoritatively_remove_a_previously_published_appointment(
    offline, monkeypatch, tmp_path
):
    old = public_event(
        "future",
        source="openfootball",
        league="EPL",
        sport="soccer",
        status="scheduled",
        season="2027-28",
        calendar_date="2027-08-01",
        end_calendar_date="2027-08-01",
        start_time_utc=None,
        start_time_local=None,
    )
    key = "github:openfootball/football.json:2027-28/en.1.json"
    unit = SourceUnit(
        key,
        f"https://raw.githubusercontent.com/openfootball/football.json/{'a' * 40}/2027-28/en.1.json",
        "2026-11-03",
        ("future",),
        {"future": "missing_final_score"},
        complete=True,
        closed=False,
    )
    previous = Baseline(
        manifest={"available_seasons": [2027]},
        bundles={"2027.json": {"season": 2027, "events": [old]}},
        units={key: unit},
    )
    plan = RefreshPlan(previous, NOW)
    original = schedules.read_url

    def read(url):
        if (
            url.endswith("2027-28/en.1.json")
            or url.endswith("2027/worldcup.json")
            or "/contents/src/data/seasons/2027/" in url
        ):
            raise HTTPError(url, 404, "currently unavailable", {}, None)
        return original(url)

    monkeypatch.setattr(schedules, "read_url", read)
    output = json.loads(schedules.refresh_open_schedules(2027, tmp_path / "future404", plan=plan).read_text())
    assert output["events"] == [old]
    assert plan.current[key].complete is False and plan.current[key].closed is False
    assert plan.units[key].unresolved == {"future": "missing_final_score"}
