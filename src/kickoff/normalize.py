from __future__ import annotations

import hashlib

from kickoff.models import CalendarEvent


def stable_event_id(*parts: object) -> str:
    canonical = "::".join(str(part).strip() for part in parts if part is not None and str(part).strip())
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    return digest[:20]


def sort_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    return sorted(
        events,
        key=lambda event: (
            event.calendar_date or "9999-12-31",
            event.start_time_utc is None,
            event.start_time_utc or event.start_time_local or "",
            event.league,
            event.title,
            event.event_id,
        ),
    )
