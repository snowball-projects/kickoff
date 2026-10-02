"""Scheduled league feeds: official league APIs and ESPN's public site JSON.

Approved by the owner on October 1, 2026 for factual schedule data (dates, times,
participants, venues). These sources grant no data license; the calendar names
them, links back, and carries no logos, scores, odds or article content.
"""

from __future__ import annotations

import gzip
import json
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from kickoff.models import CalendarEvent, Participant
from kickoff.semantics import classification_fields

USER_AGENT = "kickoff-refresh/0.3 (https://github.com/snowball-projects/kickoff)"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
EASTERN = ZoneInfo("America/New_York")
CENTRAL_EUROPE = ZoneInfo("Europe/Paris")
# Golf scoreboards embed full leaderboards; gzip keeps the transfer to a few MB.
MAX_BYTES = 80_000_000
DROPPED_STATUSES = {"STATUS_CANCELED", "STATUS_POSTPONED", "STATUS_SUSPENDED", "STATUS_FORFEIT"}

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
                data = response.read(MAX_BYTES + 1)
                if response.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
            if len(data) > MAX_BYTES:
                raise ValueError(f"Source exceeds size limit: {url}")
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


def _local_date(utc: str, zone: ZoneInfo) -> str:
    return datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(zone).date().isoformat()


