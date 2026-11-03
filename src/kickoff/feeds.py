"""Scheduled league feeds: official league APIs and ESPN's public site JSON.

Approved by the owner on October 1, 2026 for factual schedule data (dates, times,
participants, venues). These sources grant no data license; the calendar names
them, links back, and includes only supplied team facts and confirmed final scores,
never odds or article content.
"""

from __future__ import annotations

import json
import re
import time
import warnings
from calendar import monthrange
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from functools import cache
from importlib.resources import files
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from kickoff.countries import COUNTRY_LEAGUES, venue_country
from kickoff.http import read_bounded_response
from kickoff.models import CalendarEvent, Participant
from kickoff.semantics import classification_fields
from kickoff.textutils import espn_logo_url

USER_AGENT = "kickoff-refresh/0.3 (https://github.com/snowball-projects/kickoff)"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
EASTERN = ZoneInfo("America/New_York")
CENTRAL_EUROPE = ZoneInfo("Europe/Paris")
# Golf scoreboards embed full leaderboards; gzip keeps the transfer to a few MB.
MAX_BYTES = 80_000_000
DROPPED_STATUSES = {"STATUS_CANCELED", "STATUS_POSTPONED", "STATUS_SUSPENDED", "STATUS_FORFEIT"}
# Exact ESPN titles checked 2026-10-30 against the PGA/LPGA season feeds.
# LPGA majors: https://www.lpga.com/news/2026/nelly-korda-wins-2026-rolex-annika-major-award
# An unrelated tournament named Open must never become a major.
GOLF_MAJORS = {
    "PGA_TOUR": {"Masters Tournament", "PGA Championship", "U.S. Open", "The Open"},
    "LPGA_TOUR": {
        "The Chevron Championship",
        "U.S. Women's Open pres. by Ally",
        "U.S. Women's Open",
        "KPMG Women's PGA Championship",
        "The Amundi Evian Championship",
        "AIG Women's Open",
    },
}
# ESPN's current top-level rugby union competitions. Sevens, lower divisions
# and discontinued replacement competitions are separate calendars.
# https://sports.core.api.espn.com/v2/sports/rugby/leagues?limit=1000
# https://site.api.espn.com/apis/site/v2/leagues/dropdown?sport=rugby
# Checked 2026-10-31; an unpublished season remains an empty source schedule.
RUGBY_LEAGUES = {
    "RUGBY_WORLD_CUP": ("164205", "Rugby World Cup"),
    "WOMENS_RUGBY_WORLD_CUP": ("289237", "Women's Rugby World Cup"),
    "SIX_NATIONS": ("180659", "Six Nations"),
    "RUGBY_CHAMPIONSHIP": ("244293", "The Rugby Championship"),
    "NATIONS_CHAMPIONSHIP": ("17567", "Nations Championship"),
    "RUGBY_CHAMPIONS_CUP": ("271937", "European Rugby Champions Cup"),
    "RUGBY_CHALLENGE_CUP": ("272073", "European Rugby Challenge Cup"),
    "PREMIERSHIP_RUGBY": ("267979", "Gallagher Prem"),
    "UNITED_RUGBY_CHAMPIONSHIP": ("270557", "United Rugby Championship"),
    "TOP_14": ("270559", "French Top 14"),
    "SUPER_RUGBY_PACIFIC": ("242041", "Super Rugby Pacific"),
    "CURRIE_CUP": ("270555", "Currie Cup"),
    "NPC": ("270563", "National Provincial Championship"),
    "URBA_TOP_14": ("289279", "URBA Top 14"),
    "MAJOR_LEAGUE_RUGBY": ("289262", "Major League Rugby"),
    "BRITISH_IRISH_LIONS": ("268565", "British and Irish Lions Tour"),
    "RUGBY_TESTS": ("289234", "International Test Match"),
}

SOURCES = {
    "espn": {
        "name": "ESPN",
        "url": "https://www.espn.com/",
        "license": "No license granted; factual schedule information with attribution",
        "license_url": "https://disneytermsofuse.com/",
    },
    "mlb": {
        "name": "MLB Stats API",
        "url": "https://statsapi.mlb.com/",
        "license": "No license granted; factual schedule information with attribution",
        "license_url": "http://gdx.mlb.com/components/copyright.txt",
    },
    "nhl": {
        "name": "NHL",
        "url": "https://www.nhl.com/schedule",
        "license": "No license granted; factual schedule information with attribution",
        "license_url": "https://www.nhl.com/info/terms-of-service",
    },
}


def get_json(url: str, *, retries: int = 3, missing_ok: bool = False) -> dict | list | None:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Encoding": "gzip"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=60) as response:
                data = read_bounded_response(response, max_bytes=MAX_BYTES)
            return json.loads(data)
        except HTTPError as error:
            if missing_ok and error.code in {400, 404}:
                return None
            if error.code < 500 or attempt == retries - 1:
                raise
        except (TimeoutError, OSError):
            if attempt == retries - 1:
                raise
        time.sleep(2**attempt)
    return None


def rows(payload: dict, key: str) -> list:
    """Missing collections are malformed, never a successful empty schedule."""
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError(f"Missing or invalid {key} collection")
    return payload[key]


