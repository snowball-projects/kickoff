from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime

from kickoff.http import FetchError, fetch_bytes, fetch_json, fetch_text
from kickoff.models import CalendarEvent, Participant, ProviderOptions, ProviderRunResult, RawArtifact
from kickoff.normalize import stable_event_id
from kickoff.pdf import extract_pdf_lines
from kickoff.provider_utils import EventAccumulator
from kickoff.providers.base import Provider
from kickoff.semantics import classification_fields
from kickoff.settings import Settings
from kickoff.timeutils import (
    EASTERN_NAME,
    UTC,
    eastern_to_utc,
    get_zoneinfo,
    isoformat_local,
    isoformat_z,
    localize_date_time,
    parse_iso_datetime,
    utc_to_timezone,
)

NBA_PDF_TEAM_MAP = {
    "Atlanta": "Atlanta Hawks",
    "Boston": "Boston Celtics",
    "Brooklyn": "Brooklyn Nets",
    "Charlotte": "Charlotte Hornets",
    "Chicago": "Chicago Bulls",
    "Cleveland": "Cleveland Cavaliers",
    "Dallas": "Dallas Mavericks",
    "Denver": "Denver Nuggets",
    "Detroit": "Detroit Pistons",
    "Golden State": "Golden State Warriors",
    "Houston": "Houston Rockets",
    "Indiana": "Indiana Pacers",
    "LA Clippers": "LA Clippers",
    "L.A. Lakers": "Los Angeles Lakers",
    "Memphis": "Memphis Grizzlies",
    "Miami": "Miami Heat",
    "Milwaukee": "Milwaukee Bucks",
    "Minnesota": "Minnesota Timberwolves",
    "New Orleans": "New Orleans Pelicans",
    "New York": "New York Knicks",
    "Oklahoma City": "Oklahoma City Thunder",
    "Orlando": "Orlando Magic",
    "Philadelphia": "Philadelphia 76ers",
    "Phoenix": "Phoenix Suns",
    "Portland": "Portland Trail Blazers",
    "Sacramento": "Sacramento Kings",
    "San Antonio": "San Antonio Spurs",
    "Toronto": "Toronto Raptors",
    "Utah": "Utah Jazz",
    "Washington": "Washington Wizards",
}

NBA_TEAM_TIMEZONES = {
    "Atlanta Hawks": "America/New_York",
    "Boston Celtics": "America/New_York",
    "Brooklyn Nets": "America/New_York",
    "Charlotte Hornets": "America/New_York",
    "Chicago Bulls": "America/Chicago",
    "Cleveland Cavaliers": "America/New_York",
    "Dallas Mavericks": "America/Chicago",
    "Denver Nuggets": "America/Denver",
    "Detroit Pistons": "America/New_York",
    "Golden State Warriors": "America/Los_Angeles",
    "Houston Rockets": "America/Chicago",
    "Indiana Pacers": "America/Indiana/Indianapolis",
    "LA Clippers": "America/Los_Angeles",
    "Los Angeles Lakers": "America/Los_Angeles",
    "Memphis Grizzlies": "America/Chicago",
    "Miami Heat": "America/New_York",
    "Milwaukee Bucks": "America/Chicago",
    "Minnesota Timberwolves": "America/Chicago",
    "New Orleans Pelicans": "America/Chicago",
    "New York Knicks": "America/New_York",
    "Oklahoma City Thunder": "America/Chicago",
    "Orlando Magic": "America/New_York",
    "Philadelphia 76ers": "America/New_York",
    "Phoenix Suns": "America/Phoenix",
    "Portland Trail Blazers": "America/Los_Angeles",
    "Sacramento Kings": "America/Los_Angeles",
    "San Antonio Spurs": "America/Chicago",
    "Toronto Raptors": "America/Toronto",
    "Utah Jazz": "America/Denver",
    "Washington Wizards": "America/New_York",
}

DAY_PREFIX_RE = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.")
PDF_LINE_RE = re.compile(
    r"^(?P<dow>\w+\.) (?P<date>\d{1,2}/\d{1,2}/\d{2}) (?P<matchup>.+?) "
    r"(?P<local>\d{1,2}(?::\d{2})? [AP]M) (?P<et>\d{1,2}(?::\d{2})? [AP]M)(?: (?P<extra>.*))?$"
)

NBA_EXHIBITION_LABELS = {
    "All-Star",
    "All-Star Championship",
    "Rising Stars Semifinal",
    "Rising Stars Final",
}

NBA_POSTSEASON_KEYWORDS = (
    "Play-In Tournament",
    "First Round",
    "Conference Semifinal",
    "Conference Finals",
    "Conference Final",
    "Second Round",
    "NBA Finals",
)


