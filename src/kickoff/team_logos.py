"""Offline team-image lookup. Daily schedule publication never fetches metadata."""

from __future__ import annotations

import json
import re
from functools import cache
from importlib.resources import files

from kickoff.models import CalendarEvent, Participant
from kickoff.textutils import espn_logo_url

TEAM_SPORTS = {"soccer", "football", "basketball", "baseball", "hockey", "rugby", "cricket"}
LOGO_FIELDS = ("logo_url", "logo_source_url", "logo_checked_date")
COHORT_FIELDS = ("league", "source", "season", "participant_id", "name", "short_name")


def source_logo(team: dict) -> str | None:
    candidates = [team.get("logo")]
    if isinstance(team.get("logos"), list):
        candidates.extend(row.get("href") for row in team["logos"] if isinstance(row, dict))
    return next((logo for value in candidates if (logo := espn_logo_url(value))), None)


def competition_season(event) -> int | None:
    if event.league == "NHL":
        return int(event.season[4:]) if re.fullmatch(r"\d{8}", event.season) else None
    if re.fullmatch(r"\d{4}-\d{2}", event.season):
        start = int(event.season[:4])
        return start if int(event.season[5:]) == (start + 1) % 100 else None
    return int(event.season) if re.fullmatch(r"\d{4}", event.season) else None


def cohort(event, participant: Participant) -> dict:
    return {
        "league": event.league,
        "source": event.source,
        "season": event.season,
        "participant_id": participant.participant_id,
        "name": participant.name,
        "short_name": participant.short_name,
        "competition_season": competition_season(event),
    }


def cohort_key(row: dict) -> str:
    return json.dumps([row[field] for field in COHORT_FIELDS], ensure_ascii=True, separators=(",", ":"))


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
            target.metadata.update(logo_url=logo, logo_source_url=source_url, logo_checked_date=checked)


def enrich_team_logos(events: list[CalendarEvent]) -> list[dict]:
    """Use source-supplied images first, then the checked-in cohort registry."""
    logos, receipts = logo_registry()
    supplied_images = {}
    for event in events:
        if event.sport in TEAM_SPORTS:
            for participant in event.participants:
                metadata = participant.metadata
                logo = espn_logo_url(metadata.get("logo_url"))
                if logo and metadata.get("logo_source_url") and metadata.get("logo_checked_date"):
                    supplied_images[cohort_key(cohort(event, participant))] = (
                        logo,
                        metadata["logo_source_url"],
                        metadata["logo_checked_date"],
                    )
    observations = {}
    for event in events:
        if event.sport not in TEAM_SPORTS:
            continue
        for participant in event.participants:
            if participant.entity_type not in {"team", "club", "national_team"}:
                continue
            row = cohort(event, participant)
            key = cohort_key(row)
            metadata = participant.metadata
            own = espn_logo_url(metadata.get("logo_url"))
            supplied = (
                (own, metadata["logo_source_url"], metadata["logo_checked_date"])
                if own and metadata.get("logo_source_url") and metadata.get("logo_checked_date")
                else supplied_images.get(key)
            )
            receipt = receipts.get(key, {})
            choice = supplied or (
                (logos[key], receipt["source_url"], receipt["checked_date"]) if key in logos else None
            )
            if choice:
                _apply(event, participant, *choice)
            observations[key] = {
                **row,
                "status": "logo" if choice else receipt.get("status", "unregistered"),
                "logo_url": choice[0] if choice else None,
                "source_url": choice[1] if choice else receipt.get("source_url"),
            }
    return list(observations.values())
