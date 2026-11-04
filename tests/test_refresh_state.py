import hashlib
import json
import zlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from kickoff.refresh_state import (
    SourceUnit,
    build_refresh_state,
    end_bound_aged,
    event_is_frozen,
    load_published_baseline,
    team_result_confirmed,
    unit_is_frozen,
)

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
OLD_END = NOW - timedelta(days=3)


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


def publication(events=None, units=None, *, at=NOW, **policy):
    events = [game()] if events is None else events
    manifest = {
        "schema_version": "1",
        "available_seasons": [2026],
        "seasons": {
            "2026": {
                "season": 2026,
                "all_events": len(events),
                "updated_at": at.isoformat(),
                "sports": [
                    {"value": "football", "leagues": ["NFL"], "file": "2026-football-nfl.json", "count": len(events)}
                ],
            }
        },
    }
    files = {
        "manifest.json": encode(manifest),
        "2026-football-nfl.json": encode(
            {"schema_version": "1", "season": 2026, "updated_at": at.isoformat(), "events": events, "sources": []}
        ),
    }
    if "ended_before" not in policy and "actual_end" not in policy:
        policy["ended_before"] = {event["event_id"]: (at - timedelta(days=3)).isoformat() for event in events}
    state = build_refresh_state(
        files,
        [unit(observed_at=(at - timedelta(days=1)).date().isoformat())] if units is None else units,
        published_at=at,
        **policy,
    )
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


def test_only_complete_finished_source_result_with_old_end_proof_freezes_without_role_invention():
    assert team_result_confirmed(game())
    assert not event_is_frozen(game(), NOW)
    assert event_is_frozen(game(), NOW, actual_end=lambda _: OLD_END)
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
        assert not event_is_frozen(event, NOW, actual_end=lambda _: OLD_END)
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


def test_stored_freeze_decision_survives_without_reinterpreting_parser_or_promoting_old_rows():
    files = publication([game("finished", status="scheduled")], frozen_ids={"finished"})
    assert baseline(files).frozen_ids == {"finished"}
    files = publication(frozen_ids=set())
    assert baseline(files).frozen_ids == set()
    loaded = load_published_baseline(files.__getitem__, now=NOW + timedelta(days=100), expected_years=[2026])
    assert loaded.frozen_ids == set() and not loaded.full_rebuild


@pytest.mark.parametrize("age", [0, 72, 7200, 87600])
def test_current_format_baseline_age_never_expires_frozen_facts_or_their_check_dates(age):
    files = publication(at=NOW - timedelta(hours=age))
    reads = []

    def read(name):
        reads.append(name)
        return files[name]

    loaded = load_published_baseline(read, now=NOW, expected_years=[2026])
    assert not loaded.full_rebuild and loaded.frozen_ids == {"finished"}
    assert loaded.events["finished"]["facts_checked_date"] == "2025-01-02"
    assert reads == ["refresh-state.json", "manifest.json", "2026-football-nfl.json"]


def test_future_publication_falls_back_before_reading_any_bound_files():
    files = publication(at=NOW + timedelta(minutes=1))
    reads = []

    def read(name):
        reads.append(name)
        return files[name]

    loaded = load_published_baseline(read, now=NOW, expected_years=[2026])
    assert loaded.reason == "publication_future" and reads == ["refresh-state.json"]


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
    assert not event_is_frozen(
        game(status="scheduled"), NOW, result_confirmed=lambda _: True, actual_end=lambda _: OLD_END
    )
    assert event_is_frozen(game(status="finished"), NOW, result_confirmed=lambda _: True, actual_end=lambda _: OLD_END)


def test_tba_opponent_is_not_a_named_final_score_result():
    event = game(
        participants=[
            {"name": "First", "entity_type": "team", "final_score": 2},
            {"name": " TBA ", "entity_type": "team", "final_score": 1},
        ]
    )
    assert not team_result_confirmed(event)
    assert not event_is_frozen(event, NOW)


@pytest.mark.parametrize("hours,expected", [(0, False), (47.999, False), (48, False), (48.0001, True), (72, True)])
def test_result_freeze_requires_strictly_more_than_two_days_after_end_upper_bound(hours, expected):
    ended = NOW - timedelta(hours=hours)
    assert event_is_frozen(game(), NOW, actual_end=lambda _: ended) is expected


@pytest.mark.parametrize("ended", [None, NOW + timedelta(seconds=1), NOW.replace(tzinfo=None)])
def test_confirmed_result_with_unknown_future_or_naive_end_is_not_eligible(ended):
    row = game(calendar_date="1990-01-01", start_time_utc="1990-01-01T00:00:00Z")
    assert not event_is_frozen(row, NOW, actual_end=lambda _: ended)


def test_explicit_source_end_callback_is_persisted_without_changing_public_fact_dates():
    files = publication(actual_end=lambda _: OLD_END)
    state = json.loads(files["refresh-state.json"])
    assert state["ended_before"] == {"finished": OLD_END.isoformat()}
    loaded = baseline(files)
    assert loaded.ended_before == state["ended_before"]
    assert loaded.events["finished"] == game()
    assert loaded.units["week"].observed_at == "2026-11-03"


