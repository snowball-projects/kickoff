import hashlib
import json
import zlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from kickoff.refresh_state import (
    SourceUnit,
    build_refresh_state,
    event_is_frozen,
    load_published_baseline,
    team_result_confirmed,
    unit_is_frozen,
)

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def game(identity="finished", **changes):
    return {
        "event_id": identity,
        "sport": "football",
        "league": "NFL",
        "event_type": "game",
        "status": "finished",
        "facts_checked_date": "2025-01-02",
        "participants": [
            {"name": "First", "entity_type": "team", "final_score": 0},
            {"name": "Second", "entity_type": "team", "final_score": 20},
        ],
        **changes,
    }


def unit(key="week", **changes):
    return SourceUnit(
        **{
            "key": key,
            "source_url": "https://example.org/schedule/2026/week/1",
            "observed_at": "2026-11-03",
            "event_ids": ("finished",),
            "complete": True,
            "closed": True,
            **changes,
        }
    )


def encode(value):
    return json.dumps(value, separators=(",", ":")).encode()


def publication(events=None, units=None, **policy):
    events = [game()] if events is None else events
    manifest = {
        "schema_version": "1",
        "available_seasons": [2026],
        "seasons": {
            "2026": {
                "season": 2026,
                "all_events": len(events),
                "updated_at": NOW.isoformat(),
                "sports": [
                    {"value": "football", "leagues": ["NFL"], "file": "2026-football-nfl.json", "count": len(events)}
                ],
            }
        },
    }
    files = {
        "manifest.json": encode(manifest),
        "2026-football-nfl.json": encode(
            {"schema_version": "1", "season": 2026, "updated_at": NOW.isoformat(), "events": events, "sources": []}
        ),
    }
    state = build_refresh_state(files, [unit()] if units is None else units, published_at=NOW, **policy)
    files["refresh-state.json"] = encode(state)
    return files


def baseline(files, **kwargs):
    return load_published_baseline(files.__getitem__, now=NOW, expected_years=[2026], **kwargs)


def change_state(files, /, **changes):
    state = json.loads(files["refresh-state.json"])
    state.update(changes)
    files["refresh-state.json"] = encode(state)


def rebind(files):
    change_state(
        files,
        files={name: hashlib.sha256(body).hexdigest() for name, body in files.items() if name != "refresh-state.json"},
    )


def test_only_complete_source_result_freezes_immediately_with_zero_scores_and_no_role_invention():
    assert team_result_confirmed(game())
    assert event_is_frozen(game(), NOW)
    for event in [
        game(status="scheduled"),
        game(status="postponed"),
        game(participants=[]),
        game(event_type="tournament"),
        game(participants=[{"name": "First", "entity_type": "team", "final_score": 2}]),
        game(participants=[{"name": "First", "entity_type": "team", "final_score": True}] * 2),
        game(participants=[{"name": "TBD", "entity_type": "team", "final_score": 2}] * 2),
        game(participants=[{"name": "First", "entity_type": "team"}, {"name": "Second", "entity_type": "team"}]),
    ]:
        assert not event_is_frozen(event, NOW)
    assert "role" not in game()["participants"][0]


def test_never_result_needs_explicit_capability_and_actual_end_not_age_or_failure():
    event = game(status="scheduled", participants=[], event_type="appointment")
    assert not event_is_frozen(event, NOW)
    assert not event_is_frozen(event, NOW, never_result=lambda _: True)
    assert not event_is_frozen(event, NOW, never_result=lambda _: True, actual_end=lambda _: None)
    assert not event_is_frozen(event, NOW, never_result=lambda _: False, actual_end=lambda _: NOW - timedelta(days=100))
    for days, expected in [(13, False), (14, True), (15, True)]:
        assert (
            event_is_frozen(
                event, NOW, never_result=lambda _: True, actual_end=lambda _, days=days: NOW - timedelta(days=days)
            )
            is expected
        )
    for status in ["postponed", "canceled", "cancelled", "undecided"]:
        assert not event_is_frozen(
            {**event, "status": status},
            NOW,
            result_confirmed=lambda _: True,
            never_result=lambda _: True,
            actual_end=lambda _: NOW - timedelta(days=100),
        )


