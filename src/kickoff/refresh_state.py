"""Pure freeze policy and a hash-bound baseline of our published public files."""

from __future__ import annotations

import hashlib
import json
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

Event = dict
Predicate = Callable[[Event], bool]


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _boundary(value: str) -> datetime:
    if "T" in value:
        return _instant(value)
    return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=timezone.utc)


def team_result_confirmed(event: Event) -> bool:
    """Only source-finished team games with scores for both named participants."""
    participants = event.get("participants", [])
    return (
        event.get("status") == "finished"
        and event.get("event_type") == "game"
        and len(participants) == 2
        and all(
            p.get("entity_type") in {"team", "national_team"}
            and isinstance(p.get("name"), str)
            and p["name"].strip()
            and p["name"].strip().casefold() not in {"tba", "tbd", "tbc", "unknown", "undecided"}
            and type(p.get("final_score")) is int
            for p in participants
        )
        and participants[0]["name"] != participants[1]["name"]
    )


def end_bound_aged(bound: str | datetime | None, now: datetime, days: int = 2) -> bool:
    """True only beyond the elapsed-day limit with an aware source end proof."""
    try:
        ended = _instant(bound) if isinstance(bound, str) else bound
        if not isinstance(ended, datetime) or ended.tzinfo is None or now.tzinfo is None:
            return False
        return now.astimezone(timezone.utc) - ended.astimezone(timezone.utc) > timedelta(days=days)
    except (ValueError, TypeError):
        return False


def event_is_frozen(
    event: Event,
    now: datetime,
    *,
    result_confirmed: Predicate = team_result_confirmed,
    never_result: Predicate | None = None,
    actual_end: Callable[[Event], datetime | None] | None = None,
) -> bool:
    if event.get("status") in {"canceled", "cancelled", "postponed", "undecided"}:
        return False
    ended = actual_end(event) if actual_end is not None else None
    if ended is None or ended.tzinfo is None or now.tzinfo is None:
        return False
    if event.get("status") == "finished" and result_confirmed(event):
        return end_bound_aged(ended, now)
    elapsed = now.astimezone(timezone.utc) - ended.astimezone(timezone.utc)
    return never_result is not None and never_result(event) and elapsed >= timedelta(days=14)


@dataclass(frozen=True)
class SourceUnit:
    """A real observed source request, including rows omitted from public output.

    Complete means all pages/children were observed successfully. Closed is an
    explicit source-boundary decision, never an inference from a past date.
    Discovery requests list every child key before they can be skipped.
    """

    key: str
    source_url: str
    observed_at: str
    event_ids: tuple[str, ...] = ()
    unresolved: dict[str, str] = field(default_factory=dict)
    complete: bool = False
    closed: bool = False
    children: tuple[str, ...] = ()
    start: str | None = None
    end: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def unit_is_frozen(key: str, frozen_ids: Iterable[str], units: Mapping[str, SourceUnit]) -> bool:
    """Skip only proven closed units; past dates alone cannot establish closure."""
    frozen = set(frozen_ids)

    def visit(name: str, visiting: set[str]) -> bool:
        if name in visiting or name not in units:
            return False
        unit = units[name]
        if not unit.complete or not unit.closed or unit.unresolved:
            return False
        if not unit.event_ids and not unit.children:
            # The producer owns the lookback/closure decision. Require a real
            # bounded historical observation, not vacuous membership truth.
            if unit.start is None or unit.end is None:
                return False
            try:
                return _boundary(unit.start) <= _boundary(unit.end) < _boundary(unit.observed_at)
            except (ValueError, TypeError):
                return False
        return set(unit.event_ids) <= frozen and all(visit(child, visiting | {name}) for child in unit.children)

    return visit(key, set())


@dataclass
class Baseline:
    reason: str | None = None
    manifest: dict = field(default_factory=dict)
    bundles: dict[str, dict] = field(default_factory=dict)
    units: dict[str, SourceUnit] = field(default_factory=dict)
    frozen_ids: frozenset[str] = frozenset()
    ended_before: dict[str, str] = field(default_factory=dict)

    @property
    def full_rebuild(self) -> bool:
        return self.reason is not None

    @property
    def events(self) -> dict[str, Event]:
        return {event["event_id"]: event for bundle in self.bundles.values() for event in bundle["events"]}

    @property
    def year_bundles(self) -> dict[int, list[dict]]:
        """Original public league envelopes grouped by publication year."""
        return {
            year: [bundle for bundle in self.bundles.values() if bundle["season"] == year]
            for year in self.manifest.get("available_seasons", [])
        }


