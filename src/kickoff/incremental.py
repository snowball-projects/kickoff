"""Source-observation bookkeeping and restoration of our published event facts."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import fields, replace
from datetime import datetime, timezone

from kickoff.models import CalendarEvent, Participant
from kickoff.refresh_state import Baseline, SourceUnit, unit_is_frozen
from kickoff.results import same_result_scope
from kickoff.weightlifting_startlists import ENTRY_FIELDS

EVENT_FIELDS = {f.name for f in fields(CalendarEvent)} - {
    "participants",
    "home_participant",
    "away_participant",
    "raw_source_payload",
    "result_complete",
}
PARTICIPANT_FIELDS = {f.name for f in fields(Participant)} - {"metadata"}
PARTICIPANT_METADATA = set(ENTRY_FIELDS) | {
    "result_winner",
    "result_advance",
    "aggregate_score",
    "shootout_score",
    "logo_url",
    "logo_source_url",
    "logo_checked_date",
    "country_code",
    "country_source_url",
    "country_checked_date",
    "country_source_kind",
}


def event_from_public(row: dict, *, result_complete: bool = False) -> CalendarEvent:
    """Restore only exported fields; roles restore aliases without inventing sides.

    Completeness is private policy state, never inferred from a nonempty public
    result. No source payload is reconstructed from public facts.
    """
    participants = [
        Participant(
            **{key: deepcopy(value) for key, value in p.items() if key in PARTICIPANT_FIELDS},
            metadata={key: deepcopy(value) for key, value in p.items() if key in PARTICIPANT_METADATA},
        )
        for p in row["participants"]
    ]
    return CalendarEvent(
        **{key: deepcopy(value) for key, value in row.items() if key in EVENT_FIELDS},
        participants=participants,
        home_participant=next((p for p in participants if p.role == "home"), None),
        away_participant=next((p for p in participants if p.role == "away"), None),
        result_complete=result_complete,
    )


def _order(row: dict) -> tuple:
    # Same public facts and order as normalize.sort_events; no date conversion.
    return (
        row.get("calendar_date") or "9999-12-31",
        row.get("start_time_utc") is None,
        row.get("start_time_utc") or row.get("start_time_local") or "",
        row["league"],
        row["title"],
        row["event_id"],
    )


class RefreshPlan:
    """Keep source authority separate from public visibility and freeze decisions.

    `current` contains exactly the caller's observations from this run. `units`
    also retains unvisited historical observations, frozen published membership
    and unresolved IDs omitted by a new response. Its observed_at is the real request date, not an athlete or
    game fact date. An omitted unresolved ID stays pending until another actual
    source observation reconciles it; public visibility cannot do that.
    """

    def __init__(self, baseline: Baseline, now: datetime):
        self.now = now
        self.baseline = Baseline(reason=baseline.reason) if baseline.full_rebuild else baseline
        self.current: dict[str, SourceUnit] = {}
        self.receipts: dict[str, dict] = {}
        self.confirmed_results: set[str] = set()
        self.f1_contexts: dict[str, dict] = {}
        self.result_end_bounds: dict[str, str] = {}
        self._skipped: set[str] = set()
        self._events = self.baseline.events
        self._years = {
            event["event_id"]: bundle["season"]
            for bundle in self.baseline.bundles.values()
            for event in bundle["events"]
        }

    @property
    def refreshed(self) -> int:
        return len(self.current)

    @property
    def skipped(self) -> int:
        return len(self._skipped - self.current.keys())

    @property
    def pending_unit_keys(self) -> set[str]:
        """Baseline requests not yet actually observed or proved reusable this run."""
        return set(self.baseline.units) - self.current.keys() - self._skipped

    @property
    def counters(self) -> dict[str, int]:
        return {
            "current": len(self.current),
            "refreshed": self.refreshed,
            "skipped": self.skipped,
            "pending": len(self.pending_unit_keys),
        }

    @property
    def units(self) -> dict[str, SourceUnit]:
        units = deepcopy(self.baseline.units)
        current = self.current.copy()
        latest = {}
        for observation in current.values():
            if not observation.complete:
                continue
            instant = datetime.fromisoformat(observation.observed_at.replace("Z", "+00:00"))
            instant = instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant
            for identity in observation.event_ids:
                if identity not in latest or instant >= latest[identity][0]:
                    latest[identity] = (instant, observation.unresolved.get(identity))
        seen = set(latest)
        for key, previous in list(units.items()):
            if key in current:
                continue
            # Another complete response may actually recheck a moved game.
            # Keep this locator's true request date; only reconcile its IDs.
            units[key] = replace(
                previous,
                unresolved={
                    identity: latest[identity][1] if identity in latest else reason
                    for identity, reason in previous.unresolved.items()
                    if identity not in latest or latest[identity][1] is not None
                },
            )
        for key, unit in current.items():
            previous = self.baseline.units.get(key)
            carried = (
                {identity: state for identity, state in previous.unresolved.items() if identity not in seen}
                if previous
                else {}
            )
            if previous:
                carried.update(
                    {
                        identity: previous.unresolved.get(identity, "missing_confirmed_result")
                        for identity in previous.event_ids
                        if identity in self.baseline.ended_before
                        and identity not in self.baseline.frozen_ids
                        and identity not in seen
                    }
                )
            frozen = (
                [identity for identity in previous.event_ids if identity in self.baseline.frozen_ids]
                if previous
                else []
            )
            units[key] = replace(
                deepcopy(unit),
                event_ids=tuple(dict.fromkeys([*unit.event_ids, *frozen, *carried])),
                unresolved={**carried, **unit.unresolved},
            )
        return units

    def try_reuse(self, unit_key: str) -> list[CalendarEvent] | None:
        """Skip only a baseline unit whose complete graph is already frozen."""
        if unit_key in self.current or not unit_is_frozen(unit_key, self.baseline.frozen_ids, self.baseline.units):
            return None
        identities = {}

        def visit(key: str) -> None:
            unit = self.baseline.units[key]
            self._skipped.add(key)
            identities.update(dict.fromkeys(unit.event_ids))
            for child in unit.children:
                visit(child)

        visit(unit_key)
        return [
            event_from_public(self._events[identity], result_complete=self._events[identity].get("result") is not None)
            for identity in identities
            if identity in self._events
        ]

    def observe(self, unit: SourceUnit) -> None:
        """Record actual pre-filter observations; never infer completion or closure."""
        self.current[unit.key] = deepcopy(unit)

    def public_events(self, fresh: Iterable[dict], year: int) -> list[dict]:
        """Merge exact IDs; only complete observations can remove stale visible rows.

        Frozen records win globally, even when incidentally present in a freshly
        fetched mixed batch, and retain their original publication year. A source
        row can disappear from public output while remaining unresolved metadata.
        Fresh duplicate IDs follow the existing adapter convention: last wins.
        """
        incoming = {row["event_id"]: row for row in fresh if row["event_id"] not in self.baseline.frozen_ids}
        previous_results = {
            identity for identity in incoming if (self._events.get(identity) or {}).get("result") is not None
        }
        reasons_by_id = {identity: [] for identity in previous_results}
        if previous_results:
            for observation in self.current.values():
                if observation.complete:
                    for identity in previous_results.intersection(observation.event_ids):
                        reasons_by_id[identity].append(observation.unresolved.get(identity))
        for identity in previous_results:
            row = incoming[identity]
            previous = self._events[identity]
            observed_reasons = reasons_by_id[identity]
            # Reviewed timetables and F1 schedule adapters have no completion
            # status. Their default appointment is not an actual source reopen.
            appointment_default = (
                row.get("status") in {"scheduled", "past schedule"}
                and bool(observed_reasons)
                and all(reason == "missing_confirmed_result" for reason in observed_reasons)
            )
            if (
                previous
                and previous.get("result") is not None
                and row.get("result") is None
                and previous.get("status") == "finished"
                and (row.get("status") == "finished" or appointment_default)
                and same_result_scope(row, previous)
            ):
                row = deepcopy(row)
                row["result"] = deepcopy(previous["result"])
                row["status"] = "finished"
                incoming[identity] = row
                if previous["result"].get("complete") is True:
                    self.confirmed_results.add(identity)
        authoritative = set()
        for key, unit in self.current.items():
            if not unit.complete:
                continue
            authoritative.update(unit.event_ids)
            previous = self.baseline.units.get(key)
            if previous:
                authoritative.update(previous.event_ids)
        merged = {}
        for identity, row in self._events.items():
            if self._years[identity] != year:
                continue
            if identity in self.baseline.frozen_ids or (identity not in incoming and identity not in authoritative):
                merged[identity] = row
        merged.update(incoming)
        return deepcopy(sorted(merged.values(), key=_order))
