from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any

from sportsbro.models import CalendarEvent


def stable_event_id(*parts: object) -> str:
    canonical = "::".join(str(part).strip() for part in parts if part is not None and str(part).strip())
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    return digest[:20]


def dedupe_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    deduped: OrderedDict[str, CalendarEvent] = OrderedDict()
    for event in events:
        deduped[event.event_id] = event
    return list(deduped.values())


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


def to_jsonable(events: list[CalendarEvent]) -> list[dict[str, Any]]:
    return [event.to_dict() for event in sort_events(dedupe_events(events))]


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