def _catalog(manifest: dict) -> dict[str, tuple[int, dict]]:
    if manifest["schema_version"] != "1":
        raise ValueError("manifest_schema")
    years = manifest["available_seasons"]
    if not years or len(set(years)) != len(years) or set(map(str, years)) != set(manifest["seasons"]):
        raise ValueError("manifest_years")
    catalog = {}
    for year in years:
        season = manifest["seasons"][str(year)]
        if type(year) is not int or season["season"] != year:
            raise ValueError("manifest_year")
        for item in season["sports"]:
            name = item["file"]
            if not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".json"):
                raise ValueError("bundle_name")
            if name in {"manifest.json", "refresh-state.json"} or name in catalog:
                raise ValueError("duplicate_bundle")
            catalog[name] = (year, item)
    return catalog


def _read_units(
    rows: list[dict], public_ids: set[str], now: datetime, frozen_ids: Iterable[str] = ()
) -> dict[str, SourceUnit]:
    units = {}
    frozen = set(frozen_ids)
    for row in rows:
        unit = SourceUnit(**row)
        if not isinstance(unit.key, str) or not unit.key or unit.key in units:
            raise ValueError("duplicate_or_empty_unit")
        url = urlsplit(unit.source_url)
        if url.scheme not in {"https", "http"} or not url.netloc or url.username or url.password:
            raise ValueError("unit_source_url")
        observed = _instant(unit.observed_at) if "T" in unit.observed_at else date.fromisoformat(unit.observed_at)
        if observed > now if isinstance(observed, datetime) else observed > now.date():
            raise ValueError("unit_future_observation")
        if unit.start is not None:
            _boundary(unit.start)
        if unit.end is not None:
            _boundary(unit.end)
        if unit.start is not None and unit.end is not None and _boundary(unit.start) > _boundary(unit.end):
            raise ValueError("unit_bounds")
        if type(unit.complete) is not bool or type(unit.closed) is not bool:
            raise ValueError("unit_flags")
        if not isinstance(unit.event_ids, (list, tuple)) or not isinstance(unit.children, (list, tuple)):
            raise ValueError("unit_membership_type")
        if len(set(unit.event_ids)) != len(unit.event_ids) or len(set(unit.children)) != len(unit.children):
            raise ValueError("unit_duplicates")
        if not all(isinstance(value, str) and value for value in [*unit.event_ids, *unit.children]):
            raise ValueError("unit_identity")
        if not isinstance(unit.unresolved, dict) or not all(
            key in unit.event_ids and isinstance(status, str) and status for key, status in unit.unresolved.items()
        ):
            raise ValueError("unit_unresolved")
        if set(unit.event_ids) - public_ids - unit.unresolved.keys() - frozen:
            raise ValueError("unit_missing_public_members")
        units[unit.key] = unit
    members = {identity for unit in units.values() for identity in unit.event_ids}
    if public_ids - members:
        raise ValueError("unit_coverage")
    if frozen - members:
        raise ValueError("unknown_frozen_event")

    def visit(key: str, stack: set[str]) -> None:
        if key in stack or key not in units:
            raise ValueError("unit_graph")
        for child in units[key].children:
            visit(child, stack | {key})

    for key in units:
        visit(key, set())
    return units


def _read_files(manifest: dict, read_bytes: Callable[[str], bytes]) -> dict[str, dict]:
    bundles = {}
    ids = set()
    for name, (year, item) in _catalog(manifest).items():
        bundle = json.loads(read_bytes(name))
        events = bundle["events"]
        if bundle["schema_version"] != "1" or bundle["season"] != year or len(events) != item["count"]:
            raise ValueError("bundle_count_or_year")
        if bundle["updated_at"] != manifest["seasons"][str(year)]["updated_at"]:
            raise ValueError("bundle_generation")
        for event in events:
            identity = event["event_id"]
            if not isinstance(identity, str) or not identity or identity in ids:
                raise ValueError("duplicate_or_empty_event")
            if event["sport"] != item["value"] or event["league"] not in item["leagues"]:
                raise ValueError("bundle_membership")
            ids.add(identity)
        bundles[name] = bundle
    for year in manifest["available_seasons"]:
        if (
            sum(len(b["events"]) for b in bundles.values() if b["season"] == year)
            != manifest["seasons"][str(year)]["all_events"]
        ):
            raise ValueError("season_count")
    return bundles


def _read_ended_before(values: dict, known_ids: set[str], observed: datetime) -> dict[str, str]:
    """Source end upper bounds, never inferred from a scheduled date or start."""
    if not isinstance(values, dict) or any(not isinstance(key, str) or key not in known_ids for key in values):
        raise ValueError("end_evidence_identity")
    for value in values.values():
        if not isinstance(value, str) or _instant(value) > observed:
            raise ValueError("end_evidence_timestamp")
    return dict(values)


def _frozen_bounds_valid(frozen: Iterable[str], ended_before: Mapping[str, str], observed: datetime) -> bool:
    return all(end_bound_aged(ended_before.get(key), observed) for key in frozen)


