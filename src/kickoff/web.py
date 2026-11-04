from __future__ import annotations

from typing import Any

from kickoff.countries import ISO_CODES
from kickoff.models import CalendarEvent, Participant
from kickoff.team_logos import TEAM_SPORTS, participant_logo
from kickoff.weightlifting_startlists import ENTRY_FIELDS, START_LIST_LEAGUES

SCHEMA_VERSION = "1"
NATIONAL_COUNTRY_CODES = ISO_CODES | {"GB-ENG", "GB-SCT", "GB-WLS", "GB-NIR", "XK"}


def _participant_payload(
    participant: Participant | None, *, include_logo: bool = True, include_start_list: bool = False
) -> dict[str, Any] | None:
    if participant is None:
        return None
    logo = participant_logo(participant, participant.metadata.get("logo_url"))
    return {
        "name": participant.name,
        "participant_id": participant.participant_id,
        "short_name": participant.short_name,
        "role": participant.role,
        "entity_type": participant.entity_type,
        **{
            key: getattr(participant, key)
            for key in ("record", "team_source_url", "final_score")
            if getattr(participant, key) is not None
        },
        **{
            key: participant.metadata[key]
            for key in ("result_winner", "result_advance", "aggregate_score", "shootout_score")
            if key in participant.metadata
        },
        **(
            {
                key: logo if key == "logo_url" else participant.metadata[key]
                for key in ("logo_url", "logo_source_url", "logo_checked_date")
                if key in participant.metadata
            }
            if include_logo
            and logo
            and isinstance(participant.metadata.get("logo_source_url"), str)
            and participant.metadata["logo_source_url"].startswith(
                ("https://site.api.espn.com/apis/site/v2/sports/", "https://sports.core.api.espn.com/v2/sports/")
            )
            and isinstance(participant.metadata.get("logo_checked_date"), str)
            and participant.metadata["logo_checked_date"]
            else {}
        ),
        **(
            {key: participant.metadata[key] for key in ENTRY_FIELDS if key in participant.metadata}
            if include_start_list and participant.entity_type == "athlete"
            else {}
        ),
        **(
            {
                "country_code": participant.metadata["country_code"],
                **{
                    key: participant.metadata[key]
                    for key in ("country_source_url", "country_checked_date", "country_source_kind")
                    if key in participant.metadata
                },
            }
            if (
                participant.entity_type == "national_team"
                or (include_start_list and participant.entity_type == "athlete")
            )
            and isinstance(participant.metadata.get("country_code"), str)
            and participant.metadata["country_code"] in NATIONAL_COUNTRY_CODES
            else {}
        ),
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
        **(
            {"start_time_source": event.start_time_source, "start_time_source_url": event.start_time_source_url}
            if event.start_time_source
            else {}
        ),
        "start_time_local": event.start_time_local,
        "timezone": event.timezone,
        "status": event.status,
        **(
            {"facts_checked_date": event.facts_checked_date, "facts_source_url": event.facts_source_url}
            if event.facts_checked_date
            else {}
        ),
        "venue": event.venue,
        "city": event.city,
        "region": event.region,
        "country": event.country,
        **(
            {"country_source_url": event.country_source_url, "country_checked_date": event.country_checked_date}
            if event.country_checked_date
            else {}
        ),
        "participants": [
            _participant_payload(
                participant,
                include_logo=event.sport in TEAM_SPORTS,
                include_start_list=event.sport == "weightlifting" and event.league in START_LIST_LEAGUES,
            )
            for participant in event.participants
        ],
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
        **({"result": event.result} if event.result is not None else {}),
        **({"start_time_scope": event.start_time_scope} if event.start_time_scope != "event" else {}),
    }
