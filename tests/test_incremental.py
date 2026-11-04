"""Authority, freeze preservation and public-model round trips without source I/O."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from kickoff.incremental import RefreshPlan, event_from_public
from kickoff.models import CalendarEvent, Participant
from kickoff.refresh_state import Baseline, SourceUnit
from kickoff.web import _event_payload
from tests.test_refresh_state import publication

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
OLD_DATE = "2026-11-03T10:00:00+00:00"
NEW_DATE = "2026-11-04T10:00:00+00:00"


def event(identity="game", **changes):
    row = CalendarEvent(
        event_id=identity,
        source="espn",
        sport="football",
        league="NFL",
        season="2026",
        event_type="game",
        title=f"First at Second {identity}",
        subtitle=None,
        start_time_utc="2026-11-01T17:00:00Z",
        start_time_local="2026-11-01T12:00:00",
        timezone="America/New_York",
        status="finished",
        venue=None,
        city=None,
        region=None,
        country=None,
        participants=[
            Participant("First", "1", role="away", final_score=10),
            Participant("Second", "2", role="home", final_score=20),
        ],
        calendar_date="2026-11-01",
        end_calendar_date="2026-11-01",
        facts_checked_date="2026-11-01",
        facts_source_url="https://example.org/facts",
        source_url="https://example.org/game",
    )
    for key, value in changes.items():
        setattr(row, key, value)
    row.home_participant = next((p for p in row.participants if p.role == "home"), None)
    row.away_participant = next((p for p in row.participants if p.role == "away"), None)
    return _event_payload(row)


def unit(key="unit", **changes):
    return SourceUnit(
        **{
            "key": key,
            "source_url": f"https://example.org/{key}",
            "observed_at": OLD_DATE,
            "event_ids": ("game",),
            "complete": True,
            "closed": True,
            **changes,
        }
    )


def baseline(events=None, units=None, frozen=("game",), year=2026):
    return Baseline(
        manifest={"available_seasons": [year]},
        bundles={f"{year}-football-nfl.json": {"season": year, "events": [event()] if events is None else events}},
        units={u.key: u for u in ([unit()] if units is None else units)},
        frozen_ids=frozenset(frozen),
    )


def variants():
    proof = {
        "logo_source_url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "logo_checked_date": "2026-11-01",
    }
    country = {
        "country_code": "US",
        "country_source_url": "https://example.org/identity",
        "country_checked_date": "2026-10-31",
        "country_source_kind": "reviewed",
    }
    roster = {
        "entry_total_kg": 180,
        "start_list_category": "Women's 48 kg, Group A",
        "start_list_nation": "WRT",
        "start_list_guest": False,
        "start_list_source_url": "https://example.org/book.pdf",
        "start_list_checked_date": "2026-11-04",
    }
    return [
        event(),
        event(sport="cricket", league="IPL", participants=[Participant("First", "1"), Participant("Second", "2")]),
        event(sport="cricket", league="IPL", participants=[Participant("Known side", "1", role="home")]),
        event(
            participants=[
                Participant(
                    "Club",
                    "1",
                    entity_type="club",
                    metadata={**proof, "logo_url": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png"},
                )
            ]
        ),
        event(
            participants=[
                Participant(
                    "National side",
                    "1",
                    entity_type="national_team",
                    metadata={
                        **proof,
                        **country,
                        "logo_url": "https://a.espncdn.com/i/teamlogos/countries/500/usa.png",
                    },
                )
            ]
        ),
        event(
            sport="weightlifting",
            league="IWF_WORLDS",
            event_type="session",
            participants=[Participant("Athlete", "lot1", entity_type="athlete", metadata=roster)],
        ),
        event(
            sport="weightlifting",
            league="IWF_JUNIOR_WORLDS",
            event_type="session",
            participants=[Participant("Athlete", "lot1", entity_type="athlete", metadata={**roster, **country})],
        ),
        event(
            result={
                "kind": "podium",
                "rows": [{"rank": 1, "name": "Driver", "participant_id": "driver"}],
                "checked_date": "2026-11-02",
                "source_url": "https://example.org/result",
            }
        ),
        event(
            start_time_utc=None,
            start_time_local=None,
            timezone=None,
            start_time_scope="session",
            end_calendar_date="2026-11-03",
            country="US",
            country_source_url="https://example.org/host",
            country_checked_date="2026-10-31",
        ),
    ]


@pytest.mark.parametrize("row", variants())
def test_exact_public_roundtrip_retains_role_exceptions_images_countries_rosters_and_results(row):
    original = deepcopy(row)
    restored = event_from_public(row)
    assert _event_payload(restored) == original
    assert row == original
    assert restored.raw_source_payload == {} and restored.result_complete is False
    for role in ("home", "away"):
        participant = next((p for p in restored.participants if p.role == role), None)
        assert getattr(restored, role + "_participant") is participant


def test_restoration_whitelists_public_fields_and_does_not_trust_private_flags_or_fake_raw_data():
    row = event(raw_source_payload={"secret": "not exported"})
    row.update(raw_source_payload={"private": True}, result_complete=True)
    row["participants"][0].update(metadata={"private": True}, dateOfBirth="private")
    restored = event_from_public(row)
    assert restored.raw_source_payload == {} and restored.result_complete is False
    assert restored.participants[0].metadata == {}


def test_reuse_preserves_actual_observation_and_fact_dates_and_detaches_mutable_models():
    source = baseline()
    plan = RefreshPlan(source, NOW)
    restored = plan.try_reuse("unit")
    assert [_event_payload(e) for e in restored] == [event()]
    assert plan.units["unit"].observed_at == OLD_DATE
    assert restored[0].facts_checked_date == "2026-11-01"
    restored[0].participants[0].name = "Mutation"
    assert source.events["game"] == event()
    assert plan.try_reuse("unit")[0].participants[0].name == "First"
    assert plan.counters == {"current": 0, "refreshed": 0, "skipped": 1, "pending": 0}


def test_nested_discovery_reuse_deduplicates_ids_and_marks_all_proven_requests_skipped():
    child = unit("child")
    parent = unit("parent", event_ids=("game",), children=("child",))
    plan = RefreshPlan(baseline(units=[parent, child]), NOW)
    assert len(plan.try_reuse("parent")) == 1
    assert plan.skipped == 2 and plan.pending_unit_keys == set()
    assert plan.units["child"] == child


@pytest.mark.parametrize("change", [{"closed": False}, {"complete": False}, {"unresolved": {"game": "missing_result"}}])
def test_visibility_or_a_finished_date_cannot_make_an_unproven_unit_reusable(change):
    plan = RefreshPlan(baseline(units=[replace(unit(), **change)]), NOW)
    assert plan.try_reuse("unit") is None
    assert plan.pending_unit_keys == {"unit"} and plan.skipped == 0


def test_unknown_old_finished_rows_are_not_retroactively_frozen():
    plan = RefreshPlan(baseline(frozen=()), NOW)
    assert plan.try_reuse("unit") is None
    assert plan.baseline.frozen_ids == frozenset()


def test_reuse_restores_result_completeness_only_for_trusted_frozen_results():
    row = event(result={"kind": "podium", "rows": []})
    plan = RefreshPlan(baseline(events=[row]), NOW)
    assert plan.try_reuse("unit")[0].result_complete is True
    assert event_from_public(row).result_complete is False


def test_frozen_public_bytes_win_over_incidental_fresh_mutations_in_a_mixed_batch():
    row = event()
    plan = RefreshPlan(baseline(events=[row, event("pending", status="scheduled")]), NOW)
    changed = deepcopy(row)
    changed["title"] = "Unwanted fresh rewrite"
    changed["facts_checked_date"] = "2026-11-04"
    output = plan.public_events([changed, event("pending", status="finished")], 2026)
    actual = next(e for e in output if e["event_id"] == "game")
    assert json.dumps(actual) == json.dumps(row)
    actual["participants"][0]["name"] = "Mutation"
    assert plan.public_events([], 2026)[0] == row


def test_only_complete_actual_observation_can_remove_old_unfrozen_visible_rows():
    plan = RefreshPlan(
        baseline(events=[event(), event("pending", status="scheduled")], units=[unit(event_ids=("game", "pending"))]),
        NOW,
    )
    assert len(plan.public_events([], 2026)) == 2
    plan.observe(unit(event_ids=(), complete=False, observed_at=NEW_DATE))
    assert len(plan.public_events([], 2026)) == 2
    plan.observe(unit(event_ids=(), complete=True, closed=False, observed_at=NEW_DATE))
    assert plan.public_events([], 2026) == [event()]
    assert plan.units["unit"].closed is False


def test_cancelled_withheld_public_row_is_removed_but_source_locator_remains():
    plan = RefreshPlan(
        baseline(events=[event("cancelled", status="scheduled")], units=[unit(event_ids=("cancelled",))], frozen=()),
        NOW,
    )
    observed = unit(event_ids=("cancelled",), unresolved={"cancelled": "canceled"}, closed=False, observed_at=NEW_DATE)
    plan.observe(observed)
    assert plan.public_events([], 2026) == []
    assert plan.units["unit"] == observed
    files = publication(events=[], units=list(plan.units.values()))
    assert "cancelled" in json.loads(files["refresh-state.json"])["units"][0]["unresolved"]


def test_missing_unpublished_unresolved_id_survives_even_when_new_response_is_empty():
    previous = unit(event_ids=("hidden",), unresolved={"hidden": "postponed"}, closed=False)
    plan = RefreshPlan(baseline(events=[], units=[previous], frozen=()), NOW)
    fresh = unit(event_ids=(), closed=False, observed_at=NEW_DATE)
    plan.observe(fresh)
    assert plan.current["unit"] == fresh
    assert plan.units["unit"].event_ids == ("hidden",)
    assert plan.units["unit"].unresolved == {"hidden": "postponed"}
    assert plan.units["unit"].observed_at == NEW_DATE
    assert plan.public_events([], 2026) == []
    assert plan.pending_unit_keys == set()
    publication(events=[], units=list(plan.units.values()))


@pytest.mark.parametrize("new_first", [True, False])
def test_moved_unresolved_id_reconciles_from_actual_source_observations_not_public_visibility(new_first):
    old = unit("old", event_ids=("hidden",), unresolved={"hidden": "postponed"}, closed=False)
    plan = RefreshPlan(baseline(events=[], units=[old], frozen=()), NOW)
    plan.public_events([event("hidden")], 2026)
    assert plan.units["old"].unresolved == {"hidden": "postponed"}
    observations = [
        unit("new", event_ids=("hidden",), observed_at=NEW_DATE),
        replace(old, event_ids=(), unresolved={}, observed_at=NEW_DATE),
    ]
    for observation in observations if new_first else reversed(observations):
        plan.observe(observation)
    assert plan.units["old"].unresolved == {} and plan.units["old"].event_ids == ()
    assert plan.units["new"].event_ids == ("hidden",)
    assert plan.pending_unit_keys == set()


def test_unrefreshed_old_locator_stays_pending_after_id_is_seen_elsewhere():
    old = unit("old", event_ids=("hidden",), unresolved={"hidden": "postponed"}, closed=False)
    plan = RefreshPlan(baseline(events=[], units=[old], frozen=()), NOW)
    plan.observe(unit("new", event_ids=("hidden",), observed_at=NEW_DATE))
    assert plan.pending_unit_keys == {"old"}
    assert plan.units["old"].unresolved == {}
    assert plan.units["old"].observed_at == old.observed_at


def test_rescheduled_id_moves_year_without_duplicate_or_stale_old_appointment():
    plan = RefreshPlan(
        baseline(events=[event("moving", status="scheduled")], units=[unit(event_ids=("moving",))], frozen=()), NOW
    )
    plan.observe(unit(event_ids=("moving",), closed=False, observed_at=NEW_DATE))
    assert plan.public_events([], 2026) == []
    moved = event("moving", status="scheduled", calendar_date="2027-01-02", end_calendar_date="2027-01-02")
    assert plan.public_events([moved, moved], 2027) == [moved]


def test_frozen_id_cannot_be_copied_into_a_new_publication_year_from_mixed_source_batch():
    plan = RefreshPlan(baseline(), NOW)
    assert plan.public_events([event(calendar_date="2027-01-02")], 2027) == []
    assert plan.public_events([], 2026) == [event()]


def test_fresh_duplicate_ids_use_last_fact_and_do_not_share_mutable_input_objects():
    plan = RefreshPlan(Baseline(reason="missing_baseline"), NOW)
    first, last = event("new", title="Before"), event("new", title="After")
    result = plan.public_events([first, last], 2026)
    assert result == [last]
    result[0]["participants"][0]["name"] = "Mutation"
    assert last["participants"][0]["name"] == "First"


def test_invalid_or_forced_full_baseline_cannot_supply_old_units_rows_or_freeze_ids():
    previous = baseline()
    previous.reason = "force_full"
    plan = RefreshPlan(previous, NOW)
    assert plan.try_reuse("unit") is None and plan.units == {} and plan.pending_unit_keys == set()
    assert plan.public_events([], 2026) == []
    observed = unit("fresh", event_ids=("new",), closed=False, observed_at=NEW_DATE)
    plan.observe(observed)
    assert plan.public_events([event("new")], 2026) == [event("new")]
    assert plan.units == {"fresh": observed} and plan.refreshed == 1


def test_complete_bounded_empty_historical_unit_can_skip_without_a_synthetic_event():
    empty = unit(event_ids=(), start="2026-01-01", end="2026-01-02")
    plan = RefreshPlan(baseline(events=[], units=[empty], frozen=()), NOW)
    assert plan.try_reuse("unit") == []
    assert plan.units["unit"] == empty and plan.skipped == 1


def test_partial_observation_cannot_reconcile_a_missing_historical_unresolved_id():
    old = unit("old", event_ids=("hidden",), unresolved={"hidden": "postponed"}, closed=False)
    plan = RefreshPlan(baseline(events=[], units=[old], frozen=()), NOW)
    plan.observe(replace(old, event_ids=(), unresolved={}, observed_at=NEW_DATE))
    plan.observe(unit("new", event_ids=("hidden",), complete=False, closed=False, observed_at=NEW_DATE))
    assert plan.units["old"].unresolved == {"hidden": "postponed"}
    assert old.unresolved == {"hidden": "postponed"}
    plan.observe(unit("new", event_ids=("hidden",), complete=True, closed=False, observed_at=NEW_DATE))
    assert plan.units["old"].unresolved == {} and plan.units["old"].event_ids == ()


def test_omitted_frozen_member_keeps_public_bytes_and_effective_state_coverage():
    previous = unit(event_ids=("game", "pending"))
    plan = RefreshPlan(baseline(events=[event(), event("pending", status="scheduled")], units=[previous]), NOW)
    observed = unit(event_ids=("new",), complete=True, closed=False, observed_at=NEW_DATE)
    plan.observe(observed)
    merged = plan.public_events([event("new", status="scheduled")], 2026)
    assert {row["event_id"] for row in merged} == {"game", "new"}
    assert json.dumps(next(row for row in merged if row["event_id"] == "game")) == json.dumps(event())
    assert plan.current["unit"] == observed
    assert plan.units["unit"].event_ids == ("new", "game")
    assert plan.units["unit"].observed_at == NEW_DATE
    assert plan.units["unit"].closed is False
    files = publication(events=merged, units=list(plan.units.values()), frozen_ids=plan.baseline.frozen_ids)
    state = json.loads(files["refresh-state.json"])
    assert state["frozen_event_ids"] == ["game"]
    assert state["units"][0]["event_ids"] == ["new", "game"]
    assert "pending" not in state["units"][0]["event_ids"]


def test_frozen_raw_outside_public_members_are_not_fabricated_on_reuse():
    old = baseline(units=[unit(event_ids=("game", "outside"))], frozen=("game", "outside"))
    old.ended_before = {"game": "2026-10-01T00:00:00+00:00", "outside": "2026-10-01T00:00:00+00:00"}
    plan = RefreshPlan(old, NOW)
    restored = plan.try_reuse("unit")
    assert [e.event_id for e in restored] == ["game"]
    assert plan.skipped == 1


def test_omitted_end_bound_member_stays_known_without_inventing_public_row():
    old = baseline(units=[unit(event_ids=("game", "outside"))], frozen=("game",))
    old.ended_before = {"outside": "2026-11-03T00:00:00+00:00"}
    plan = RefreshPlan(old, NOW)
    plan.observe(unit(event_ids=("game",), observed_at=NEW_DATE))
    assert plan.units["unit"].event_ids == ("game", "outside")
    assert plan.units["unit"].unresolved == {"outside": "missing_confirmed_result"}
    assert [e["event_id"] for e in plan.public_events([], 2026)] == ["game"]


def test_optional_result_failure_preserves_previous_facts_and_complete_proof():
    old = event(result={"kind": "podium", "complete": True, "rows": [{"rank": 1, "name": "Actual winner"}]})
    previous = baseline(events=[old], frozen=())
    previous.ended_before = {"game": "2026-11-03T00:00:00Z"}
    plan = RefreshPlan(previous, NOW)
    plan.observe(unit(observed_at=NEW_DATE))
    fresh = event()
    assert plan.public_events([fresh], 2026)[0]["result"] == old["result"]
    assert "result" not in fresh
    assert plan.confirmed_results == {"game"}
    reopened = event(status="scheduled")
    assert "result" not in plan.public_events([reopened], 2026)[0]
    moved = event(calendar_date="2026-12-01")
    assert "result" not in plan.public_events([moved], 2026)[0]


def test_effective_units_uses_one_snapshot_during_concurrent_observations():
    plan = RefreshPlan(baseline(frozen=()), NOW)

    class Arriving(dict):
        def copy(self):
            snapshot = super().copy()
            self["later"] = unit("later", event_ids=("outside",))
            return snapshot

    plan.current = Arriving({"first": unit("first")})
    observed = plan.units
    assert "first" in observed and "later" not in observed
    assert "later" in plan.current


def test_actual_complete_other_locator_reconciles_old_unresolved_without_new_date():
    old_unit = unit("old", unresolved={"game": "postponed"})
    plan = RefreshPlan(baseline(units=[old_unit], frozen=()), NOW)
    plan.observe(unit("new", observed_at=NEW_DATE))
    assert plan.units["old"].unresolved == {}
    assert plan.units["old"].observed_at == OLD_DATE
    plan.observe(unit("new", observed_at=NEW_DATE, unresolved={"game": "scheduled"}))
    assert plan.units["old"].unresolved == {"game": "scheduled"}


def test_parent_omission_or_incomplete_observation_never_reconciles_old_locator():
    plan = RefreshPlan(baseline(units=[unit("old", unresolved={"game": "postponed"})], frozen=()), NOW)
    plan.observe(unit("parent", event_ids=(), observed_at=NEW_DATE))
    plan.observe(unit("partial", complete=False, observed_at=NEW_DATE))
    assert plan.units["old"].unresolved == {"game": "postponed"}


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize("default_status", ["scheduled", "past schedule"])
def test_default_timetable_status_never_erases_actual_previous_results(complete, default_status):
    old = event(
        result={
            "kind": "podium",
            "complete": complete,
            "checked_date": "2026-10-30",
            "rows": [{"name": "Winner", "rank": 1}],
        }
    )
    plan = RefreshPlan(baseline(events=[old], frozen=()), NOW)
    plan.observe(unit("reviewed:2026:source", unresolved={"game": "missing_confirmed_result"}, observed_at=OLD_DATE))
    fresh = event(status=default_status)
    (merged,) = plan.public_events([fresh], 2026)
    assert merged["status"] == "finished" and merged["result"] == old["result"]
    assert merged["result"]["checked_date"] == "2026-10-30"
    assert plan.confirmed_results == ({"game"} if complete else set())
    plan.observe(unit("api-reopened", unresolved={"game": "STATUS_SCHEDULED"}, observed_at=NEW_DATE))
    (reopened,) = plan.public_events([fresh], 2026)
    assert reopened["status"] == default_status and "result" not in reopened