def _season_label(season: int) -> str:
    return f"{season - 1}-{season}"


def _article_url(season: int) -> str:
    start_year = season - 1
    end_suffix = str(season)[-2:]
    return f"https://pr.nba.com/{start_year}-{end_suffix}-nba-regular-season-schedule/"


def _json_candidate_urls(season: int) -> list[str]:
    start_year = season - 1
    return [
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
        f"https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{start_year}/league/00_full_schedule.json",
    ]


def _full_team_name(team_payload: dict) -> str:
    city = team_payload.get("teamCity") or team_payload.get("city") or ""
    name = team_payload.get("teamName") or team_payload.get("name") or team_payload.get("nickname") or ""
    combined = f"{city} {name}".strip()
    return combined or str(team_payload.get("teamTricode") or "").strip()


def _parse_nba_utc(game: dict) -> datetime | None:
    for key in ("gameDateTimeUTC", "gameDateUTC", "gameTimeUTC", "gameDateEst", "gameEt"):
        raw_value = game.get(key)
        if not raw_value:
            continue
        try:
            parsed = parse_iso_datetime(raw_value)
        except ValueError:
            continue
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            if key in {"gameDateEst", "gameEt"}:
                parsed = parsed.replace(tzinfo=get_zoneinfo(EASTERN_NAME)).astimezone(UTC)
            else:
                parsed = parsed.replace(tzinfo=UTC)
        return parsed
    return None


def _normalize_status(game: dict) -> str:
    status_code = game.get("gameStatus")
    if status_code == 1:
        return "scheduled"
    if status_code == 2:
        return "live"
    if status_code == 3:
        return "final"

    raw_text = str(game.get("gameStatusText") or "").strip().lower()
    if raw_text.startswith("final"):
        return "final"
    if raw_text:
        return raw_text.replace(" ", "_")
    return "scheduled"


def _competition_phase(label: str | None, sublabel: str | None) -> str:
    normalized_label = str(label or "").strip()
    normalized_sublabel = str(sublabel or "").strip()

    if normalized_label == "Preseason":
        return "preseason"
    if normalized_label in NBA_EXHIBITION_LABELS:
        return "exhibition"
    if normalized_label == "Emirates NBA Cup":
        if "Semifinal" in normalized_sublabel or normalized_sublabel == "Championship":
            return "special"
        return "regular_season"
    if any(keyword in normalized_label for keyword in NBA_POSTSEASON_KEYWORDS):
        return "postseason"
    return "regular_season"


def _subtitle_and_stage(label: str | None, sublabel: str | None, competition_phase: str) -> tuple[str, str]:
    normalized_label = str(label or "").strip()
    normalized_sublabel = str(sublabel or "").strip()

    if competition_phase == "regular_season":
        if normalized_label == "Emirates NBA Cup":
            return "Emirates NBA Cup", normalized_sublabel or "NBA Cup"
        if normalized_label and normalized_label not in {"Preseason"}:
            return normalized_label, "Regular Season"
        return "NBA Regular Season", "Regular Season"

    if competition_phase == "preseason":
        return "NBA Preseason", "Preseason"

    if competition_phase == "postseason":
        if normalized_label == "SoFi Play-In Tournament":
            return "NBA Postseason", "Play-In Tournament"
        return "NBA Postseason", normalized_label or "Postseason"

    if competition_phase == "special":
        return "Emirates NBA Cup", normalized_sublabel or normalized_label or "Special Event"

    if competition_phase == "exhibition":
        return normalized_label or "NBA Exhibition", normalized_label or normalized_sublabel or "Exhibition"

    return "NBA Special Event", normalized_label or normalized_sublabel or "Special Event"


def _event_tags(label: str | None, competition_phase: str) -> list[str]:
    normalized_label = str(label or "").strip()
    tags = ["nba", "game", competition_phase.replace("_", "-")]
    if normalized_label == "Emirates NBA Cup":
        tags.append("nba-cup")
    if normalized_label == "AWS NBA Rivals Week":
        tags.append("rivals-week")
    if normalized_label.startswith("NBA ") and normalized_label.endswith(" Game"):
        tags.append("special-site")
    if normalized_label == "NBA Pioneers Classic":
        tags.append("special-site")
    return tags


