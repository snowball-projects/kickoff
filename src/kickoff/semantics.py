from __future__ import annotations

from kickoff.models import CalendarEvent, ProviderOptions

COMPETITION_PHASES = {
    "regular_season",
    "league_phase",
    "group_stage",
    "postseason",
    "knockout",
    "final",
    "championship",
    "preseason",
    "exhibition",
    "special",
    "qualifying",
    "testing",
    "support_event",
}

SPECIAL_COMPETITION_PHASES = {
    "preseason",
    "exhibition",
    "special",
    "qualifying",
    "testing",
}

REGULAR_LIKE_PHASES = {
    "regular_season",
    "league_phase",
    "group_stage",
}

POSTSEASON_PHASES = {
    "postseason",
    "knockout",
    "final",
    "championship",
}


def classification_fields(competition_phase: str) -> dict[str, bool | str]:
    if competition_phase not in COMPETITION_PHASES:
        competition_phase = "special"
    return {
        "competition_phase": competition_phase,
        "is_regular_season": competition_phase in REGULAR_LIKE_PHASES,
        "is_postseason": competition_phase in POSTSEASON_PHASES,
        "is_exhibition": competition_phase in {"preseason", "exhibition", "testing"},
        "is_support_event": competition_phase == "support_event",
    }


def include_competition_phase(competition_phase: str, options: ProviderOptions) -> bool:
    if competition_phase == "support_event":
        return options.include_support_events
    if competition_phase == "qualifying" and options.motorsport_view == "full_weekend":
        return True
    if competition_phase in POSTSEASON_PHASES:
        return options.event_scope == "all_published"
    if competition_phase in SPECIAL_COMPETITION_PHASES:
        return options.include_special_events
    return True


def is_special_phase(competition_phase: str) -> bool:
    return competition_phase in SPECIAL_COMPETITION_PHASES or competition_phase == "support_event"


def is_malformed_event(event: CalendarEvent) -> bool:
    if not event.title.strip() or event.title.strip().casefold() == "at":
        return True
    if not event.calendar_date:
        return True
    if event.event_type == "game":
        if not event.home_participant or not event.away_participant:
            return True
        if not event.home_participant.name.strip() or not event.away_participant.name.strip():
            return True
    return False
