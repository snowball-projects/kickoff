from __future__ import annotations

import json
from collections import Counter

from kickoff.http import fetch_json
from kickoff.models import CalendarEvent, Participant, ProviderOptions, ProviderRunResult, RawArtifact
from kickoff.normalize import stable_event_id
from kickoff.provider_utils import EventAccumulator
from kickoff.providers.base import Provider
from kickoff.semantics import classification_fields
from kickoff.settings import Settings
from kickoff.timeutils import isoformat_local, isoformat_z, parse_iso_datetime, utc_to_timezone

MLB_PHASE_BY_GAME_TYPE = {
    "R": "regular_season",
    "S": "preseason",
    "E": "exhibition",
    "A": "exhibition",
    "F": "postseason",
    "D": "postseason",
    "L": "postseason",
    "W": "postseason",
    "C": "postseason",
}

MLB_STAGE_BY_GAME_TYPE = {
    "R": "Regular Season",
    "S": "Spring Training",
    "E": "Exhibition",
    "A": "All-Star Game",
}

MLB_STATUS_MAP = {
    "preview": "scheduled",
    "scheduled": "scheduled",
    "pre-game": "scheduled",
    "warmup": "scheduled",
    "live": "live",
    "in progress": "live",
    "manager challenge": "live",
    "game over": "final",
    "final": "final",
    "completed early": "final",
    "postponed": "postponed",
    "delayed": "delayed",
    "suspended": "suspended",
    "cancelled": "cancelled",
}


def _competition_phase(game_type: str | None) -> str:
    return MLB_PHASE_BY_GAME_TYPE.get((game_type or "").upper(), "special")


def _round_or_stage(game_type: str | None) -> str:
    normalized = (game_type or "").upper()
    if normalized in MLB_STAGE_BY_GAME_TYPE:
        return MLB_STAGE_BY_GAME_TYPE[normalized]
    if normalized in {"F", "D", "L", "W", "C"}:
        return f"Postseason ({normalized})"
    return "Special Event"


def _subtitle_for_phase(game_type: str | None, competition_phase: str) -> str:
    stage = _round_or_stage(game_type)
    if competition_phase == "regular_season":
        return "MLB Regular Season"
    if competition_phase == "preseason":
        return "MLB Spring Training"
    if competition_phase == "postseason":
        return "MLB Postseason"
    if stage == "All-Star Game":
        return "MLB All-Star Game"
    if competition_phase == "exhibition":
        return "MLB Exhibition"
    return "MLB Special Event"


def _normalize_status(game: dict) -> str:
    status_payload = game.get("status", {}) or {}
    for key in ("abstractGameState", "detailedState"):
        raw = str(status_payload.get(key) or "").strip().lower()
        if raw:
            return MLB_STATUS_MAP.get(raw, raw.replace(" ", "_"))
    return "scheduled"


class MLBProvider(Provider):
    key = "mlb"
    league = "MLB"
    sport = "baseball"

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        url = (
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}&hydrate=venue(location,timeZone),team"
        )
        payload = fetch_json(url, settings)
        artifacts = [
            RawArtifact(
                relative_path="schedule.json",
                content=json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8"),
            )
        ]
        accumulator = EventAccumulator(options)
        game_type_counts: Counter[str] = Counter()
        for date_block in payload.get("dates", []):
            for game in date_block.get("games", []):
                game_id = game.get("gamePk")
                game_type = str(game.get("gameType") or "").upper()
                game_type_counts[game_type or "<missing>"] += 1
                away_team = game.get("teams", {}).get("away", {}).get("team", {})
                home_team = game.get("teams", {}).get("home", {}).get("team", {})
                venue = game.get("venue", {}) or {}
                venue_location = venue.get("location", {}) or {}
                timezone_name = venue.get("timeZone", {}).get("id")

                utc_dt = parse_iso_datetime(game.get("gameDate"))
                local_dt = utc_to_timezone(utc_dt, timezone_name)

                away_name = str(away_team.get("name") or "").strip()
                home_name = str(home_team.get("name") or "").strip()
                home = Participant(
                    name=home_name,
                    participant_id=str(home_team.get("id")) if home_team.get("id") else None,
                    role="home",
                )
                away = Participant(
                    name=away_name,
                    participant_id=str(away_team.get("id")) if away_team.get("id") else None,
                    role="away",
                )

                competition_phase = _competition_phase(game_type)
                stage = _round_or_stage(game_type)
                tags = ["mlb", "game", competition_phase.replace("_", "-")]
                if stage == "All-Star Game":
                    tags.append("all-star")

                accumulator.add(
                    CalendarEvent(
                        event_id=stable_event_id(self.key, season, game_id),
                        source="mlb_statsapi",
                        sport=self.sport,
                        league=self.league,
                        season=str(season),
                        event_type="game",
                        title=f"{away_name} at {home_name}",
                        subtitle=_subtitle_for_phase(game_type, competition_phase),
                        start_time_utc=isoformat_z(utc_dt),
                        start_time_local=isoformat_local(local_dt),
                        timezone=timezone_name,
                        status=_normalize_status(game),
                        venue=venue.get("name"),
                        city=venue_location.get("city"),
                        region=venue_location.get("stateAbbrev") or venue_location.get("state"),
                        country=venue_location.get("country"),
                        participants=[away, home],
                        home_participant=home,
                        away_participant=away,
                        round_or_stage=stage,
                        week_label=None,
                        calendar_date=(local_dt.date().isoformat() if local_dt else game.get("officialDate")),
                        end_calendar_date=(local_dt.date().isoformat() if local_dt else game.get("officialDate")),
                        tags=tags,
                        raw_source_payload=game,
                        **classification_fields(competition_phase),
                    ),
                    dedupe_key=str(game_id),
                )

        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=accumulator.events(),
            raw_artifacts=artifacts,
            metadata={
                "url": url,
                "source_game_type_counts": dict(game_type_counts),
                "semantics": {
                    "default_behavior": "Regular-season MLB games only.",
                    "all_published_behavior": "Adds postseason when the source publishes it.",
                    "special_behavior": "Adds spring training, exhibitions, and All-Star events when include_special_events is enabled.",
                    "dedupe_rule": "gamePk",
                },
                **accumulator.metadata(),
            },
        )