def test_later_source_confirmations_keep_the_earliest_proven_bound():
    first = NOW - timedelta(days=5)
    files = publication(ended_before={"finished": first.isoformat()}, actual_end=lambda _: OLD_END)
    assert baseline(files).ended_before == {"finished": first.isoformat()}
    earlier = first - timedelta(days=1)
    files = publication(ended_before={"finished": first.isoformat()}, actual_end=lambda _: earlier)
    assert baseline(files).ended_before == {"finished": earlier.isoformat()}


def test_first_observed_finished_result_warms_up_then_requires_fresh_confirmation_to_freeze():
    observed = NOW.isoformat()
    first = publication(ended_before={"finished": observed})
    assert baseline(first).frozen_ids == set()
    aged = load_published_baseline(first.__getitem__, now=NOW + timedelta(days=100), expected_years=[2026])
    assert aged.frozen_ids == set() and aged.ended_before == {"finished": observed}
    second = publication(at=NOW + timedelta(days=1), ended_before=aged.ended_before)
    assert json.loads(second["refresh-state.json"])["frozen_event_ids"] == []
    exact = publication(at=NOW + timedelta(days=2), ended_before=aged.ended_before)
    assert json.loads(exact["refresh-state.json"])["frozen_event_ids"] == []
    confirmed = publication(at=NOW + timedelta(days=2, microseconds=1), ended_before=aged.ended_before)
    state = json.loads(confirmed["refresh-state.json"])
    assert state["frozen_event_ids"] == ["finished"] and state["ended_before"]["finished"] == observed
    assert json.loads(confirmed["2026-football-nfl.json"])["events"][0]["facts_checked_date"] == "2025-01-02"


def test_missing_required_end_map_is_an_old_format_full_rebuild_before_bundle_reads():
    files = publication()
    state = json.loads(files["refresh-state.json"])
    state.pop("ended_before")
    files["refresh-state.json"] = encode(state)
    reads = []

    def read(name):
        reads.append(name)
        return files[name]

    assert load_published_baseline(read, now=NOW, expected_years=[2026]).reason == "end_evidence_missing"
    assert reads == ["refresh-state.json"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"unknown": "2026-11-01T00:00:00Z"},
        {"finished": None},
        {"finished": True},
        {"finished": "2026-11-01"},
        {"finished": "invalid"},
        {"finished": "2027-01-01T00:00:00Z"},
    ],
)
def test_malformed_or_unknown_or_future_end_evidence_discards_entire_baseline(value):
    files = publication()
    change_state(files, ended_before=value)
    loaded = baseline(files)
    assert loaded.full_rebuild and loaded.frozen_ids == set() and loaded.ended_before == {}


@pytest.mark.parametrize("hours", [0, 47, 48])
def test_explicit_frozen_selection_without_an_old_enough_bound_is_rejected_by_builder_and_reader(hours):
    bound = (NOW - timedelta(hours=hours)).isoformat()
    with pytest.raises(ValueError, match="frozen_end_evidence"):
        publication(ended_before={"finished": bound}, frozen_ids={"finished"})
    files = publication()
    change_state(files, ended_before={"finished": bound})
    assert baseline(files).reason == "frozen_end_evidence"


def test_age_evidence_must_have_been_valid_when_frozen_not_only_when_baseline_is_read():
    files = publication()
    change_state(
        files,
        published_at=(NOW - timedelta(hours=1)).isoformat(),
        ended_before={"finished": (NOW - timedelta(hours=48, minutes=30)).isoformat()},
    )
    assert baseline(files).reason == "frozen_end_evidence"


def test_empty_end_evidence_is_valid_but_cannot_freeze_any_result():
    files = publication(ended_before={})
    loaded = baseline(files)
    assert not loaded.full_rebuild and loaded.ended_before == {} and loaded.frozen_ids == set()
    with pytest.raises(ValueError, match="frozen_end_evidence"):
        publication(ended_before={}, frozen_ids={"finished"})


def test_batch_baseline_reader_feature_is_preserved_without_extra_single_bundle_reads():
    files = publication()
    singles, batches = [], []

    def read(name):
        singles.append(name)
        return files[name]

    def read_many(names):
        batches.append(tuple(names))
        return {name: files[name] for name in names}

    loaded = load_published_baseline(read, now=NOW, expected_years=[2026], read_many=read_many)
    assert not loaded.full_rebuild and loaded.frozen_ids == {"finished"}
    assert singles == ["refresh-state.json"] and batches == [("manifest.json", "2026-football-nfl.json")]


def test_known_raw_members_can_keep_proven_end_bounds_and_freeze_without_public_event_fabrication():
    observed = unit(event_ids=("finished", "outside"))
    ends = {"finished": OLD_END.isoformat(), "outside": OLD_END.isoformat()}
    files = publication(units=[observed], ended_before=ends, frozen_ids={"finished", "outside"})
    loaded = baseline(files)
    assert not loaded.full_rebuild and loaded.frozen_ids == {"finished", "outside"}
    assert loaded.ended_before == ends and set(loaded.events) == {"finished"}
    assert len(json.loads(files["2026-football-nfl.json"])["events"]) == 1
    assert unit_is_frozen("week", loaded.frozen_ids, loaded.units)


