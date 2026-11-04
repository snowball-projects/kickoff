"""Fetch every schedule into generated static assets; primary feed failures stop publication."""

import argparse
import json
import shutil
import sys
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from types import SimpleNamespace
from urllib.parse import quote
from urllib.request import Request, urlopen

from kickoff.feeds import FEEDS
from kickoff.http import MAX_BYTES, read_bounded_response
from kickoff.incremental import RefreshPlan
from kickoff.open_schedules import refresh_open_schedules
from kickoff.published import publish_sports
from kickoff.refresh_metrics import refresh_metrics
from kickoff.refresh_state import (
    Baseline,
    build_refresh_state,
    end_bound_aged,
    event_is_frozen,
    load_published_baseline,
    team_result_confirmed,
)
from kickoff.result_loader import ResultsLoader
from kickoff.weightlifting_startlists import StartListLoader

PUBLIC_DATA = "https://snowball-projects.github.io/kickoff/data/"
BASELINE_BUDGET_SECONDS = 90
BASELINE_SOCKET_SECONDS = 15


class PublishedFiles:
    """Read our CDN with normal caching, gzip and eight bounded concurrent reads."""

    def __init__(self):
        self.deadline = monotonic() + BASELINE_BUDGET_SECONDS

    def read_bytes(self, name: str) -> bytes:
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Published baseline deadline exceeded")
        request = Request(
            PUBLIC_DATA + quote(name, safe=""),
            headers={
                "User-Agent": "kickoff-refresh (https://github.com/snowball-projects/kickoff)",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        chunks, size = [], 0
        with urlopen(request, timeout=min(BASELINE_SOCKET_SECONDS, remaining)) as response:
            while True:
                if monotonic() >= self.deadline:
                    raise TimeoutError("Published baseline deadline exceeded")
                chunk = response.read1(min(65_536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Published baseline exceeds transfer size limit")
            buffered = SimpleNamespace(headers=response.headers, read=BytesIO(b"".join(chunks)).read)
        if monotonic() >= self.deadline:
            raise TimeoutError("Published baseline deadline exceeded")
        return read_bounded_response(buffered)

    def read_many(self, names):
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(self.read_bytes, name): name for name in names}
            try:
                return {
                    futures[future]: future.result()
                    for future in as_completed(futures, timeout=max(0, self.deadline - monotonic()))
                }
            except BaseException:
                for future in futures:
                    future.cancel()
                raise


def _aware(value: str | None) -> datetime | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _scope_changed(before: dict, after: dict) -> bool:
    fields = (
        "source",
        "sport",
        "league",
        "season",
        "event_type",
        "calendar_date",
        "end_calendar_date",
        "start_time_utc",
        "round_or_stage",
    )
    if any(before.get(key) is not None and after.get(key) is not None and before[key] != after[key] for key in fields):
        return True
    old_scope = (before.get("result") or {}).get("scope") or {}
    new_scope = (after.get("result") or {}).get("scope") or {}
    keys = ("event_url", "discipline", "category", "category_id", "gender", "weight_class", "group", "session_id")
    if any(key in old_scope and key in new_scope and old_scope[key] != new_scope[key] for key in keys):
        return True
    old_count, new_count = old_scope.get("expected_category_count"), new_scope.get("expected_category_count")
    if old_count is not None and new_count is not None:
        if old_count != new_count:
            return True
        old_ids, new_ids = old_scope.get("category_ids", []), new_scope.get("category_ids", [])
        # A partial parser result is not proof of a different final block.
        return len(old_ids) == old_count and len(new_ids) == new_count and old_ids != new_ids
    return False


def finalized_state(plan: RefreshPlan, events: dict, published_at: datetime, *, freeze_eligible=None, actual_end=None):
    """Observe end upper bounds without turning schedule dates into finish times."""
    effective = plan.units
    known_ids = {identity for unit in effective.values() for identity in unit.event_ids}
    confirmed = set(plan.confirmed_results) & known_ids
    observed = {identity for unit in plan.current.values() for identity in unit.event_ids}
    observations = {}
    for unit in plan.current.values():
        if not unit.complete:
            continue
        for identity in unit.event_ids:
            if identity in unit.unresolved:
                continue
            if identity in events and not team_result_confirmed(events[identity]):
                continue
            confirmed.add(identity)
            seen = _aware(unit.observed_at) or published_at
            observations[identity] = min(observations.get(identity, seen), seen)
    frozen = set(plan.baseline.frozen_ids)
    bounds = dict(plan.baseline.ended_before)
    explicit_reopen = {
        "status_scheduled",
        "status_postponed",
        "status_in_progress",
        "status_canceled",
        "status_cancelled",
        "status_suspended",
        "scheduled",
        "pre-game",
        "warmup",
        "in progress",
        "postponed",
        "canceled",
        "cancelled",
        "suspended",
        "fut",
        "pre",
        "live",
        "crit",
        "ppd",
        "cncl",
    }
    reopened = {
        identity
        for unit in plan.current.values()
        for identity, reason in unit.unresolved.items()
        if reason.casefold() in explicit_reopen and identity not in frozen
    }
    previous_events = plan.baseline.events
    changed = {
        identity
        for identity in observed & events.keys() & previous_events.keys()
        if identity not in frozen and _scope_changed(previous_events[identity], events[identity])
    }
    for identity in reopened | changed:
        bounds.pop(identity, None)
    confirmed.difference_update(reopened)
    for identity in confirmed - frozen:
        ended = actual_end(events[identity]) if actual_end is not None and identity in events else None
        # A specialized result may be fetched after its schedule request. Unless
        # an exact result response time exists, completion of this collection is
        # a safe observed-by bound, never the timetable's historical check date.
        seen = observations.get(identity, published_at)
        result_bound = _aware(getattr(plan, "result_end_bounds", {}).get(identity))
        if result_bound is not None and result_bound <= published_at:
            seen = min(seen, result_bound)
        if ended is not None and ended.tzinfo is not None:
            seen = min(seen, ended)
        if identity not in bounds or seen < _aware(bounds[identity]):
            bounds[identity] = seen.isoformat()
    policy = freeze_eligible or event_is_frozen
    eligible = set(frozen)
    for identity in confirmed - frozen:
        if identity in events:
            if policy(
                events[identity],
                published_at,
                result_confirmed=lambda row: row["event_id"] in confirmed,
                actual_end=lambda row: _aware(bounds[row["event_id"]]) if row["event_id"] in bounds else None,
            ):
                eligible.add(identity)
        elif end_bound_aged(bounds.get(identity), published_at):
            eligible.add(identity)
    units = []
    for unit in effective.values():
        unresolved = {
            identity: reason
            for identity, reason in unit.unresolved.items()
            if not (identity in confirmed and reason == "result_unconfirmed")
        }
        for identity in set(unit.event_ids) - events.keys():
            if identity in eligible:
                if identity in confirmed and unresolved.get(identity) == "outside_published_coverage":
                    del unresolved[identity]
            else:
                unresolved.setdefault(identity, "outside_published_coverage")
        units.append(replace(unit, unresolved=unresolved))
    return units, eligible, bounds


def refresh(
    years: list[int],
    output: Path,
    reviewed: Path,
    *,
    force_full: bool = False,
    read_bytes=None,
    read_many=None,
    clock=None,
    result_loader=None,
    freeze_eligible=None,
    actual_end=None,
) -> RefreshPlan:
    with refresh_metrics() as metrics:
        clock = clock or (lambda: datetime.now(timezone.utc))
        now = clock()
        if force_full:
            baseline = Baseline(reason="force_full")
        else:
            if read_bytes is None:
                reader = PublishedFiles()
                read_bytes, read_many = reader.read_bytes, reader.read_many
            baseline = load_published_baseline(read_bytes, read_many=read_many, now=now, expected_years=years)
        plan = RefreshPlan(baseline, now)
        metrics.plan = plan
        metrics.frozen = len(plan.baseline.frozen_ids)
        start_lists = StartListLoader()
        with TemporaryDirectory(prefix="kickoff-collect-") as staging:
            staging = Path(staging)
            collected = staging / "collected"
            collected.mkdir()
            bundles = [
                json.loads(
                    refresh_open_schedules(
                        year,
                        collected,
                        reviewed,
                        feeds=FEEDS,
                        available_seasons=years,
                        enrich_times=True,
                        start_list_loader=start_lists,
                        result_loader=result_loader,
                        plan=plan,
                    ).read_text()
                )
                for year in years
            ]
            published = staging / "published"
            publish_sports(bundles, published)
            files = {path.name: path.read_bytes() for path in published.glob("*.json")}
            manifest = json.loads(files["manifest.json"])
            names = [row["file"] for season in manifest["seasons"].values() for row in season["sports"]]
            events = {event["event_id"]: event for name in names for event in json.loads(files[name])["events"]}
            published_at = clock()
            units, eligible, bounds = finalized_state(
                plan, events, published_at, freeze_eligible=freeze_eligible, actual_end=actual_end
            )
            metrics.frozen = len(eligible)
            state = build_refresh_state(
                files, units, published_at=published_at, frozen_ids=eligible, ended_before=bounds
            )
            (published / "refresh-state.json").write_text(json.dumps(state, separators=(",", ":")) + "\n")
            output.mkdir(parents=True, exist_ok=True)
            # State and manifest follow the data; generated-file cleanup is confined
            # to the fresh staging directory. Local ignored/extra files are retained.
            paths = sorted(
                path for path in published.iterdir() if path.name not in {"manifest.json", "refresh-state.json"}
            )
            paths += [published / "manifest.json", published / "refresh-state.json"]
            for path in paths:
                shutil.copyfile(path, output / path.name)
        return plan


def coverage_years(today: date) -> list[int]:
    """Source years for the rolling window in every visitor timezone.

    Two boundary days cover the UTC/local today difference plus an event's
    source-date conversion. Annual bundles retain these boundary spillovers.
    """
    start = today.replace(year=today.year - 1, day=min(today.day, monthrange(today.year - 1, today.month)[1]))
    end = today.replace(year=today.year + 1, day=min(today.day, monthrange(today.year + 1, today.month)[1]))
    return list(range((start - timedelta(days=2)).year, (end + timedelta(days=2)).year + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        help="Calendar year; repeatable. Default: one year back through one year forward",
    )
    parser.add_argument("--force-full", action="store_true", help="Rebuild without reading the published baseline")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    years = args.year or coverage_years(datetime.now(timezone.utc).date())
    refresh(
        years,
        root / "frontend/public/data",
        root / "data/reviewed",
        force_full=args.force_full,
        result_loader=ResultsLoader(),
    )
    for name in ["LICENSE", "THIRD-PARTY-NOTICES.md"]:
        shutil.copyfile(root / name, root / "frontend/public" / name)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