class NBAProvider(Provider):
    key = "nba"
    league = "NBA"
    sport = "basketball"

    def season_label(self, season: int) -> str:
        return _season_label(season)

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        warnings: list[str] = []

        for url in _json_candidate_urls(season):
            try:
                payload = fetch_json(url, settings)
                events, metadata = self._parse_json_payload(payload, season, options)
                if metadata.get("regular_season_team_game_count_anomalies"):
                    warnings.append(
                        "NBA official schedule JSON currently exposes 1228 regular-season games; four NBA Cup semifinalist teams appear in only 81 regular-season games."
                    )
                if events:
                    return ProviderRunResult(
                        provider_key=self.key,
                        season=season,
                        events=events,
                        warnings=warnings,
                        raw_artifacts=[
                            RawArtifact(
                                relative_path="schedule.json",
                                content=json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8"),
                            )
                        ],
                        metadata={
                            "url": url,
                            "source_format": "json",
                            "semantics": {
                                "default_behavior": "Regular-season NBA games only.",
                                "special_handling": [
                                    "Preseason, All-Star weekend, NBA Cup semifinals/championship, and other special events are excluded by default.",
                                    "NBA Cup group play and quarterfinals remain included because they count toward the regular season.",
                                    "The current official feed exposes 1228 regular-season games; four NBA Cup semifinalist teams appear in 81 regular-season games instead of 82.",
                                    "Malformed placeholder playoff records without participants are dropped.",
                                ],
                                "dedupe_rule": "gameId",
                            },
                            **metadata,
                        },
                    )
            except FetchError as exc:
                warnings.append(str(exc))
            except Exception as exc:  # pragma: no cover
                warnings.append(f"failed to parse NBA JSON source {url}: {exc}")

        pdf_result = self._fetch_pdf_fallback(season, settings, options)
        pdf_result.warnings = warnings + pdf_result.warnings
        return pdf_result

    def _parse_json_payload(
        self, payload: dict, season: int, options: ProviderOptions
    ) -> tuple[list[CalendarEvent], dict[str, object]]:
        accumulator = EventAccumulator(options)
        label_counts: Counter[str] = Counter()
        status_counts: Counter[str] = Counter()
        regular_team_counts: Counter[str] = Counter()
        if isinstance(payload, dict) and "leagueSchedule" in payload:
            for game_date in payload.get("leagueSchedule", {}).get("gameDates", []):
                for game in game_date.get("games", []):
                    label = str(game.get("gameLabel") or "").strip() or "<none>"
                    label_counts[label] += 1
                    status_counts[_normalize_status(game)] += 1
                    event = self._event_from_json_game(game, season, game_date.get("gameDate"))
                    if event:
                        if event.competition_phase == "regular_season":
                            for participant in event.participants:
                                if participant.name:
                                    regular_team_counts[participant.name] += 1
                        accumulator.add(
                            event, dedupe_key=str(game.get("gameId") or game.get("gameCode") or event.event_id)
                        )
        anomalies = {team: count for team, count in sorted(regular_team_counts.items()) if count != 82}
        return accumulator.events(), {
            "source_label_counts": dict(label_counts),
            "source_status_counts": dict(status_counts),
            "regular_season_team_game_count_anomalies": anomalies,
            **accumulator.metadata(),
        }

    def _event_from_json_game(self, game: dict, season: int, fallback_date: str | None) -> CalendarEvent | None:
        away_team = game.get("awayTeam", {}) or {}
        home_team = game.get("homeTeam", {}) or {}
        away_name = _full_team_name(away_team)
        home_name = _full_team_name(home_team)
        competition_phase = _competition_phase(game.get("gameLabel"), game.get("gameSubLabel"))
        subtitle, round_or_stage = _subtitle_and_stage(
            game.get("gameLabel"),
            game.get("gameSubLabel"),
            competition_phase,
        )
        utc_dt = _parse_nba_utc(game)
        timezone_name = game.get("arenaTimezone") or NBA_TEAM_TIMEZONES.get(home_name)
        local_dt = utc_to_timezone(utc_dt, timezone_name)

        away = Participant(
            name=away_name, participant_id=away_team.get("teamId") or away_team.get("teamTricode"), role="away"
        )
        home = Participant(
            name=home_name, participant_id=home_team.get("teamId") or home_team.get("teamTricode"), role="home"
        )

        return CalendarEvent(
            event_id=stable_event_id(self.key, season, game.get("gameId") or game.get("gameCode")),
            source="nba_official_schedule_json",
            sport=self.sport,
            league=self.league,
            season=self.season_label(season),
            event_type="game",
            title=f"{away_name} at {home_name}",
            subtitle=subtitle,
            start_time_utc=isoformat_z(utc_dt),
            start_time_local=isoformat_local(local_dt),
            timezone=timezone_name,
            status=_normalize_status(game),
            venue=game.get("arenaName"),
            city=game.get("arenaCity"),
            region=game.get("arenaState") or game.get("arenaStateAbbr"),
            country=game.get("arenaCountry"),
            participants=[away, home],
            home_participant=home,
            away_participant=away,
            round_or_stage=round_or_stage,
            week_label=None,
            calendar_date=(local_dt.date().isoformat() if local_dt else fallback_date),
            end_calendar_date=(local_dt.date().isoformat() if local_dt else fallback_date),
            tags=_event_tags(game.get("gameLabel"), competition_phase),
            raw_source_payload=game,
            **classification_fields(competition_phase),
        )

    def _fetch_pdf_fallback(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        article_html = fetch_text(_article_url(season), settings)
        pdf_match = re.search(r'href="([^"]+)"[^>]*>[^<]*SCHEDULE BY DAY', article_html, flags=re.IGNORECASE)
        if not pdf_match:
            return ProviderRunResult(
                provider_key=self.key,
                season=season,
                events=[],
                warnings=["NBA JSON sources failed and the official PDF fallback link was not found."],
                metadata={"source_format": "none"},
            )

        pdf_url = pdf_match.group(1)
        pdf_bytes = fetch_bytes(pdf_url, settings)
        lines = extract_pdf_lines(pdf_bytes)
        events = self._parse_pdf_lines(lines, season)
        warnings = [
            "NBA fallback used the official schedule-release PDF; late schedule adjustments may require a fresher JSON source."
        ]
        if options.event_scope != "regular_only" or options.include_special_events:
            warnings.append(
                "NBA PDF fallback only models the published regular-season schedule; special events and postseason records remain unavailable in this mode."
            )
        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=events,
            raw_artifacts=[
                RawArtifact(relative_path="schedule_release.html", content=article_html.encode("utf-8")),
                RawArtifact(relative_path="schedule_by_day.pdf", content=pdf_bytes, is_binary=True),
            ],
            warnings=warnings,
            metadata={
                "url": pdf_url,
                "source_format": "pdf",
                "semantics": {
                    "default_behavior": "Regular-season NBA games only.",
                    "special_handling": [
                        "This fallback source does not expose preseason, All-Star, NBA Cup, or postseason records.",
                    ],
                    "dedupe_rule": "date + away + home",
                },
            },
        )

    def _parse_pdf_lines(self, lines: list[str], season: int) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for line in lines:
            if not DAY_PREFIX_RE.match(line):
                continue
            match = PDF_LINE_RE.match(line)
            if not match:
                continue

            matchup = match.group("matchup")
            delimiter = " at " if " at " in matchup else " vs " if " vs " in matchup else None
            if delimiter is None:
                continue

            away_label, home_label = matchup.split(delimiter, 1)
            away_name = NBA_PDF_TEAM_MAP.get(away_label.strip(), away_label.strip())
            home_name = NBA_PDF_TEAM_MAP.get(home_label.strip(), home_label.strip())
            game_day = datetime.strptime(match.group("date"), "%m/%d/%y").date()
            utc_dt = eastern_to_utc(game_day, match.group("et"))

            timezone_name = None
            local_dt = None
            if delimiter == " at ":
                timezone_name = NBA_TEAM_TIMEZONES.get(home_name)
                if timezone_name:
                    local_dt = localize_date_time(game_day, match.group("local"), timezone_name)

            away = Participant(name=away_name, participant_id=away_name, role="away")
            home = Participant(name=home_name, participant_id=home_name, role="home")

            extra = match.group("extra") or ""
            tags = ["nba", "game", "regular-season"]
            if delimiter == " vs ":
                tags.append("neutral-site")
            if " C" in f" {extra} ":
                tags.append("cup-night")

            events.append(
                CalendarEvent(
                    event_id=stable_event_id(self.key, season, match.group("date"), away_name, home_name),
                    source="nba_schedule_release_pdf",
                    sport=self.sport,
                    league=self.league,
                    season=self.season_label(season),
                    event_type="game",
                    title=f"{away_name} at {home_name}",
                    subtitle="NBA Regular Season",
                    start_time_utc=isoformat_z(utc_dt),
                    start_time_local=isoformat_local(local_dt),
                    timezone=timezone_name,
                    status="scheduled",
                    venue=None,
                    city=None,
                    region=None,
                    country=None,
                    participants=[away, home],
                    home_participant=home,
                    away_participant=away,
                    round_or_stage="Regular Season",
                    week_label=None,
                    calendar_date=(local_dt.date().isoformat() if local_dt else game_day.isoformat()),
                    end_calendar_date=(local_dt.date().isoformat() if local_dt else game_day.isoformat()),
                    tags=tags,
                    raw_source_payload={"line": line, "extra": extra},
                    **classification_fields("regular_season"),
                )
            )
        return events
