from __future__ import annotations

import re
from dataclasses import fields
from datetime import date

from kickoff.models import CalendarEvent
from kickoff.semantics import COMPETITION_PHASES, classification_fields

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

    if event.start_time_scope not in {"event", "shared_session"}:
        errors.append(f"{event.event_id}: invalid start_time_scope")
    if event.start_time_scope == "shared_session" and not event.start_time_utc:
        errors.append(f"{event.event_id}: shared session scope needs a known session start")

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

    participants = [*event.participants, event.home_participant, event.away_participant]
    has_team_facts = event.week_label is not None or any(
        p and (p.short_name is not None or p.record is not None or p.final_score is not None) for p in participants
    )
    if has_team_facts and not event.facts_checked_date:
        errors.append(f"{event.event_id}: team facts need a checked date")
    if event.facts_checked_date:
        try:
            date.fromisoformat(event.facts_checked_date)
        except (ValueError, TypeError):
            errors.append(f"{event.event_id}: invalid facts_checked_date")
        if not (event.facts_source_url or event.source_url or "").startswith("https://"):
            errors.append(f"{event.event_id}: team facts need a source URL")
    for participant in participants:
        if participant is None:
            continue
        if participant.short_name is not None and (
            not isinstance(participant.short_name, str) or not participant.short_name.strip()
        ):
            errors.append(f"{event.event_id}: invalid team short name")
        if participant.record is not None and (
            not isinstance(participant.record, str) or not re.fullmatch(r"\d+(?:-\d+){1,2}", participant.record)
        ):
            errors.append(f"{event.event_id}: invalid team record")
        if participant.team_source_url is not None and not participant.team_source_url.startswith("https://"):
            errors.append(f"{event.event_id}: invalid team source URL")
        if participant.final_score is not None and (
            type(participant.final_score) is not int or participant.final_score < 0 or event.status != "finished"
        ):
            errors.append(f"{event.event_id}: only confirmed final scores are allowed")

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
