"""Exact source scope for preserving previously published optional results."""

from kickoff.models import CalendarEvent


def same_result_scope(event: CalendarEvent | dict, previous: dict) -> bool:
    """Identity and source scope must match before reusing an optional result."""
    return all(
        (event.get(key) if isinstance(event, dict) else getattr(event, key)) == previous.get(key)
        for key in (
            "event_id",
            "source",
            "sport",
            "league",
            "season",
            "event_type",
            "title",
            "round_or_stage",
            "source_url",
            "calendar_date",
            "end_calendar_date",
        )
    ) and sorted(event.get("tags", []) if isinstance(event, dict) else event.tags) == sorted(previous.get("tags", []))
