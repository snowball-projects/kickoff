"""Offline team-image lookup. Daily schedule publication never fetches metadata."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit

from kickoff.models import CalendarEvent, Participant
from kickoff.textutils import espn_logo_url

TEAM_SPORTS = {"soccer", "football", "basketball", "baseball", "hockey", "rugby", "cricket"}
LOGO_FIELDS = ("logo_url", "logo_source_url", "logo_checked_date")


@cache
def country_images() -> dict:
    return json.loads(files("kickoff").joinpath("config/espn-country-images.json").read_text())["assets"]


def participant_logo(participant: Participant, value: object) -> str | None:
    """Country assets need a separately sourced national identity and audited match."""
    if participant.entity_type not in {"team", "club", "national_team"}:
        return None
    logo = espn_logo_url(value)
    if logo is None:
        return None
    path = parse_qs(urlsplit(logo).query)["img"][0]
    if path.casefold().startswith("/i/teamlogos/countries/"):
        metadata = participant.metadata
        asset = country_images().get(path)
        if (
            participant.entity_type != "national_team"
            or not asset
            or metadata.get("country_code") != asset["country_code"]
        ):
            return None
    return logo


def source_logo(team: dict, participant: Participant) -> str | None:
    candidates = [team.get("logo")]
    if isinstance(team.get("logos"), list):
        candidates.extend(row.get("href") for row in team["logos"] if isinstance(row, dict))
    return next((logo for value in candidates if (logo := participant_logo(participant, value))), None)


def cohort_key(event: CalendarEvent, participant: Participant) -> str:
    return json.dumps(
        [
            event.league,
            event.source,
            event.season,
            participant.participant_id,
            participant.name,
            participant.short_name,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )


@cache
def logo_registry() -> tuple[dict, dict]:
    config = files("kickoff").joinpath("config")
    return (
        json.loads(config.joinpath("team_logos.json").read_text())["logos"],
        json.loads(config.joinpath("team_logo_receipts.json").read_text())["teams"],
    )


def _apply(event: CalendarEvent, participant: Participant, logo: str, source_url: str, checked: str) -> None:
    for target in (participant, event.home_participant, event.away_participant):
        if target is not None and target.role == participant.role and target.name == participant.name:
            if participant_logo(target, logo):
                target.metadata.update(logo_url=logo, logo_source_url=source_url, logo_checked_date=checked)


def enrich_team_logos(events: list[CalendarEvent]) -> None:
    """Use source-supplied images first, then the checked-in cohort registry."""
    logos, receipts = logo_registry()
    supplied_images = {}
    for event in events:
        for participant in [*event.participants, event.home_participant, event.away_participant]:
            if participant is not None and "logo_url" in participant.metadata:
                if participant_logo(participant, participant.metadata["logo_url"]) is None:
                    for field in LOGO_FIELDS:
                        participant.metadata.pop(field, None)
    for event in events:
        if event.sport in TEAM_SPORTS:
            for participant in event.participants:
                metadata = participant.metadata
                logo = participant_logo(participant, metadata.get("logo_url"))
                if logo and metadata.get("logo_source_url") and metadata.get("logo_checked_date"):
                    supplied_images[cohort_key(event, participant)] = (
                        logo,
                        metadata["logo_source_url"],
                        metadata["logo_checked_date"],
                    )
    for event in events:
        if event.sport not in TEAM_SPORTS:
            continue
        for participant in event.participants:
            if participant.entity_type not in {"team", "club", "national_team"}:
                continue
            key = cohort_key(event, participant)
            metadata = participant.metadata
            own = participant_logo(participant, metadata.get("logo_url"))
            supplied = (
                (own, metadata["logo_source_url"], metadata["logo_checked_date"])
                if own and metadata.get("logo_source_url") and metadata.get("logo_checked_date")
                else supplied_images.get(key)
            )
            receipt = receipts.get(key, {})
            registered = participant_logo(participant, logos.get(key))
            choice = supplied or ((registered, receipt["source_url"], receipt["checked_date"]) if registered else None)
            if choice:
                _apply(event, participant, *choice)
