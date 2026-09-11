from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sportsbro.dataset import load_events_from_json
from sportsbro.models import CalendarEvent, Participant
from sportsbro.normalize import sort_events
from sportsbro.settings import Settings

SCHEMA_VERSION = "1"


def _participant_payload(participant: Participant | None) -> dict[str, Any] | None:
    if participant is None:
        return None
    return {
        "name": participant.name,
        "participant_id": participant.participant_id,
        "short_name": participant.short_name,
        "role": participant.role,
        "entity_type": participant.entity_type,
    }


def _event_payload(event: CalendarEvent) -> dict[str, Any]:
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
        "participants": [_participant_payload(participant) for participant in event.participants],
        "home_participant": _participant_payload(event.home_participant),
        "away_participant": _participant_payload(event.away_participant),
        "home_participant_name": event.home_participant.name if event.home_participant else None,
        "away_participant_name": event.away_participant.name if event.away_participant else None,
        "round_or_stage": event.round_or_stage,
        "week_label": event.week_label,
        "calendar_date": event.calendar_date,
        "end_calendar_date": event.end_calendar_date,
        "source_url": event.source_url,
        "competition_phase": event.competition_phase,
        "is_regular_season": event.is_regular_season,
        "is_postseason": event.is_postseason,
        "is_exhibition": event.is_exhibition,
        "is_support_event": event.is_support_event,
        "tags": event.tags,
    }


def _available_seasons(settings: Settings) -> list[int]:
    if not settings.normalized_dir.exists():
        return []
    return sorted(
        int(path.name)
        for path in settings.normalized_dir.iterdir()
        if path.is_dir() and path.name.isdigit() and (path / "all_events.json").exists()
    )


def _provider_payload(settings: Settings, season: int, item: dict[str, Any]) -> dict[str, Any]:
    provider_key = str(item.get("provider", ""))
    config = settings.providers_config.get(provider_key, {})
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "provider": provider_key,
        "label": config.get("label"),
        "sport": config.get("sport"),
        "season_mode": config.get("season_mode"),
        "season": int(item.get("season", season)),
        "event_count": int(item.get("event_count", 0)),
        "warnings": list(item.get("warnings", [])),
        "default_event_scope": config.get("default_event_scope"),
        "default_include_special_events": config.get("default_include_special_events"),
        "default_include_support_events": config.get("default_include_support_events"),
        "default_motorsport_view": config.get("default_motorsport_view"),
        "semantics": metadata.get("semantics", {}),
    }


def export_web_bundle(settings: Settings, season: int, output_dir: Path) -> Path:
    season_root = settings.normalized_dir / str(season)
    events_path = season_root / "all_events.json"
    manifest_path = season_root / "manifest.json"
    if not events_path.exists():
        raise FileNotFoundError(events_path)
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events = sort_events(load_events_from_json(events_path))
    seasons = _available_seasons(settings)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "season": season,
        "available_seasons": seasons,
        "providers": [
            _provider_payload(settings, season, item)
            for item in manifest.get("providers", [])
            if isinstance(item, dict)
        ],
        "events": [_event_payload(event) for event in events],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / f"{season}.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (output_dir / "index.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "available_seasons": seasons}, indent=2, ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )
    return bundle_path