def _iso_utc(value: str) -> str:
    """Normalize '2026-10-07T23:30Z' and '...:00Z' forms to seconds precision."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


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
        # Clients derive not started / live / over from the clock; no live state is stored.
        status="scheduled",
        venue=venue,
        city=None,
        region=None,
        country=None,
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
) -> CalendarEvent | None:
    status = ((event.get("status") or {}).get("type") or {}).get("name", "")
    competition = (event.get("competitions") or [{}])[0]
    if status in DROPPED_STATUSES or status.startswith("STATUS_CANCEL"):
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
    return make_event(
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
        venue=(competition.get("venue") or {}).get("fullName"),
        source_url=_espn_link(event, fallback_url),
    )


def _in_year(events: list[CalendarEvent], year: int) -> list[CalendarEvent]:
    prefix = str(year)
    return [
        e
        for e in events
        if (e.calendar_date or "").startswith(prefix) or (e.end_calendar_date or "").startswith(prefix)
    ]


def _dedupe(events: list[CalendarEvent]) -> list[CalendarEvent]:
    return list({event.event_id: event for event in events}.values())


def espn_season_feed(path: str, league: str, sport: str, event_type: str, fallback_url: str, *, span=False):
    """Golf, MMA and racing: one scoreboard request returns the whole calendar year."""

    def fetch(year: int) -> list[CalendarEvent]:
        payload = get_json(f"{ESPN}/{path}/scoreboard?dates={year}&limit=500")
        events = []
        for row in payload.get("events") or []:
            phase = "regular_season"
            name = row.get("name", "")
            if league == "NASCAR_CUP" and any(word in name for word in ("Clash", "Duel", "All-Star")):
                phase = "exhibition"
            event = _espn_event(
                row,
                league=league,
                sport=sport,
                zone=EASTERN,
                fallback_url=fallback_url,
                event_type=event_type,
                phase=phase,
                span=span,
            )
            if event:
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
        for row in (payload or {}).get("events") or []:
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
                events.append(event)
    return _in_year(_dedupe(events), year)


def nba_events(year: int) -> list[CalendarEvent]:
    """Per-team season schedules; ESPN rejects league-wide date ranges."""
    teams = get_json(f"{ESPN}/basketball/nba/teams")["sports"][0]["leagues"][0]["teams"]
    team_ids = [team["team"]["id"] for team in teams]
    if len(team_ids) < 30:
        raise ValueError(f"Expected 30 NBA teams, got {len(team_ids)}")
    events = []
    for team_id in team_ids:
        for season, season_type in ((year, 2), (year, 3), (year + 1, 2)):
            payload = get_json(
                f"{ESPN}/basketball/nba/teams/{team_id}/schedule?season={season}&seasontype={season_type}",
                missing_ok=True,
            )
            for row in (payload or {}).get("events") or []:
                event = _espn_event(
                    row,
                    league="NBA",
                    sport="basketball",
                    zone=EASTERN,
                    fallback_url="https://www.nba.com/schedule",
                    phase="postseason" if season_type == 3 else "regular_season",
                )
                if event:
                    events.append(event)
    return _in_year(_dedupe(events), year)


UCL_PHASES = {"league-phase": "league_phase", "final": "final"}


def ucl_events(year: int) -> list[CalendarEvent]:
    """OpenLigaDB lists the match dates; ESPN supplies English names and kickoff times."""
    days = set()
    for season in (year - 1, year):
        matches = get_json(f"https://api.openligadb.de/getmatchdata/ucl/{season}", missing_ok=True) or []
        for match in matches:
            utc = match.get("matchDateTimeUTC")
            if utc and not utc.startswith("1970"):
                day = _local_date(utc, CENTRAL_EUROPE)
                if day.startswith(str(year)):
                    days.add(day)
    events = []
    for day in sorted(days):
        payload = get_json(f"{ESPN}/soccer/uefa.champions/scoreboard?dates={day.replace('-', '')}", missing_ok=True)
        for row in (payload or {}).get("events") or []:
            slug = (row.get("season") or {}).get("slug", "")
            event = _espn_event(
                row,
                league="UEFA_CHAMPIONS_LEAGUE",
                sport="soccer",
                zone=CENTRAL_EUROPE,
                fallback_url="https://www.uefa.com/uefachampionsleague/fixtures-results/",
                phase=UCL_PHASES.get(slug, "knockout" if slug else "league_phase"),
            )
            if event:
                events.append(event)
    return _in_year(_dedupe(events), year)


# --- Official league APIs ---------------------------------------------------

MLB_PHASES = {"R": "regular_season", "F": "postseason", "D": "postseason", "L": "postseason", "W": "final"}


def mlb_events(year: int) -> list[CalendarEvent]:
    payload = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={year}&gameType=R,F,D,L,W")
    events = []
    for day in payload.get("dates") or []:
        for game in day.get("games") or []:
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
                    title=f"{series} · Game {game.get('seriesGameNumber')} · teams TBD"
                    if undecided
                    else f"{away} at {home}",
                    subtitle=subtitle,
                    utc=None if status.get("startTimeTBD") else game["gameDate"],
                    day=game.get("officialDate") or _local_date(game["gameDate"], EASTERN),
                    home=home,
                    away=away,
                    phase=MLB_PHASES.get(game.get("gameType"), "regular_season"),
                    venue=(game.get("venue") or {}).get("name"),
                    source_url=f"https://www.mlb.com/gameday/{game['gamePk']}",
                )
            )
    return _in_year(_dedupe(events), year)


def nhl_events(year: int) -> list[CalendarEvent]:
    """Walk the week-by-week schedule across the calendar year (about 53 requests)."""
    events = []
    cursor = date(year, 1, 1)
    end = date(year, 12, 31)
    while cursor <= end:
        payload = get_json(f"https://api-web.nhle.com/v1/schedule/{cursor.isoformat()}")
        for week in payload.get("gameWeek") or []:
            for game in week.get("games") or []:
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
                    )
                )
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
    "UFC": ("espn", espn_season_feed("mma/ufc", "UFC", "combat", "card", "https://www.ufc.com/events")),
    "NASCAR_CUP": (
        "espn",
        espn_season_feed("racing/nascar-premier", "NASCAR_CUP", "motorsport", "race", "https://www.nascar.com/"),
    ),
    "INDYCAR": ("espn", espn_season_feed("racing/irl", "INDYCAR", "motorsport", "race", "https://www.indycar.com/")),
}
