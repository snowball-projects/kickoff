from __future__ import annotations

from dataclasses import fields
from datetime import date

from sportsbro.models import CalendarEvent
from sportsbro.semantics import COMPETITION_PHASES, classification_fields

REQUIRED_STRING_FIELDS = [
    "event_id",
    "source",
    "sport",
    "league",
    "season",
    "event_type",
    "title",
    "status",
]


def validate_event(event: CalendarEvent) -> list[str]:
    errors: list[str] = []
    for field_name in REQUIRED_STRING_FIELDS:
        value = getattr(event, field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{event.event_id or '<missing-id>'}: missing {field_name}")

    if event.calendar_date is None:
        errors.append(f"{event.event_id}: missing calendar_date")

    if event.start_time_local and not event.timezone:
        errors.append(f"{event.event_id}: start_time_local present without timezone")

    try:
        start_date = date.fromisoformat(event.calendar_date) if event.calendar_date else None
        end_date = date.fromisoformat(event.end_calendar_date) if event.end_calendar_date else None
        if start_date and end_date and end_date < start_date:
            errors.append(f"{event.event_id}: end_calendar_date precedes calendar_date")
    except (ValueError, TypeError):
        errors.append(f"{event.event_id}: invalid calendar date")

    if event.home_participant and event.home_participant.role not in {None, "home"}:
        errors.append(f"{event.event_id}: home participant role should be 'home'")

    if event.away_participant and event.away_participant.role not in {None, "away"}:
        errors.append(f"{event.event_id}: away participant role should be 'away'")

    if event.competition_phase not in COMPETITION_PHASES:
        errors.append(f"{event.event_id}: invalid competition_phase '{event.competition_phase}'")
    else:
        expected = classification_fields(event.competition_phase)
        for field_name in ("is_regular_season", "is_postseason", "is_exhibition", "is_support_event"):
            if getattr(event, field_name) != expected[field_name]:
                errors.append(
                    f"{event.event_id}: {field_name} does not match competition_phase '{event.competition_phase}'"
                )

    return errors


def validate_batch(events: list[CalendarEvent]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for event in events:
        errors.extend(validate_event(event))
        if event.event_id in seen_ids:
            errors.append(f"{event.event_id}: duplicate event_id")
        seen_ids.add(event.event_id)
    return errors


def schema_field_names() -> list[str]:
    return [field.name for field in fields(CalendarEvent)]