def _local_date(utc: str, zone: ZoneInfo) -> str:
    return datetime.fromisoformat(_iso_utc(utc).replace("Z", "+00:00")).astimezone(zone).date().isoformat()


def _iso_utc(value: str) -> str:
    """Convert an explicit source offset to UTC, retaining seconds precision."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Source timestamp must include a timezone offset")
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_event(
    *,
    source: str,
    league: str,
    sport: str,
    upstream_id: str | int,
    season: str,
    title: str,
    utc: str | None,
    day: str,
    end_day: str | None = None,
    home: str | None = None,
    away: str | None = None,
    event_type: str = "game",
    phase: str = "regular_season",
    venue: str | None = None,
    subtitle: str | None = None,
    source_url: str | None = None,
    country: str | None = None,
    country_source_url: str | None = None,
    country_checked_date: str | None = None,
    status: str = "scheduled",
    facts_source_url: str | None = None,
    round_or_stage: str | None = None,
    week_label: str | None = None,
) -> CalendarEvent:
    home_participant = Participant(name=home, role="home") if home else None
    away_participant = Participant(name=away, role="away") if away else None
    return CalendarEvent(
        event_id=f"{source}-{league.lower()}-{upstream_id}",
        source=source,
        sport=sport,
        league=league,
        season=season,
        event_type=event_type,
        title=title,
        subtitle=subtitle,
        start_time_utc=_iso_utc(utc) if utc else None,
        start_time_local=None,
        timezone="UTC" if utc else None,
        status=status,
        facts_checked_date=datetime.now(UTC).date().isoformat() if facts_source_url else None,
        facts_source_url=facts_source_url,
        round_or_stage=round_or_stage,
        week_label=week_label,
        venue=venue,
        city=None,
        region=None,
        country=country,
        country_source_url=country_source_url,
        country_checked_date=country_checked_date,
        participants=[p for p in (home_participant, away_participant) if p],
        home_participant=home_participant,
        away_participant=away_participant,
        calendar_date=day,
        end_calendar_date=end_day or day,
        source_url=source_url,
        tags=[league.lower(), event_type],
        **classification_fields(phase),
    )


# --- ESPN -------------------------------------------------------------------


def _espn_link(event: dict, fallback: str) -> str:
    for link in event.get("links") or []:
        href = link.get("href", "")
        if href.startswith("https://www.espn.com/"):
            return href
    return fallback


def _score(value) -> int | None:
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    if isinstance(value, str) and re.fullmatch(r"\d+", value):
        return int(value)
    if type(value) in (int, float) and value >= 0 and float(value).is_integer():
        return int(value)
    return None


def _record(value) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"\d+(?:-\d+){1,2}", value) else None


def _espn_record(competitor: dict, sport: str) -> str | None:
    # Soccer total summaries are W-D-L (confirmed against named standings
    # wins/ties/losses). NHL labels its overall season record YTD; home,
    # road and tournament-group splits never stand in for an overall record.
    for kind in ("total", "ytd") if sport == "hockey" else ("total",):
        for record in competitor.get("records") or []:
            if record.get("type") == kind and (summary := _record(record.get("summary"))):
                return summary
    return None


def _espn_finished(event: dict, competition: dict) -> bool:
    return any(
        (item.get("status") or {}).get("type", {}).get("completed") is True
        or (item.get("status") or {}).get("type", {}).get("name") in {"STATUS_FINAL", "STATUS_FULL_TIME"}
        for item in (event, competition)
    )


@cache
def _espn_national_teams() -> dict[str, dict]:
    """Reviewed national identities; scoreboard names and logos prove no nationality."""
    return json.loads(files("kickoff").joinpath("config/espn-national-teams.json").read_text())["teams"]


def espn_national_sources(events: list[CalendarEvent]) -> list[dict]:
    kinds = {p.metadata.get("country_source_kind") for event in events for p in event.participants}
    sources = json.loads(files("kickoff").joinpath("config/espn-national-teams.json").read_text()).get("sources", [])
    return [source for source in sources if source["kind"] in kinds]


def _espn_participants(event: CalendarEvent, competitors: list, finished: bool) -> None:
    for participant in event.participants:
        row = next((c for c in competitors if c.get("homeAway") == participant.role), {})
        team = row.get("team") or {}
        participant.participant_id = str(team["id"]) if team.get("id") is not None else None
        participant.short_name = team.get("shortDisplayName") or team.get("abbreviation")
        participant.record = _espn_record(row, event.sport)
        participant.final_score = _score(row.get("score")) if finished else None
        if event.league in ADDITIONAL_TEAM_LEAGUES and (logo := espn_logo_url(team.get("logo"))):
            participant.metadata.update(
                logo_url=logo,
                logo_source_url=event.facts_source_url,
                logo_checked_date=event.facts_checked_date,
            )
        national = _espn_national_teams().get(f"{event.sport}/{participant.participant_id}")
        if national:
            participant.entity_type = "national_team"
            participant.metadata.update(
                country_code=national["country_code"],
                country_source_url=national["source_url"],
                country_checked_date=national["checked_date"],
                country_source_kind=national.get("source_kind", "espn"),
            )


def _espn_event(
    event: dict,
    *,
    league: str,
    sport: str,
    zone: ZoneInfo,
    fallback_url: str,
    event_type: str = "game",
    phase: str = "regular_season",
    span: bool = False,
    input_url: str | None = None,
) -> CalendarEvent | None:
    competition = (event.get("competitions") or [{}])[0]
    # Scoreboards expose event.status; team schedules use competition.status.
    # If the feed disagrees with itself, withholding is safer than an old appointment.
    statuses = [((item.get("status") or {}).get("type") or {}).get("name", "") for item in (event, competition)]
    if any(status in DROPPED_STATUSES or status.startswith("STATUS_CANCEL") for status in statuses):
        return None
    timed = bool(competition.get("timeValid", True)) and not span
    home = away = None
    competitors = competition.get("competitors") or []
    if event_type == "game" and len(competitors) == 2:
        for competitor in competitors:
            name = (competitor.get("team") or {}).get("displayName")
            if competitor.get("homeAway") == "home":
                home = name
            elif competitor.get("homeAway") == "away":
                away = name
    end_day = _local_date(event["endDate"], zone) if span and event.get("endDate") else None
    season = event.get("season") or {}
    venue = competition.get("venue") or {}
    country = venue_country((venue.get("address") or {}).get("country")) if league in COUNTRY_LEAGUES else None
    finished = _espn_finished(event, competition if event_type == "game" else {})
    week = event.get("week") or {}
    week_label = week.get("text") or (f"Week {week['number']}" if type(week.get("number")) is int else None)
    # Match labels are used only when the feed explicitly supplies them.
    round_label = week_label
    if not round_label and league == "UEFA_CHAMPIONS_LEAGUE" and season.get("slug"):
        round_label = season["slug"].replace("-", " ").capitalize()
    result = make_event(
        source="espn",
        league=league,
        sport=sport,
        upstream_id=event["id"],
        season=str(season.get("year", "")) or _local_date(event["date"], zone)[:4],
        title=event.get("name") or event.get("shortName") or "Event",
        utc=event["date"] if timed else None,
        day=_local_date(event["date"], zone),
        end_day=end_day,
        home=home,
        away=away,
        event_type=event_type,
        phase=phase,
        venue=venue.get("fullName"),
        source_url=_espn_link(event, fallback_url),
        country=country,
        country_source_url=(input_url or _espn_link(event, fallback_url)) if country else None,
        country_checked_date=datetime.now(UTC).date().isoformat() if country else None,
        status="finished" if finished else "scheduled",
        facts_source_url=input_url or _espn_link(event, fallback_url),
        round_or_stage=round_label,
        week_label=week_label,
    )
    _espn_participants(result, competitors, finished)
    return result


def _in_year(events: list[CalendarEvent], year: int) -> list[CalendarEvent]:
    prefix = str(year)
    return [
        e
        for e in events
        if (e.calendar_date or "").startswith(prefix) or (e.end_calendar_date or "").startswith(prefix)
    ]


def _dedupe(events: list[CalendarEvent]) -> list[CalendarEvent]:
    return list({event.event_id: event for event in events}.values())


def _espn_appointment(event: CalendarEvent, label: str | None) -> None:
    unknown = {p.role for p in event.participants if p.name.strip().upper() in {"TBD", "TBA"}}
    if not unknown:
        return
    # A published bowl/bracket appointment is not a named matchup.
    if not label:
        raise ValueError(f"Missing published label for undecided ESPN appointment: {event.event_id}")
    event.participants = [p for p in event.participants if p.role not in unknown]
    names = [p.name for p in event.participants if p.name.casefold() not in label.casefold()]
    event.title = " · ".join([label, *names])
    if event.subtitle == label:
        event.subtitle = None
    if "home" in unknown:
        event.home_participant = None
    if "away" in unknown:
        event.away_participant = None


@cache
def _phase_overrides() -> dict[str, dict]:
    """Reviewed event identities, never inferred postseason dates for future years."""
    payload = json.loads(files("kickoff").joinpath("config/feed-phases.json").read_text())
    return {row["event_id"]: row for row in payload["events"]}


def espn_calendar_phase(league: str, event_id: str | int, season: str, name: str) -> str:
    """Retain reviewed playoff identity where ESPN reports generic regular-season."""
    if name in GOLF_MAJORS.get(league, set()):
        return "championship"
    if league == "NASCAR_CUP" and re.search(r"\b(?:clash|duel|all[\s-]*star)\b", name, re.IGNORECASE):
        return "exhibition"
    override = _phase_overrides().get(f"espn-{league.lower()}-{event_id}")
    if override and override["league"] == league and override["season"] == season:
        return override["competition_phase"]
    return "regular_season"


def espn_season_feed(
    path: str, league: str, sport: str, event_type: str, fallback_url: str, *, span=False, zone=EASTERN
):
    """Annual scoreboards expose tournaments or games as top-level events."""

    def fetch(year: int) -> list[CalendarEvent]:
        url = f"{ESPN}/{path}/scoreboard?dates={year}&limit=500"
        payload = get_json(url)
        events = []
        for row in rows(payload, "events"):
            # LPGA and Major League Rugby include empty calendar placeholders.
            if row == {}:
                continue
            name = row.get("name", "")
            season = str((row.get("season") or {}).get("year") or _local_date(row["date"], zone)[:4])
            phase = "championship" if row.get("major") is True else espn_calendar_phase(league, row["id"], season, name)
            event = _espn_event(
                row,
                league=league,
                sport=sport,
                zone=zone,
                fallback_url=fallback_url,
                event_type=event_type,
                phase=phase,
                span=span,
                input_url=url,
            )
            if event:
                if sport == "rugby":
                    competition = (row.get("competitions") or [{}])[0]
                    label = (
                        " · ".join(
                            note["headline"]
                            for note in competition.get("notes") or []
                            if note.get("type") == "event" and note.get("headline")
                        )
                        or event.round_or_stage
                    )
                    if label:
                        event.round_or_stage = label
                    # A dated source fixture remains an appointment even when
                    # ESPN has not named either opponent. The catalog supplies
                    # its competition identity; never turn TBD/TBA into a team.
                    _espn_appointment(event, label or RUGBY_LEAGUES[league][1])
                events.append(event)
        return _in_year(_dedupe(events), year)

    return fetch


def nfl_events(year: int) -> list[CalendarEvent]:
    """Weekly scoreboards for the season ending early in `year` and the one starting in it."""
    events = []
    weeks = [(year - 1, 2, week) for week in (17, 18)] + [(year - 1, 3, week) for week in range(1, 6)]
    weeks += [(year, 2, week) for week in range(1, 19)] + [(year, 3, week) for week in range(1, 6)]
    for season, season_type, week in weeks:
        payload = get_json(
            f"{ESPN}/football/nfl/scoreboard?dates={season}&seasontype={season_type}&week={week}", missing_ok=True
        )
        for row in rows(payload, "events") if payload is not None else []:
            name = row.get("name", "")
            if "Pro Bowl" in name:
                phase = "exhibition"
            elif season_type == 3:
                phase = "final" if week == 5 else "postseason"
            else:
                phase = "regular_season"
            event = _espn_event(
                row,
                league="NFL",
                sport="football",
                zone=EASTERN,
                fallback_url="https://www.nfl.com/schedules/",
                phase=phase,
            )
            if event:
                competition = (row.get("competitions") or [{}])[0]
                label = " · ".join(
                    note["headline"]
                    for note in competition.get("notes") or []
                    if note.get("type") == "event" and note.get("headline")
                )
                _espn_appointment(event, label)
                events.append(event)
    return _in_year(_dedupe(events), year)


def nba_events(year: int) -> list[CalendarEvent]:
    """Per-team season schedules; ESPN rejects league-wide date ranges."""
    teams = get_json(f"{ESPN}/basketball/nba/teams")["sports"][0]["leagues"][0]["teams"]
    team_ids = [team["team"]["id"] for team in teams]
    if len(team_ids) < 30:
        raise ValueError(f"Expected 30 NBA teams, got {len(team_ids)}")
    events = []
    records = {}
    for team_id in team_ids:
        for season, season_type in ((year, 2), (year, 3), (year + 1, 2)):
            url = f"{ESPN}/basketball/nba/teams/{team_id}/schedule?season={season}&seasontype={season_type}"
            payload = get_json(url, missing_ok=True)
            record = _record((payload or {}).get("team", {}).get("recordSummary"))
            for row in rows(payload, "events") if payload is not None else []:
                event = _espn_event(
                    row,
                    league="NBA",
                    sport="basketball",
                    zone=EASTERN,
                    fallback_url="https://www.nba.com/schedule",
                    phase="postseason" if season_type == 3 else "regular_season",
                    input_url=url,
                )
                if event:
                    events.append(event)
                    if record and str((payload.get("team") or {}).get("id")) == str(team_id):
                        records[(event.event_id, str(team_id))] = (record, url)
    result = _in_year(_dedupe(events), year)
    for event in result:
        for participant in event.participants:
            if not participant.record and (event.event_id, participant.participant_id) in records:
                participant.record, participant.team_source_url = records[(event.event_id, participant.participant_id)]
    return result


TEAM_LEAGUES = {
    "UEFA_EUROPA_LEAGUE": ("soccer/uefa.europa", "soccer", (None,), 1000),
    "UEFA_CONFERENCE_LEAGUE": ("soccer/uefa.europa.conf", "soccer", (None,), 1000),
    "UEFA_NATIONS_LEAGUE": ("soccer/uefa.nations", "soccer", (None,), 1000),
    "MLS": ("soccer/usa.1", "soccer", (None,), 1000),
    "WNBA": ("basketball/wnba", "basketball", (None,), 1000),
    "NCAA_MENS_BASKETBALL": ("basketball/mens-college-basketball", "basketball", (50,), 1000),
    "NCAA_WOMENS_BASKETBALL": ("basketball/womens-college-basketball", "basketball", (50,), 1000),
    "COLLEGE_FOOTBALL": ("football/college-football", "football", (80, 81), 200),
}
# Checked against primary scoreboards 2026-11-02. CFL has no usable 2025–27
# events and is intentionally absent (see data/reviewed/receipts/espn-leagues-review.json).
ADDITIONAL_TEAM_LEAGUES = {
    "FA_CUP": ("soccer/eng.fa", "soccer", "Europe/London", "FA Cup"),
    "LEAGUE_CUP": ("soccer/eng.league_cup", "soccer", "Europe/London", "League Cup"),
    "LIGA_MX": ("soccer/mex.1", "soccer", "America/Mexico_City", "Liga MX"),
    "COPA_LIBERTADORES": ("soccer/conmebol.libertadores", "soccer", "America/Sao_Paulo", "Copa Libertadores"),
    "COPA_SUDAMERICANA": ("soccer/conmebol.sudamericana", "soccer", "America/Sao_Paulo", "Copa Sudamericana"),
    "NWSL": ("soccer/usa.nwsl", "soccer", "America/New_York", "NWSL"),
    "WSL": ("soccer/eng.w.1", "soccer", "Europe/London", "Women's Super League"),
    "UEFA_WOMENS_CHAMPIONS_LEAGUE": (
        "soccer/uefa.wchampions",
        "soccer",
        "Europe/Paris",
        "UEFA Women's Champions League",
    ),
    "G_LEAGUE": ("basketball/nba-development", "basketball", "America/New_York", "NBA G League"),
    "NBL": ("basketball/nbl", "basketball", "Australia/Sydney", "NBL"),
    "UFL": ("football/ufl", "football", "America/New_York", "UFL"),
}
TEAM_LEAGUES.update(
    {league: (path, sport, (None,), 1000) for league, (path, sport, _, _) in ADDITIONAL_TEAM_LEAGUES.items()}
)


SOCCER_TEAM_LEAGUES = {league for league, (_path, sport, *_rest) in TEAM_LEAGUES.items() if sport == "soccer"}


def espn_team_phase(row: dict, league: str) -> str:
    """Use source stages and tournament identity, including regular-type conference finals."""
    season = row.get("season") or {}
    slug = season.get("slug", "")
    if season.get("type") == 1 or slug == "preseason":
        return "preseason"
    competition = (row.get("competitions") or [{}])[0]
    kind = (competition.get("type") or {}).get("abbreviation")
    notes = " · ".join(note.get("headline", "") for note in competition.get("notes") or [])
    if kind in {"ALLSTAR", "EXH"} or (league == "MLS" and re.search(r"\ball[ -]stars?\b", row.get("name", ""), re.I)):
        return "exhibition"
    if kind == "CC":  # ESPN's explicit WNBA Commissioner's Cup championship type.
        return "championship"
    if league == "UFL" and kind == "Championship":
        return "final"
    if league in SOCCER_TEAM_LEAGUES:
        if slug == "all-star-game":
            return "exhibition"
        if league == "WSL" and re.fullmatch(r"\d{4}-\d{2}-english-womens-super-league", slug):
            return "regular_season"
        if league == "LIGA_MX" and slug in {"torneo-apertura", "torneo-clausura"}:
            return "regular_season"
        if slug in {"regular-season", "league-phase", "group-stage", "group-phase"}:
            return {"league-phase": "league_phase", "group-stage": "group_stage", "group-phase": "group_stage"}.get(
                slug, "regular_season"
            )
        if slug in {"final", "mls-cup", "playoffs---championship"} or (
            league == "LIGA_MX" and slug.endswith("---finals")
        ):
            return "final"
        if slug:
            return "knockout"
    conference_tournament = (
        league in {"NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL"}
        and competition.get("conferenceCompetition") is True
        and (competition.get("type") or {}).get("abbreviation") == "TRNMNT"
    )
    football_postseason = league == "COLLEGE_FOOTBALL" and re.search(r"\b(?:bowl|playoff|championship)\b", notes, re.I)
    if season.get("type") == 3 or slug in {"post-season", "postseason"} or conference_tournament or football_postseason:
        if re.search(r"\bnational championship\b|\bncaa championship.*\bfinal\b", notes, re.I):
            return "final"
        return "postseason"
    return "regular_season"


@cache
def _espn_team_logo(path: str, team_id: str, team_name: str) -> tuple[str, str] | None:
    """Optional source image for an identified team, without fetching team statistics."""
    url = f"{ESPN}/{path}/teams/{team_id}"
    try:
        payload = get_json(url, missing_ok=True)
    except (HTTPError, OSError, TimeoutError, ValueError) as error:
        warnings.warn(f"Optional ESPN team image unavailable: {url}: {error}", stacklevel=2)
        return None
    team = payload.get("team") if isinstance(payload, dict) else None
    if not isinstance(team, dict) or not isinstance(team.get("displayName"), str):
        return None
    if str(team.get("id")) != team_id or team["displayName"].casefold() != team_name.casefold():
        return None
    logos = team.get("logos")
    candidates = (
        [team.get("logo"), *(row.get("href") for row in logos if isinstance(row, dict))]
        if isinstance(logos, list)
        else [team.get("logo")]
    )
    return next(((logo, url) for candidate in candidates if (logo := espn_logo_url(candidate))), None)


def espn_team_events(year: int, league: str) -> list[CalendarEvent]:
    """Collect every published game, subdividing saturated year/month windows.

    Checked 2026-10-31 against ESPN's primary scoreboards: YYYY, YYYYMM and
    YYYYMMDD work; hyphenated date ranges return400. Football limit1000 silently
    falls back to25, while200 returns all grouped games. College monthly requests
    omit NCAA postseason even below the limit and ignore seasontype, so every
    civil day is fetched for college leagues, including the off-season.
    """
    path, sport, groups, limit = TEAM_LEAGUES[league]
    zone = (
        ZoneInfo(ADDITIONAL_TEAM_LEAGUES[league][2])
        if league in ADDITIONAL_TEAM_LEAGUES
        else CENTRAL_EUROPE
        if sport == "soccer" and league != "MLS"
        else EASTERN
    )

    def collect(prefix: str, group: int | None, season_type: str | None = None, week: str | None = None):
        url = f"{ESPN}/{path}/scoreboard?dates={prefix}&limit={limit}"
        if season_type is not None:
            url += f"&seasontype={season_type}&week={week}"
        if group is not None:
            url += f"&groups={group}"
        payload = get_json(url)
        selected = rows(payload, "events")
        supplements = []
        if league == "UFL" and len(prefix) == 4 and season_type is None:
            # ESPN's annual/monthly/daily/Core 2025 indexes omit four completed
            # games that remain in weekly scoreboards. Discover every published
            # week, including postseason; never guess a fixed season length.
            calendar = (payload.get("leagues") or [{}])[0].get("calendar")
            if calendar is None and not selected:
                calendar = []  # unpublished season: a valid empty events collection
            if not isinstance(calendar, list):
                raise ValueError(f"Missing UFL weekly calendar: {url}")
            if selected and not any(phase.get("entries") for phase in calendar):
                raise ValueError(f"Missing UFL weekly calendar entries: {url}")
            for phase in calendar:
                for entry in phase.get("entries") or []:
                    kind, number = str(phase.get("value", "")), str(entry.get("value", ""))
                    if not kind.isdigit() or not number.isdigit():
                        raise ValueError(f"Invalid UFL weekly calendar: {url}")
                    supplements.extend(collect(prefix, group, kind, number))
        if len(selected) >= limit:
            if season_type is not None:
                raise ValueError(f"ESPN weekly feed reached its limit; refusing to truncate: {url}")
            if len(prefix) == 4:
                children = [f"{prefix}{month:02}" for month in range(1, 13)]
            elif len(prefix) == 6:
                children = [
                    f"{prefix}{day:02}" for day in range(1, monthrange(int(prefix[:4]), int(prefix[4:]))[1] + 1)
                ]
            else:
                raise ValueError(f"ESPN daily feed reached its limit; refusing to truncate: {url}")
            return [event for child in children for event in collect(child, group)] + supplements
        result = []
        for row in selected:
            # ESPN's 2025-10-18 FCS scoreboard contains one empty calendar slot.
            if league == "COLLEGE_FOOTBALL" and row == {}:
                continue
            event = _espn_event(
                row,
                league=league,
                sport=sport,
                zone=zone,
                fallback_url=url,
                input_url=url,
                phase=espn_team_phase(row, league),
            )
            if event is None:
                continue
            competition = (row.get("competitions") or [{}])[0]
            if league in ADDITIONAL_TEAM_LEAGUES:
                address = (competition.get("venue") or {}).get("address") or {}
                event.city = address.get("city")
                event.region = address.get("state")
            notes = [
                note["headline"]
                for note in competition.get("notes") or []
                if note.get("type") == "event" and note.get("headline")
            ]
            if sport == "soccer" and (row.get("season") or {}).get("slug"):
                event.round_or_stage = (row["season"]["slug"]).replace("-", " ").capitalize()
                event.subtitle = " · ".join([event.round_or_stage, *notes])
            elif notes:
                event.subtitle = " · ".join(notes)
                # ESPN tournament notes use "Competition - Round". Retain the
                # complete note in details and the specific round in team rows.
                tournament = (competition.get("type") or {}).get("abbreviation") == "TRNMNT"
                rounds = [(note.partition(" - ")[2] or note) if tournament else note for note in notes]
                event.round_or_stage = " · ".join(rounds)
            appointment_label = event.subtitle or event.round_or_stage
            if not appointment_label and league in ADDITIONAL_TEAM_LEAGUES:
                appointment_label = ADDITIONAL_TEAM_LEAGUES[league][3]
            _espn_appointment(event, appointment_label)
            if group in (80, 81):
                event.tags.append("fbs" if group == 80 else "fcs")
            result.append(event)
        return result + supplements

    # Neighboring UTC dates can belong to this calendar year in the source zone.
    if league in {"NCAA_MENS_BASKETBALL", "NCAA_WOMENS_BASKETBALL", "COLLEGE_FOOTBALL"}:
        first, last = date(year - 1, 12, 31), date(year + 1, 1, 1)
        prefixes = [(first + timedelta(days=offset)).strftime("%Y%m%d") for offset in range((last - first).days + 1)]
    else:
        prefixes = [str(year), f"{year - 1}1231", f"{year + 1}0101"]
    if league == "UFL":
        prefixes.append(str(year - 1))
    queries = [(prefix, group) for group in groups for prefix in prefixes]
    with ThreadPoolExecutor(max_workers=4) as executor:
        collected = executor.map(lambda args: collect(*args), queries)
        events = {}
        for batch in collected:
            for event in batch:
                if event.event_id in events:
                    previous = events[event.event_id]
                    event.tags = sorted(set(previous.tags + event.tags))
                    if league == "UFL":
                        # Weekly indexes recover appointments but can omit logos
                        # and records present in the same game's annual row.
                        for participant in event.participants:
                            original = next(
                                (
                                    p
                                    for p in previous.participants
                                    if p.participant_id == participant.participant_id and p.role == participant.role
                                ),
                                None,
                            )
                            if original is not None:
                                participant.metadata = {**original.metadata, **participant.metadata}
                                participant.short_name = participant.short_name or original.short_name
                                if participant.record is None and original.record is not None:
                                    participant.record = original.record
                                    participant.team_source_url = original.team_source_url or previous.facts_source_url
                                if event.status == "finished" and participant.final_score is None:
                                    participant.final_score = original.final_score
                events[event.event_id] = event
    result = _in_year(list(events.values()), year)
    if league in ADDITIONAL_TEAM_LEAGUES:
        for event in result:
            for participant in event.participants:
                if not participant.metadata.get("logo_url") and participant.participant_id:
                    if supplied := _espn_team_logo(path, participant.participant_id, participant.name):
                        participant.metadata.update(
                            logo_url=supplied[0],
                            logo_source_url=supplied[1],
                            logo_checked_date=datetime.now(UTC).date().isoformat(),
                        )
    return result


UCL_PHASES = {"league-phase": "league_phase", "final": "final"}


def ucl_events(year: int) -> list[CalendarEvent]:
    """OpenLigaDB lists the match dates; ESPN supplies English names and kickoff times."""
    days = set()
    for season in (year - 1, year):
        matches = get_json(f"https://api.openligadb.de/getmatchdata/ucl/{season}", missing_ok=True)
        if matches is None:
            continue
        if not isinstance(matches, list):
            raise ValueError("Invalid OpenLigaDB match list")
        for match in matches:
            utc = match.get("matchDateTimeUTC")
            if utc and not utc.startswith("1970"):
                day = _local_date(utc, CENTRAL_EUROPE)
                if day.startswith(str(year)):
                    days.add(day)
    events = []
    for day in sorted(days):
        url = f"{ESPN}/soccer/uefa.champions/scoreboard?dates={day.replace('-', '')}"
        payload = get_json(url, missing_ok=True)
        for row in rows(payload, "events") if payload is not None else []:
            slug = (row.get("season") or {}).get("slug", "")
            event = _espn_event(
                row,
                league="UEFA_CHAMPIONS_LEAGUE",
                sport="soccer",
                zone=CENTRAL_EUROPE,
                fallback_url="https://www.uefa.com/uefachampionsleague/fixtures-results/",
                phase=UCL_PHASES.get(slug, "knockout" if slug else "league_phase"),
                input_url=url,
            )
            if event:
                events.append(event)
    return _in_year(_dedupe(events), year)


# --- Official league APIs ---------------------------------------------------

MLB_PHASES = {"R": "regular_season", "F": "postseason", "D": "postseason", "L": "postseason", "W": "final"}


def mlb_events(year: int) -> list[CalendarEvent]:
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={year}&gameType=R,F,D,L,W"
    payload = get_json(url)
    events = []
    for day in rows(payload, "dates"):
        for game in rows(day, "games"):
            status = game.get("status") or {}
            if status.get("detailedState") in {"Postponed", "Cancelled", "Suspended"}:
                continue
            away = game["teams"]["away"]["team"]["name"]
            home = game["teams"]["home"]["team"]["name"]
            series = game.get("seriesDescription") if game.get("gameType") in MLB_PHASES.keys() - {"R"} else None
            subtitle = None
            if series:
                subtitle = f"{series} · Game {game.get('seriesGameNumber')} of {game.get('gamesInSeries')}"
                subtitle += " · if necessary" if game.get("ifNecessary") == "Y" else ""
            # Undecided postseason slots arrive as "NL Lower Seed" or "Higher Seed League Champion".
            undecided = any(word in name for name in (away, home) for word in ("Seed", "League Champion"))
            if undecided:
                away = home = None
            events.append(
                make_event(
                    source="mlb",
                    league="MLB",
                    sport="baseball",
                    upstream_id=game["gamePk"],
                    season=str(game.get("season", year)),
                    title=f"{series} · Game {game.get('seriesGameNumber')}" if undecided else f"{away} at {home}",
                    subtitle=subtitle,
                    utc=None if status.get("startTimeTBD") else game["gameDate"],
                    day=game.get("officialDate") or _local_date(game["gameDate"], EASTERN),
                    home=home,
                    away=away,
                    phase=MLB_PHASES.get(game.get("gameType"), "regular_season"),
                    venue=(game.get("venue") or {}).get("name"),
                    source_url=f"https://www.mlb.com/gameday/{game['gamePk']}",
                    status="finished"
                    if status.get("abstractGameState") == "Final"
                    or status.get("detailedState") in {"Final", "Game Over"}
                    else "scheduled",
                    facts_source_url=url,
                    round_or_stage=(game.get("description") or subtitle) if series and not undecided else None,
                )
            )
            for participant in events[-1].participants:
                row = game["teams"][participant.role]
                team = row["team"]
                participant.participant_id = str(team["id"]) if team.get("id") is not None else None
                participant.short_name = team.get("shortName") or team.get("abbreviation")
                record = row.get("leagueRecord") or {}
                if type(record.get("wins")) is int and type(record.get("losses")) is int:
                    participant.record = f"{record['wins']}-{record['losses']}" + (
                        f"-{record['ties']}" if record.get("ties") else ""
                    )
                participant.final_score = _score(row.get("score")) if events[-1].status == "finished" else None
            events[-1].raw_source_payload = {
                "game_number": game.get("gameNumber"),
                "double_header": game.get("doubleHeader"),
            }
    return _in_year(_dedupe(events), year)


def nhl_events(year: int) -> list[CalendarEvent]:
    """Walk the week-by-week schedule across the calendar year (about 53 requests)."""
    events = []
    cursor = date(year, 1, 1)
    end = date(year, 12, 31)
    while cursor <= end:
        url = f"https://api-web.nhle.com/v1/schedule/{cursor.isoformat()}"
        payload = get_json(url)
        for week in rows(payload, "gameWeek"):
            for game in rows(week, "games"):
                if game.get("gameType") not in (2, 3) or game.get("gameScheduleState") not in (None, "OK"):
                    continue
                away = _nhl_team(game["awayTeam"])
                home = _nhl_team(game["homeTeam"])
                events.append(
                    make_event(
                        source="nhl",
                        league="NHL",
                        sport="hockey",
                        upstream_id=game["id"],
                        season=str(game.get("season", "")),
                        title=f"{away} at {home}",
                        utc=game.get("startTimeUTC"),
                        day=week["date"],
                        home=home,
                        away=away,
                        phase="postseason" if game["gameType"] == 3 else "regular_season",
                        venue=(game.get("venue") or {}).get("default"),
                        source_url=f"https://www.nhl.com/gamecenter/{game['id']}",
                        status="finished" if game.get("gameState") in {"FINAL", "OFF"} else "scheduled",
                        facts_source_url=url,
                    )
                )
                for participant in events[-1].participants:
                    team = game[f"{participant.role}Team"]
                    participant.participant_id = str(team["id"]) if team.get("id") is not None else None
                    participant.short_name = (team.get("commonName") or {}).get("default") or team.get("abbrev")
                    participant.record = _record(team.get("record"))
                    participant.final_score = _score(team.get("score")) if events[-1].status == "finished" else None
        following = payload.get("nextStartDate")
        next_cursor = date.fromisoformat(following) if following else cursor + timedelta(days=7)
        cursor = max(next_cursor, cursor + timedelta(days=1))
    return _in_year(_dedupe(events), year)


def _nhl_team(team: dict) -> str:
    place = (team.get("placeName") or {}).get("default", "")
    common = (team.get("commonName") or {}).get("default", "")
    return f"{place} {common}".strip() or team.get("abbrev", "TBD")


# league -> (source kind, fetcher). Order is the order of the refresh log.
FEEDS: dict[str, tuple[str, Callable[[int], list[CalendarEvent]]]] = {
    "NFL": ("espn", nfl_events),
    "NBA": ("espn", nba_events),
    "MLB": ("mlb", mlb_events),
    "NHL": ("nhl", nhl_events),
    "UEFA_CHAMPIONS_LEAGUE": ("espn", ucl_events),
    "PGA_TOUR": (
        "espn",
        espn_season_feed("golf/pga", "PGA_TOUR", "golf", "tournament", "https://www.pgatour.com/schedule", span=True),
    ),
    "LPGA_TOUR": (
        "espn",
        espn_season_feed(
            "golf/lpga",
            "LPGA_TOUR",
            "golf",
            "tournament",
            "https://www.espn.com/golf/leaderboard/_/tour/lpga",
            span=True,
        ),
    ),
    "DP_WORLD_TOUR": (
        "espn",
        espn_season_feed(
            "golf/eur",
            "DP_WORLD_TOUR",
            "golf",
            "tournament",
            "https://www.espn.com/golf/leaderboard/_/tour/eur",
            span=True,
        ),
    ),
    "LIV_GOLF": (
        "espn",
        espn_season_feed(
            "golf/liv",
            "LIV_GOLF",
            "golf",
            "tournament",
            "https://www.espn.com/golf/leaderboard/_/tour/liv",
            span=True,
        ),
    ),
    "ATP": (
        "espn",
        espn_season_feed(
            "tennis/atp", "ATP", "tennis", "tournament", "https://www.espn.com/tennis/schedule/_/type/atp", span=True
        ),
    ),
    "WTA": (
        "espn",
        espn_season_feed(
            "tennis/wta", "WTA", "tennis", "tournament", "https://www.espn.com/tennis/schedule/_/type/wta", span=True
        ),
    ),
    **{
        league: (
            "espn",
            espn_season_feed(
                f"rugby/{slug}",
                league,
                "rugby",
                "game",
                f"https://www.espn.com/rugby/fixtures/_/league/{slug}",
                zone=ZoneInfo("UTC"),
            ),
        )
        for league, (slug, _) in RUGBY_LEAGUES.items()
    },
    "UFC": ("espn", espn_season_feed("mma/ufc", "UFC", "combat", "card", "https://www.ufc.com/events")),
    "NASCAR_CUP": (
        "espn",
        espn_season_feed("racing/nascar-premier", "NASCAR_CUP", "motorsport", "race", "https://www.nascar.com/"),
    ),
    "INDYCAR": ("espn", espn_season_feed("racing/irl", "INDYCAR", "motorsport", "race", "https://www.indycar.com/")),
    **{league: ("espn", lambda year, league=league: espn_team_events(year, league)) for league in TEAM_LEAGUES},
}