def test_outside_bound_alone_does_not_freeze_or_resolve_an_unknown_result():
    observed = unit(event_ids=("finished", "outside"), unresolved={"outside": "result_unconfirmed"})
    ends = {"finished": OLD_END.isoformat(), "outside": OLD_END.isoformat()}
    loaded = baseline(publication(units=[observed], ended_before=ends))
    assert not loaded.full_rebuild and loaded.frozen_ids == {"finished"}
    assert loaded.ended_before["outside"] == OLD_END.isoformat()
    assert loaded.units["week"].unresolved == {"outside": "result_unconfirmed"}
    assert not unit_is_frozen("week", loaded.frozen_ids, loaded.units)


def test_nonpublic_member_requires_either_unresolved_provenance_or_explicit_eligible_freeze():
    observed = unit(event_ids=("finished", "outside"))
    with pytest.raises(ValueError, match="unit_missing_public_members"):
        publication(units=[observed], ended_before={"outside": OLD_END.isoformat()})
    files = publication(units=[unit(event_ids=("finished", "outside"), unresolved={"outside": "unconfirmed"})])
    state = json.loads(files["refresh-state.json"])
    state["units"][0]["unresolved"] = {}
    files["refresh-state.json"] = encode(state)
    assert baseline(files).full_rebuild


@pytest.mark.parametrize("bound", [NOW.isoformat(), (NOW - timedelta(days=2)).isoformat()])
def test_nonpublic_frozen_member_has_the_same_strict_end_age_requirement(bound):
    observed = unit(event_ids=("finished", "outside"))
    with pytest.raises(ValueError, match="frozen_end_evidence"):
        publication(
            units=[observed],
            ended_before={"finished": OLD_END.isoformat(), "outside": bound},
            frozen_ids={"finished", "outside"},
        )


@pytest.mark.parametrize(
    "start,stop,expected",
    [("2026-10-31T12:00:00", "2026-11-02T12:00:00", True), ("2026-03-07T12:00:00", "2026-03-09T12:30:00", False)],
)
def test_two_days_means_elapsed_48_hours_across_dst_not_two_local_calendar_days(start, stop, expected):
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    ended = datetime.fromisoformat(start).replace(tzinfo=zone)
    checked = datetime.fromisoformat(stop).replace(tzinfo=zone)
    assert event_is_frozen(game(), checked, actual_end=lambda _: ended) is expected


def test_observation_after_saved_publication_is_invalid_even_when_not_future_at_read_time():
    files = publication()
    state = json.loads(files["refresh-state.json"])
    state["units"][0]["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    files["refresh-state.json"] = encode(state)
    loaded = load_published_baseline(files.__getitem__, now=NOW + timedelta(days=1), expected_years=[2026])
    assert loaded.full_rebuild


@pytest.mark.parametrize("ended", [None, NOW.replace(tzinfo=None), NOW + timedelta(seconds=1)])
def test_unconfirmed_source_end_callback_cannot_fabricate_a_bound_or_freeze(ended):
    files = publication(actual_end=lambda _: ended)
    state = json.loads(files["refresh-state.json"])
    assert state["ended_before"] == {} and state["frozen_event_ids"] == []


def test_outside_freeze_without_a_bound_cannot_rely_on_membership_alone():
    observed = unit(event_ids=("finished", "outside"))
    with pytest.raises(ValueError, match="frozen_end_evidence"):
        publication(
            units=[observed], ended_before={"finished": OLD_END.isoformat()}, frozen_ids={"finished", "outside"}
        )


@pytest.mark.parametrize("bound", [None, "", "malformed", "2026-11-01", NOW.replace(tzinfo=None), 123])
def test_shared_raw_end_bound_helper_rejects_missing_or_unaware_proof(bound):
    assert not end_bound_aged(bound, NOW)


def test_shared_end_bound_helper_accepts_iso_or_datetime_and_is_strictly_elapsed():
    exact = NOW - timedelta(days=2)
    older = exact - timedelta(microseconds=1)
    assert not end_bound_aged(exact, NOW) and not end_bound_aged(exact.isoformat(), NOW)
    assert end_bound_aged(older, NOW) and end_bound_aged(older.isoformat(), NOW)
    assert not end_bound_aged(older, NOW.replace(tzinfo=None))
    assert not end_bound_aged(NOW - timedelta(days=14), NOW, days=14)
    assert end_bound_aged(NOW - timedelta(days=14, microseconds=1), NOW, days=14)


def test_never_result_policy_also_requires_an_aware_reference_clock():
    assert not event_is_frozen(
        game(status="scheduled"),
        NOW.replace(tzinfo=None),
        never_result=lambda _: True,
        actual_end=lambda _: NOW - timedelta(days=100),
    )