def test_closed_unit_requires_every_member_and_every_discovery_child():
    final = unit()
    mixed = unit("mixed", event_ids=("finished", "future"))
    unresolved = unit("unresolved", event_ids=("finished", "dropped"), unresolved={"dropped": "postponed"})
    discovery = unit("discovery", event_ids=(), children=("week",))
    units = {x.key: x for x in [final, mixed, unresolved, discovery]}
    assert unit_is_frozen("week", {"finished"}, units)
    assert unit_is_frozen("discovery", {"finished"}, units)
    assert not unit_is_frozen("mixed", {"finished"}, units)
    assert not unit_is_frozen("unresolved", {"finished", "dropped"}, units)
    assert not unit_is_frozen("missing", {"finished"}, units)
    assert not unit_is_frozen("week", {"finished"}, {"week": replace(final, complete=False)})
    assert not unit_is_frozen("week", {"finished"}, {"week": replace(final, closed=False)})
    assert not unit_is_frozen("discovery", {"finished"}, {"discovery": discovery})
    assert not unit_is_frozen("loop", {"finished"}, {"loop": unit("loop", children=("loop",))})


def test_empty_historical_closed_observed_window_can_skip_but_future_open_unbounded_cannot():
    empty = unit(event_ids=(), start="2026-10-01", end="2026-10-02")
    assert unit_is_frozen("week", set(), {"week": empty})
    for changed in [
        replace(empty, closed=False),
        replace(empty, complete=False),
        replace(empty, end=None),
        replace(empty, start=None),
        replace(empty, end="2026-12-01"),
        replace(empty, observed_at="2026-10-02"),
    ]:
        assert not unit_is_frozen("week", set(), {"week": changed})


def test_baseline_preserves_public_facts_actual_check_dates_and_source_observations():
    files = publication()
    loaded = baseline(files)
    assert not loaded.full_rebuild
    assert loaded.events == {"finished": game()}
    assert loaded.events["finished"]["facts_checked_date"] == "2025-01-02"
    assert loaded.units["week"].observed_at == "2026-11-03"
    assert loaded.frozen_ids == {"finished"}
    assert loaded.year_bundles[2026] == [json.loads(files["2026-football-nfl.json"])]
    assert set(loaded.bundles) == {"2026-football-nfl.json"}


def test_dropped_postponed_members_remain_unresolved_without_becoming_public_events():
    observed = unit(
        event_ids=("finished", "canceled", "postponed"), unresolved={"canceled": "canceled", "postponed": "postponed"}
    )
    loaded = baseline(publication(units=[observed]))
    assert not loaded.full_rebuild
    assert set(loaded.events) == {"finished"}
    assert not unit_is_frozen("week", loaded.frozen_ids, loaded.units)


def test_frozen_decision_survives_new_parser_and_optional_predicate_only_adds_new_freezes():
    files = publication([game("finished", status="scheduled")], frozen_ids={"finished"})
    assert baseline(files, result_confirmed=lambda _: False).frozen_ids == {"finished"}
    files = publication(frozen_ids=set())
    assert baseline(files).frozen_ids == set()
    assert baseline(files, result_confirmed=lambda _: True).frozen_ids == {"finished"}


@pytest.mark.parametrize("age,ok", [(0, True), (72, True), (72.01, False), (-0.01, False)])
def test_maximum_age_uses_successful_publication_not_ancient_fact_dates(age, ok):
    files = publication()
    change_state(files, published_at=(NOW - timedelta(hours=age)).isoformat())
    assert baseline(files).full_rebuild is not ok


def test_force_full_performs_no_reads():
    def read(_):
        pytest.fail("force full must not read old data")

    assert load_published_baseline(read, now=NOW, expected_years=[2026], force_full=True).reason == "force_full"


@pytest.mark.parametrize("filename", ["refresh-state.json", "manifest.json", "2026-football-nfl.json"])
def test_missing_or_unreadable_or_malformed_file_falls_back(filename):
    files = publication()
    del files[filename]
    assert baseline(files).full_rebuild
    files = publication()
    files[filename] = b"{broken"
    assert baseline(files).full_rebuild

    def unreadable(_):
        raise OSError("offline")

    assert load_published_baseline(unreadable, now=NOW, expected_years=[2026]).full_rebuild


