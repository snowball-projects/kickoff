from __future__ import annotations

import json
from collections import Counter

from sportsbro.http import FetchError, fetch_json
from sportsbro.models import CalendarEvent, Participant, ProviderOptions, ProviderRunResult, RawArtifact
from sportsbro.normalize import stable_event_id
from sportsbro.provider_utils import EventAccumulator
from sportsbro.providers.base import Provider
from sportsbro.semantics import classification_fields
from sportsbro.settings import Settings
from sportsbro.timeutils import isoformat_local, isoformat_z, parse_iso_datetime, utc_to_timezone

NHL_CLUBS = [
    "ANA",
    "BOS",
    "BUF",
    "CAR",
    "CBJ",
    "CGY",
    "CHI",
    "COL",
    "DAL",
    "DET",
    "EDM",
    "FLA",
    "LAK",
    "MIN",
    "MTL",
    "NJD",
    "NSH",
    "NYI",
    "NYR",
    "OTT",
    "PHI",
    "PIT",
    "SEA",
    "SJS",
    "STL",
    "TBL",
    "TOR",
    "UTA",
    "VAN",
    "VGK",
    "WPG",
    "WSH",
]


def _team_name(team: dict) -> str:
    place = (team.get("placeName") or {}).get("default")
    common = (team.get("commonName") or {}).get("default")
    if place and common:
        return f"{place} {common}"
    return team.get("name", {}).get("default") or team.get("abbrev", "Unknown")


def _competition_phase(game_type: int | None) -> str:
    if game_type == 1:
        return "preseason"
    if game_type == 2:
        return "regular_season"
    if game_type == 3:
        return "postseason"
    return "special"


def _subtitle_and_stage(competition_phase: str) -> tuple[str, str]:
    if competition_phase == "preseason":
        return "NHL Preseason", "Preseason"
    if competition_phase == "postseason":
        return "NHL Postseason", "Postseason"
    if competition_phase == "regular_season":
        return "NHL Regular Season", "Regular Season"
    return "NHL Special Event", "Special Event"


def _normalize_status(raw_state: str | None) -> str:
    normalized = str(raw_state or "").strip().upper()
    if normalized in {"FUT", "PRE"}:
        return "scheduled"
    if normalized in {"LIVE", "CRIT"}:
        return "live"
    if normalized in {"OFF", "FINAL"}:
        return "final"
    if normalized == "POST":
        return "postponed"
    return normalized.lower() or "scheduled"


class NHLProvider(Provider):
    key = "nhl"
    league = "NHL"
    sport = "hockey"

    def season_label(self, season: int) -> str:
        return f"{season - 1}-{season}"

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        season_id = f"{season - 1}{season}"
        accumulator = EventAccumulator(options)
        raw_artifacts: list[RawArtifact] = []
        warnings: list[str] = []
        game_type_counts: Counter[str] = Counter()
        state_counts: Counter[str] = Counter()

        for club in NHL_CLUBS:
            url = f"https://api-web.nhle.com/v1/club-schedule-season/{club}/{season_id}"
            try:
                payload = fetch_json(url, settings)
            except FetchError as exc:
                warnings.append(str(exc))
                continue

            raw_artifacts.append(
                RawArtifact(
                    relative_path=f"{club}.json",
                    content=json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8"),
                )
            )
            for game in payload.get("games", []):
                game_id = str(game.get("id"))
                game_type = game.get("gameType")
                competition_phase = _competition_phase(game_type)
                subtitle, round_or_stage = _subtitle_and_stage(competition_phase)
                game_type_counts[str(game_type)] += 1
                state_counts[_normalize_status(game.get("gameState"))] += 1
                away_team = game.get("awayTeam", {}) or {}
                home_team = game.get("homeTeam", {}) or {}
                away_name = _team_name(away_team)
                home_name = _team_name(home_team)
                away = Participant(
                    name=away_name,
                    participant_id=away_team.get("abbrev"),
                    role="away",
                )
                home = Participant(
                    name=home_name,
                    participant_id=home_team.get("abbrev"),
                    role="home",
                )
                utc_dt = parse_iso_datetime(game.get("startTimeUTC"))
                timezone_name = game.get("venueTimezone")
                local_dt = utc_to_timezone(utc_dt, timezone_name)
                venue = game.get("venue", {}) or {}
                game_date = game.get("gameDate")

                accumulator.add(
                    CalendarEvent(
                        event_id=stable_event_id(self.key, season_id, game_id),
                        source="nhl_api_web",
                        sport=self.sport,
                        league=self.league,
                        season=self.season_label(season),
                        event_type="game",
                        title=f"{away_name} at {home_name}",
                        subtitle=subtitle,
                        start_time_utc=isoformat_z(utc_dt),
                        start_time_local=isoformat_local(local_dt),
                        timezone=timezone_name,
                        status=_normalize_status(game.get("gameState")),
                        venue=venue.get("default"),
                        city=None,
                        region=None,
                        country=None,
                        participants=[away, home],
                        home_participant=home,
                        away_participant=away,
                        round_or_stage=round_or_stage,
                        week_label=None,
                        calendar_date=(local_dt.date().isoformat() if local_dt else game_date),
                        end_calendar_date=(local_dt.date().isoformat() if local_dt else game_date),
                        tags=["nhl", "game", competition_phase.replace("_", "-")],
                        raw_source_payload=game,
                        **classification_fields(competition_phase),
                    ),
                    dedupe_key=game_id,
                )

        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=accumulator.events(),
            raw_artifacts=raw_artifacts,
            warnings=warnings,
            metadata={
                "season_id": season_id,
                "source_game_type_counts": dict(game_type_counts),
                "source_status_counts": dict(state_counts),
                "semantics": {
                    "default_behavior": "Regular-season NHL games only.",
                    "all_published_behavior": "Adds postseason if the source publishes it.",
                    "special_behavior": "Adds preseason and other non-regular phases when include_special_events is enabled.",
                    "dedupe_rule": "game id across club schedule feeds",
                },
                **accumulator.metadata(),
            },
        )
