from __future__ import annotations

import json
from pathlib import Path

from sportsbro.models import CalendarEvent, Participant


def event_from_dict(item: dict) -> CalendarEvent:
    participants = [Participant(**participant) for participant in item.get("participants", [])]
    home = item.get("home_participant")
    away = item.get("away_participant")
    return CalendarEvent(
        **{
            **item,
            "end_calendar_date": item.get("end_calendar_date"),
            "participants": participants,
            "home_participant": Participant(**home) if home else None,
            "away_participant": Participant(**away) if away else None,
        }
    )


def load_events_from_json(path: Path) -> list[CalendarEvent]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [event_from_dict(item) for item in payload]