def test_mixed_cached_generations_or_incomplete_hash_inventory_cannot_reuse():
    files = publication()
    files["2026-football-nfl.json"] += b" "
    assert baseline(files).reason == "file_hash"
    files = publication()
    state = json.loads(files["refresh-state.json"])
    del state["files"]["2026-football-nfl.json"]
    change_state(files, files=state["files"])
    assert baseline(files).reason == "file_coverage"
    files = publication()
    change_state(files, files={"../outside.json": "a" * 64})
    assert baseline(files).reason == "file_name"


@pytest.mark.parametrize("mutation", ["duplicate", "count", "timestamp", "year", "league"])
def test_bound_but_inconsistent_public_files_still_cannot_reuse(mutation):
    files = publication()
    bundle = json.loads(files["2026-football-nfl.json"])
    if mutation == "duplicate":
        bundle["events"] *= 2
        manifest = json.loads(files["manifest.json"])
        manifest["seasons"]["2026"]["sports"][0]["count"] = 2
        manifest["seasons"]["2026"]["all_events"] = 2
        files["manifest.json"] = encode(manifest)
    elif mutation == "count":
        bundle["events"] = []
    elif mutation == "timestamp":
        bundle["updated_at"] = "2026-11-01T00:00:00Z"
    elif mutation == "year":
        bundle["season"] = 2025
    else:
        bundle["events"][0]["league"] = "OTHER"
    files["2026-football-nfl.json"] = encode(bundle)
    rebind(files)
    assert baseline(files).full_rebuild


def test_incomplete_membership_unknown_freeze_missing_year_and_graph_failures():
    files = publication()
    assert load_published_baseline(files.__getitem__, now=NOW, expected_years=[2026, 2027]).reason == "missing_years"
    for change in [
        {"frozen_event_ids": ["not-published"]},
        {"units": []},
        {"units": [unit(children=("absent",)).to_dict()]},
        {"units": [unit(children=("week",)).to_dict()]},
        {"units": [unit(event_ids=("finished", "not-published")).to_dict()]},
        {"units": [unit(observed_at="2027-01-01").to_dict()]},
        {"units": [{**unit().to_dict(), "raw_payload": {}}]},
        {"units": [{**unit().to_dict(), "event_ids": {"finished": {"private": "payload"}}}]},
    ]:
        changed = publication()
        change_state(changed, **change)
        assert baseline(changed).full_rebuild


def test_state_builder_rejects_unknown_freezes_and_missing_observations():
    with pytest.raises(ValueError, match="unknown_frozen"):
        publication(frozen_ids={"unknown"})
    with pytest.raises(ValueError, match="unit_coverage"):
        publication(units=[])


@pytest.mark.parametrize("error", [EOFError("truncated gzip stream"), zlib.error("corrupt gzip stream")])
@pytest.mark.parametrize("filename", ["refresh-state.json", "2026-football-nfl.json"])
def test_compressed_read_failure_discards_whole_baseline(error, filename):
    files = publication()

    def read(name):
        if name == filename:
            raise error
        return files[name]

    loaded = load_published_baseline(read, now=NOW, expected_years=[2026])
    assert loaded.reason == "missing_or_invalid_baseline"
    assert loaded.full_rebuild
    assert loaded.bundles == {}
    assert loaded.frozen_ids == frozenset()


def test_injected_result_presence_does_not_freeze_a_source_scheduled_event():
    assert not event_is_frozen(game(status="scheduled"), NOW, result_confirmed=lambda _: True)
    assert event_is_frozen(game(status="finished"), NOW, result_confirmed=lambda _: True)


def test_tba_opponent_is_not_a_named_final_score_result():
    event = game(
        participants=[
            {"name": "First", "entity_type": "team", "final_score": 2},
            {"name": " TBA ", "entity_type": "team", "final_score": 1},
        ]
    )
    assert not team_result_confirmed(event)
    assert not event_is_frozen(event, NOW)
