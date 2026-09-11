from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from sportsbro.dataset import load_events_from_json
from sportsbro.models import CalendarEvent, ProviderRunResult
from sportsbro.normalize import dedupe_events, sort_events
from sportsbro.settings import Settings

CSV_COLUMNS = [
    "event_id",
    "source",
    "sport",
    "league",
    "season",
    "event_type",
    "title",
    "subtitle",
    "start_time_utc",
    "start_time_local",
    "timezone",
    "status",
    "venue",
    "city",
    "region",
    "country",
    "round_or_stage",
    "week_label",
    "calendar_date",
    "end_calendar_date",
    "competition_phase",
    "is_regular_season",
    "is_postseason",
    "is_exhibition",
    "is_support_event",
    "tags",
]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_provider_raw(result: ProviderRunResult, settings: Settings) -> None:
    provider_root = settings.raw_dir / result.provider_key / str(result.season)
    provider_root.mkdir(parents=True, exist_ok=True)
    for artifact in result.raw_artifacts:
        target = provider_root / artifact.relative_path
        _write_bytes(target, artifact.content)
    manifest = {
        "provider": result.provider_key,
        "season": result.season,
        "warnings": result.warnings,
        "metadata": result.metadata,
        "raw_artifacts": [artifact.relative_path for artifact in result.raw_artifacts],
    }
    _write_text(provider_root / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=True))


def _flatten_event_for_csv(event: CalendarEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "source": event.source,
        "sport": event.sport,
        "league": event.league,
        "season": event.season,
        "event_type": event.event_type,
        "title": event.title,
        "subtitle": event.subtitle,
        "start_time_utc": event.start_time_utc,
        "start_time_local": event.start_time_local,
        "timezone": event.timezone,
        "status": event.status,
        "venue": event.venue,
        "city": event.city,
        "region": event.region,
        "country": event.country,
        "round_or_stage": event.round_or_stage,
        "week_label": event.week_label,
        "calendar_date": event.calendar_date,
        "end_calendar_date": event.end_calendar_date,
        "competition_phase": event.competition_phase,
        "is_regular_season": event.is_regular_season,
        "is_postseason": event.is_postseason,
        "is_exhibition": event.is_exhibition,
        "is_support_event": event.is_support_event,
        "tags": "|".join(event.tags),
    }


def write_normalized_bundle(events: list[CalendarEvent], target_root: Path, stem: str) -> None:
    canonical_events = sort_events(dedupe_events(events))
    payload = [event.to_dict() for event in canonical_events]
    _write_text(target_root / f"{stem}.json", json.dumps(payload, indent=2, ensure_ascii=True))
    with (target_root / f"{stem}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for event in canonical_events:
            writer.writerow(_flatten_event_for_csv(event))


def _provider_json_paths(target_root: Path) -> list[Path]:
    return sorted(path for path in target_root.glob("*.json") if path.name not in {"all_events.json", "manifest.json"})


def _provider_manifest_fragment(settings: Settings, season: int, provider_key: str, event_count: int) -> dict[str, Any]:
    raw_manifest_path = settings.raw_dir / provider_key / str(season) / "manifest.json"
    if raw_manifest_path.exists():
        payload = json.loads(raw_manifest_path.read_text(encoding="utf-8"))
        payload["event_count"] = event_count
        return payload
    return {
        "provider": provider_key,
        "season": season,
        "event_count": event_count,
        "raw_artifacts": [],
        "warnings": ["raw manifest missing"],
        "metadata": {},
    }


def rebuild_season_outputs(settings: Settings, season: int) -> list[CalendarEvent]:
    target_root = settings.normalized_dir / str(season)
    target_root.mkdir(parents=True, exist_ok=True)

    merged_events: list[CalendarEvent] = []
    provider_fragments: list[dict[str, Any]] = []

    for provider_path in _provider_json_paths(target_root):
        provider_key = provider_path.stem
        provider_events = load_events_from_json(provider_path)
        merged_events.extend(provider_events)
        provider_fragments.append(_provider_manifest_fragment(settings, season, provider_key, len(provider_events)))

    write_normalized_bundle(merged_events, target_root, "all_events")
    manifest: dict[str, Any] = {
        "season": season,
        "providers": provider_fragments,
        "all_events": len(sort_events(dedupe_events(merged_events))),
    }
    _write_text(target_root / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=True))
    return sort_events(dedupe_events(merged_events))


def write_run_outputs(
    provider_results: list[ProviderRunResult],
    settings: Settings,
    season: int,
) -> list[CalendarEvent]:
    target_root = settings.normalized_dir / str(season)
    target_root.mkdir(parents=True, exist_ok=True)

    for result in provider_results:
        write_provider_raw(result, settings)
        write_normalized_bundle(result.events, target_root, result.provider_key)

    return rebuild_season_outputs(settings, season)