def build_refresh_state(
    files: Mapping[str, bytes],
    units: Iterable[SourceUnit],
    *,
    published_at: datetime,
    frozen_ids: Iterable[str] | None = None,
    ended_before: Mapping[str, str] | None = None,
    result_confirmed: Predicate = team_result_confirmed,
    never_result: Predicate | None = None,
    actual_end: Callable[[Event], datetime | None] | None = None,
) -> dict:
    """Bind a successful publication to exact output bytes, without refreshing fact dates."""
    _instant(published_at.isoformat())
    manifest = json.loads(files["manifest.json"])
    bundles = _read_files(manifest, files.__getitem__)
    events = {event["event_id"]: event for bundle in bundles.values() for event in bundle["events"]}
    rows = [unit.to_dict() for unit in units]
    requested = set(frozen_ids) if frozen_ids is not None else None
    units_by_key = _read_units(rows, set(events), published_at, requested or ())
    known_ids = {identity for unit in units_by_key.values() for identity in unit.event_ids}
    bounds = _read_ended_before(dict(ended_before or {}), known_ids, published_at)
    if actual_end is not None:
        for identity, event in events.items():
            ended = actual_end(event)
            if ended is not None and ended.tzinfo is not None and ended <= published_at:
                if identity not in bounds or ended < _instant(bounds[identity]):
                    bounds[identity] = ended.isoformat()

    def end_proof(event):
        return _instant(bounds[event["event_id"]]) if event["event_id"] in bounds else None

    selected = (
        requested
        if requested is not None
        else {
            key
            for key, event in events.items()
            if event_is_frozen(
                event, published_at, result_confirmed=result_confirmed, never_result=never_result, actual_end=end_proof
            )
        }
    )
    if selected - known_ids:
        raise ValueError("unknown_frozen_event")
    if not _frozen_bounds_valid(selected, bounds, published_at):
        raise ValueError("frozen_end_evidence")
    return {
        "schema_version": "1",
        "published_at": published_at.isoformat(),
        "files": {name: hashlib.sha256(files[name]).hexdigest() for name in ["manifest.json", *sorted(bundles)]},
        "frozen_event_ids": sorted(selected),
        "ended_before": bounds,
        "units": rows,
    }


def load_published_baseline(
    read_bytes: Callable[[str], bytes],
    *,
    now: datetime,
    expected_years: Iterable[int],
    force_full: bool = False,
    read_many: Callable[[Iterable[str]], Mapping[str, bytes]] | None = None,
) -> Baseline:
    """Load exact published proof; age alone never refreshes frozen records.

    Unfrozen records acquire eligibility only after a new source confirmation,
    not merely by aging while this baseline is read.
    """
    if force_full:
        return Baseline(reason="force_full")
    try:
        state = json.loads(read_bytes("refresh-state.json"))
        if state["schema_version"] != "1":
            return Baseline(reason="state_schema")
        if "ended_before" not in state:
            return Baseline(reason="end_evidence_missing")
        published = _instant(state["published_at"])
        if published > now:
            return Baseline(reason="publication_future")
        if any(
            not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".json")
            for name in state["files"]
        ):
            return Baseline(reason="file_name")
        names = tuple(state["files"])
        bodies = dict(read_many(names)) if read_many is not None else {name: read_bytes(name) for name in names}
        if set(bodies) != set(names):
            return Baseline(reason="file_coverage")
        if any(hashlib.sha256(body).hexdigest() != state["files"][name] for name, body in bodies.items()):
            return Baseline(reason="file_hash")
        manifest = json.loads(bodies["manifest.json"])
        if not set(expected_years) <= set(manifest["available_seasons"]):
            return Baseline(reason="missing_years")
        if set(bodies) != {"manifest.json", *_catalog(manifest)}:
            return Baseline(reason="file_coverage")
        bundles = _read_files(manifest, bodies.__getitem__)
        events = {event["event_id"]: event for bundle in bundles.values() for event in bundle["events"]}
        frozen = set(state["frozen_event_ids"])
        units = _read_units(state["units"], set(events), published, frozen)
        known_ids = {identity for unit in units.values() for identity in unit.event_ids}
        bounds = _read_ended_before(state["ended_before"], known_ids, published)
        if not _frozen_bounds_valid(frozen, bounds, _instant(state["published_at"])):
            return Baseline(reason="frozen_end_evidence")
        return Baseline(
            manifest=manifest, bundles=bundles, units=units, frozen_ids=frozenset(frozen), ended_before=bounds
        )
    except (OSError, EOFError, zlib.error, ValueError, TypeError, KeyError, AttributeError):
        return Baseline(reason="missing_or_invalid_baseline")
