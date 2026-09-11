from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sportsbro.dataset import load_events_from_json
from sportsbro.models import CalendarEvent
from sportsbro.settings import Settings


def _duplicate_candidate_key(event: CalendarEvent) -> tuple[str, ...]:
    start_marker = event.start_time_utc or event.start_time_local or ""
    if event.home_participant and event.away_participant:
        participants = tuple(sorted([event.home_participant.name, event.away_participant.name]))
        return (
            event.league,
            event.calendar_date or "",
            start_marker,
            event.event_type,
            event.competition_phase,
            *participants,
        )

    participant_names = tuple(sorted(participant.name for participant in event.participants))
    if participant_names:
        return (
            event.league,
            event.calendar_date or "",
            start_marker,
            event.event_type,
            event.competition_phase,
            *participant_names,
        )

    return (
        event.league,
        event.calendar_date or "",
        start_marker,
        event.event_type,
        event.competition_phase,
        event.title,
    )


def summarize_events(events: list[CalendarEvent]) -> dict[str, Any]:
    round_counts = Counter(event.round_or_stage or "<none>" for event in events)
    status_counts = Counter(event.status for event in events)
    type_counts = Counter(event.event_type for event in events)
    phase_counts = Counter(event.competition_phase for event in events)
    dates = sorted(event.calendar_date for event in events if event.calendar_date)

    event_id_counts = Counter(event.event_id for event in events)
    duplicate_event_ids = [
        {"event_id": event_id, "count": count} for event_id, count in event_id_counts.items() if count > 1
    ]

    candidate_groups: defaultdict[tuple[str, ...], list[CalendarEvent]] = defaultdict(list)
    for event in events:
        candidate_groups[_duplicate_candidate_key(event)].append(event)

    duplicate_candidates = []
    for key, group in candidate_groups.items():
        if len(group) < 2:
            continue
        duplicate_candidates.append(
            {
                "key": " | ".join(key),
                "count": len(group),
                "event_ids": [event.event_id for event in group],
                "titles": [event.title for event in group],
            }
        )

    duplicate_candidates.sort(key=lambda item: (-item["count"], item["key"]))

    return {
        "total_event_count": len(events),
        "counts_by_event_type": dict(type_counts),
        "counts_by_status": dict(status_counts),
        "counts_by_round_or_stage": dict(round_counts),
        "counts_by_competition_phase": dict(phase_counts),
        "min_date": dates[0] if dates else None,
        "max_date": dates[-1] if dates else None,
        "duplicate_event_ids": duplicate_event_ids,
        "duplicate_candidates": duplicate_candidates[:25],
    }


def audit_normalized_provider(settings: Settings, season: int, provider_key: str) -> dict[str, Any]:
    target = settings.normalized_dir / str(season) / f"{provider_key}.json"
    if not target.exists():
        raise FileNotFoundError(target)
    events = load_events_from_json(target)
    summary = summarize_events(events)
    summary["provider"] = provider_key
    summary["season"] = season
    return summary


def audit_normalized_selection(settings: Settings, season: int, provider_keys: list[str]) -> dict[str, Any]:
    return {
        "season": season,
        "providers": [audit_normalized_provider(settings, season, provider_key) for provider_key in provider_keys],
    }
