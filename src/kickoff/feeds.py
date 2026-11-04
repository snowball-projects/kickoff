"""Scheduled league feeds: official league APIs and ESPN's public site JSON.

Approved by the owner on October 1, 2026 for factual schedule data (dates, times,
participants, venues). These sources grant no data license; the calendar names
them, links back, and includes only supplied team facts and confirmed final scores,
never odds or article content.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from calendar import monthrange
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from functools import cache
from importlib.resources import files
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from kickoff.countries import COUNTRY_LEAGUES, tennis_venue_country, venue_country
from kickoff.http import read_bounded_response
from kickoff.models import CalendarEvent, Participant
from kickoff.semantics import classification_fields
from kickoff.source_units import espn_unit, mlb_unit, nhl_unit, unit_key
from kickoff.team_logos import TEAM_SPORTS, source_logo

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


def get_json(
    url: str, *, retries: int = 3, missing_ok: bool = False, receipt: dict | None = None
) -> dict | list | None:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Encoding": "gzip"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=60) as response:
                data = read_bounded_response(response, max_bytes=MAX_BYTES)
            parsed = json.loads(data)
            if receipt is not None:
                checked = datetime.now(UTC)
                receipt.update(
                    url=url,
                    checked_date=checked.date().isoformat(),
                    observed_at=checked.isoformat(),
                    sha256=hashlib.sha256(data).hexdigest(),
                    hash_scope="decoded source response bytes",
                )
            return parsed
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


def _schedule_source(url: str, league: str, kind: str, *, plan=None, **options):
    """Reuse normalized frozen facts, never synthetic raw source responses."""
    key = unit_key(url)
    if plan is not None:
        reused = plan.try_reuse(key)
        if reused is not None:
            return None, reused, {}
    receipt = {}
    payload = get_json(url, receipt=receipt, **options)
    if plan is not None:
        observed = datetime.fromisoformat(receipt["observed_at"]) if receipt else plan.now
        if kind == "espn":
            unit = espn_unit(url, payload, league, observed)
        elif kind == "mlb":
            unit = mlb_unit(url, payload, observed)
        else:
            unit = nhl_unit(url, payload, observed)
        plan.observe(unit)
        if receipt:
            plan.receipts[key] = {**receipt, "kind": kind, "league": league}
    return payload, None, receipt


# These fields describe evidence, not the normalized event or team facts.
_CITATION_FIELDS = {
    "source_url",
    "facts_source_url",
    "facts_checked_date",
    "start_time_source_url",
    "country_source_url",
    "country_checked_date",
    "team_source_url",
    "logo_source_url",
    "logo_checked_date",
    "start_list_source_url",
    "start_list_checked_date",
    "source_article_url",
    "input_url",
    "checked_date",
    "sha256",
    "hash_scope",
    "revision",
    "review_revision",
    "raw_source_payload",
}


def _same_event_facts(first: CalendarEvent, second: CalendarEvent) -> bool:
    def facts(value):
        if isinstance(value, dict):
            return {
                key: sorted(set(item)) if key == "tags" else facts(item)
                for key, item in value.items()
                if key not in _CITATION_FIELDS
            }
        if isinstance(value, list):
            return [facts(item) for item in value]
        return value

    return facts(first.to_dict()) == facts(second.to_dict())


def _append_pending(events: list[CalendarEvent], batch: list[CalendarEvent]) -> None:
    """Keep normal provenance for equal facts; actual corrections still win."""
    previous = {event.event_id: event for event in events}
    for event in batch:
        original = previous.get(event.event_id)
        if original is not None and _same_event_facts(original, event):
            continue
        events.append(event)
        previous[event.event_id] = event


def _pending_source_urls(plan, prefix: str) -> list[str]:
    """Previously observed locators omitted by this run's current discovery."""
    if plan is None:
        return []
    target = urlsplit(prefix)
    pending = []
    for key in sorted(plan.pending_unit_keys):
        previous = plan.baseline.units[key]
        parts = urlsplit(previous.source_url)
        matches = parts.path.startswith(target.path) if target.path.endswith("/") else parts.path == target.path
        if (parts.scheme, parts.netloc) != (target.scheme, target.netloc) or not matches:
            continue
        pending.append(previous.source_url)
    return pending


def _finish_source_children(plan, url: str, children: list[str]) -> None:
    if plan is None:
        return
    key = unit_key(url)
    unit = plan.current[key]
    observed = plan.units
    complete = bool(children) and all(child in observed and observed[child].complete for child in children)
    end = datetime.fromisoformat(unit.end.replace("Z", "+00:00")) if unit.end else None
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    closed = complete and end is not None and end < plan.now - timedelta(days=2)
    plan.observe(replace(unit, children=tuple(children), complete=complete, closed=closed))


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


def _espn_participants(event: CalendarEvent, competitors: list, finished: bool, image_source_url: str) -> None:
    for participant in event.participants:
        row = next((c for c in competitors if c.get("homeAway") == participant.role), {})
        team = row.get("team") or {}
        participant.participant_id = str(team["id"]) if team.get("id") is not None else None
        participant.short_name = team.get("shortDisplayName") or team.get("abbreviation")
        participant.record = _espn_record(row, event.sport)
        participant.final_score = _score(row.get("score")) if finished else None
        national = _espn_national_teams().get(f"{event.sport}/{participant.participant_id}")
        if national:
            participant.entity_type = "national_team"
            participant.metadata.update(
                country_code=national["country_code"],
                country_source_url=national["source_url"],
                country_checked_date=national["checked_date"],
                country_source_kind=national.get("source_kind", "espn"),
            )
        if event.sport in TEAM_SPORTS and (logo := source_logo(team, participant)):
            participant.metadata.update(
                logo_url=logo,
                logo_source_url=image_source_url,
                logo_checked_date=event.facts_checked_date,
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
    image_source_url: str | None = None,
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
    venue = competition.get("venue") or (event.get("venue") if league in {"ATP", "WTA"} else None) or {}
    country = venue_country((venue.get("address") or {}).get("country")) if league in COUNTRY_LEAGUES else None
    if not country and league in {"ATP", "WTA"}:
        country = tennis_venue_country(venue)
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
        venue=venue.get("fullName") or venue.get("displayName"),
        source_url=_espn_link(event, fallback_url),
        country=country,
        country_source_url=(input_url or _espn_link(event, fallback_url)) if country else None,
        country_checked_date=datetime.now(UTC).date().isoformat() if country else None,
        status="finished" if finished else "scheduled",
        facts_source_url=input_url or _espn_link(event, fallback_url),
        round_or_stage=round_label,
        week_label=week_label,
    )
    _espn_participants(result, competitors, finished, image_source_url or input_url or result.facts_source_url)
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

    def collect(url, plan):
        payload, reused, receipt = _schedule_source(url, league, "espn", plan=plan)
        if reused is not None:
            return reused
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
        return events

    def fetch(year: int, *, plan=None) -> list[CalendarEvent]:
        events = collect(f"{ESPN}/{path}/scoreboard?dates={year}&limit=500", plan)
        for previous_url in _pending_source_urls(plan, f"{ESPN}/{path}/scoreboard"):
            previous_year = int(parse_qs(urlsplit(previous_url).query)["dates"][0])
            if previous_year < year:
                _append_pending(events, collect(previous_url, plan))
        return _in_year(_dedupe(events), year)

    return fetch


def nfl_events(year: int, *, plan=None) -> list[CalendarEvent]:
    """Weekly scoreboards for the season ending early in `year` and the one starting in it."""
    events = []
    weeks = [(year - 1, 2, week) for week in (17, 18)] + [(year - 1, 3, week) for week in range(1, 6)]
    weeks += [(year, 2, week) for week in range(1, 19)] + [(year, 3, week) for week in range(1, 6)]

    def collect(url, season_type, week):
        payload, reused, _ = _schedule_source(url, "NFL", "espn", plan=plan, missing_ok=True)
        if reused is not None:
            return reused
        batch = []
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
                image_source_url=url,
            )
            if event:
                competition = (row.get("competitions") or [{}])[0]
                label = " · ".join(
                    note["headline"]
                    for note in competition.get("notes") or []
                    if note.get("type") == "event" and note.get("headline")
                )
                _espn_appointment(event, label)
                batch.append(event)

        return batch

    for season, season_type, week in weeks:
        events.extend(
            collect(
                f"{ESPN}/football/nfl/scoreboard?dates={season}&seasontype={season_type}&week={week}", season_type, week
            )
        )
    for url in _pending_source_urls(plan, f"{ESPN}/football/nfl/scoreboard"):
        query = parse_qs(urlsplit(url).query)
        if int(query["dates"][0][:4]) <= year:
            _append_pending(events, collect(url, int(query["seasontype"][0]), int(query["week"][0])))
    return _in_year(_dedupe(events), year)


def nba_events(year: int, *, plan=None) -> list[CalendarEvent]:
    """Per-team season schedules; ESPN rejects league-wide date ranges."""
    teams = get_json(f"{ESPN}/basketball/nba/teams")["sports"][0]["leagues"][0]["teams"]
    team_ids = [team["team"]["id"] for team in teams]
    if len(team_ids) < 30:
        raise ValueError(f"Expected 30 NBA teams, got {len(team_ids)}")
    events = []
    records = {}

    def collect(url, team_id, season_type, *, pending=False):
        payload, reused, _ = _schedule_source(url, "NBA", "espn", plan=plan, missing_ok=True)
        if reused is not None:
            return reused
        record = _record((payload or {}).get("team", {}).get("recordSummary"))
        batch = []
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
                batch.append(event)
                if record and str((payload.get("team") or {}).get("id")) == str(team_id):
                    identity = event.event_id, str(team_id)
                    if not pending or identity not in records or records[identity][0] != record:
                        records[identity] = (record, url)

        return batch

    for team_id in team_ids:
        for season, season_type in ((year, 2), (year, 3), (year + 1, 2)):
            events.extend(
                collect(
                    f"{ESPN}/basketball/nba/teams/{team_id}/schedule?season={season}&seasontype={season_type}",
                    team_id,
                    season_type,
                )
            )
    for url in _pending_source_urls(plan, f"{ESPN}/basketball/nba/teams/"):
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        season, season_type = int(query["season"][0]), int(query["seasontype"][0])
        if parts.path.endswith("/schedule") and (season <= year or (season == year + 1 and season_type == 2)):
            _append_pending(events, collect(url, parts.path.split("/")[-2], season_type, pending=True))
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


def espn_team_events(year: int, league: str, *, plan=None) -> list[CalendarEvent]:
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

    def query_url(prefix, group, season_type=None, week=None):
        url = f"{ESPN}/{path}/scoreboard?dates={prefix}&limit={limit}"
        if season_type is not None:
            url += f"&seasontype={season_type}&week={week}"
        if group is not None:
            url += f"&groups={group}"
        return url

    def collect(
        prefix: str, group: int | None, season_type: str | None = None, week: str | None = None, request_url=None
    ):
        url = request_url or query_url(prefix, group, season_type, week)
        payload, reused, _ = _schedule_source(url, league, "espn", plan=plan)
        if reused is not None:
            return reused
        selected = rows(payload, "events")
        supplements = []
        dependencies = []
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
                    dependencies.append(unit_key(query_url(prefix, group, kind, number)))
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
            result = [event for child in children for event in collect(child, group)] + supplements
            dependencies.extend(unit_key(query_url(child, group)) for child in children)
            _finish_source_children(plan, url, dependencies)
            return result
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
        if dependencies:
            _finish_source_children(plan, url, dependencies)
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
    events = {}

    def merge(batch, *, pending=False):
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
            if pending and event.event_id in events and _same_event_facts(events[event.event_id], event):
                continue
            events[event.event_id] = event

    with ThreadPoolExecutor(max_workers=4) as executor:
        for batch in executor.map(lambda args: collect(*args), queries):
            merge(batch)
    for url in _pending_source_urls(plan, f"{ESPN}/{path}/scoreboard"):
        query = parse_qs(urlsplit(url).query)
        prefix = query["dates"][0]
        if int(prefix[:4]) > year:
            continue
        group = int(query["groups"][0]) if "groups" in query else None
        merge(
            collect(prefix, group, query.get("seasontype", [None])[0], query.get("week", [None])[0], url), pending=True
        )
    result = _in_year(list(events.values()), year)
    return result


UCL_PHASES = {"league-phase": "league_phase", "final": "final"}


def ucl_events(year: int, *, plan=None) -> list[CalendarEvent]:
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
    urls = [f"{ESPN}/soccer/uefa.champions/scoreboard?dates={day.replace('-', '')}" for day in sorted(days)]
    normal_urls = set(urls)
    urls.extend(
        url
        for url in _pending_source_urls(plan, f"{ESPN}/soccer/uefa.champions/scoreboard")
        if int(parse_qs(urlsplit(url).query)["dates"][0][:4]) <= year
    )
    for url in dict.fromkeys(urls):
        payload, reused, _ = _schedule_source(url, "UEFA_CHAMPIONS_LEAGUE", "espn", plan=plan, missing_ok=True)
        if reused is not None:
            if url in normal_urls:
                events.extend(reused)
            else:
                _append_pending(events, reused)
            continue
        batch = []
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
                batch.append(event)
        if url in normal_urls:
            events.extend(batch)
        else:
            _append_pending(events, batch)
    return _in_year(_dedupe(events), year)


# --- Official league APIs ---------------------------------------------------

MLB_PHASES = {"R": "regular_season", "F": "postseason", "D": "postseason", "L": "postseason", "W": "final"}


def mlb_events(year: int, *, plan=None) -> list[CalendarEvent]:
    events = []

    def collect(url):
        payload, reused, _ = _schedule_source(url, "MLB", "mlb", plan=plan)
        if reused is not None:
            return reused
        batch = []
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
                country = venue_country(((game.get("venue") or {}).get("location") or {}).get("country"))
                batch.append(
                    make_event(
                        source="mlb",
                        league="MLB",
                        sport="baseball",
                        upstream_id=game["gamePk"],
                        season=str(game.get("season", parse_qs(urlsplit(url).query)["season"][0])),
                        title=f"{series} · Game {game.get('seriesGameNumber')}" if undecided else f"{away} at {home}",
                        subtitle=subtitle,
                        utc=None if status.get("startTimeTBD") else game["gameDate"],
                        day=game.get("officialDate") or _local_date(game["gameDate"], EASTERN),
                        home=home,
                        away=away,
                        phase=MLB_PHASES.get(game.get("gameType"), "regular_season"),
                        venue=(game.get("venue") or {}).get("name"),
                        source_url=f"https://www.mlb.com/gameday/{game['gamePk']}",
                        country=country,
                        country_source_url=url if country else None,
                        country_checked_date=datetime.now(UTC).date().isoformat() if country else None,
                        status="finished"
                        if status.get("abstractGameState") == "Final"
                        or status.get("detailedState") in {"Final", "Game Over"}
                        else "scheduled",
                        facts_source_url=url,
                        round_or_stage=(game.get("description") or subtitle) if series and not undecided else None,
                    )
                )
                for participant in batch[-1].participants:
                    row = game["teams"][participant.role]
                    team = row["team"]
                    participant.participant_id = str(team["id"]) if team.get("id") is not None else None
                    participant.short_name = team.get("shortName") or team.get("abbreviation")
                    record = row.get("leagueRecord") or {}
                    if type(record.get("wins")) is int and type(record.get("losses")) is int:
                        participant.record = f"{record['wins']}-{record['losses']}" + (
                            f"-{record['ties']}" if record.get("ties") else ""
                        )
                    participant.final_score = _score(row.get("score")) if batch[-1].status == "finished" else None
                    if batch[-1].status == "finished" and type(row.get("isWinner")) is bool:
                        participant.metadata["result_winner"] = row["isWinner"]
                batch[-1].raw_source_payload = {
                    "game_number": game.get("gameNumber"),
                    "double_header": game.get("doubleHeader"),
                }

        return batch

    events.extend(
        collect(
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={year}&gameType=R,F,D,L,W&hydrate=venue(location)"
        )
    )
    for previous_url in _pending_source_urls(plan, "https://statsapi.mlb.com/api/v1/schedule"):
        previous_year = int(parse_qs(urlsplit(previous_url).query)["season"][0])
        if previous_year < year:
            _append_pending(events, collect(previous_url))
    return _in_year(_dedupe(events), year)


def nhl_events(year: int, *, plan=None) -> list[CalendarEvent]:
    """Walk the week-by-week schedule across the calendar year (about 53 requests)."""
    events = []

    def collect(url):
        payload, reused, _ = _schedule_source(url, "NHL", "nhl", plan=plan)
        if reused is not None:
            return plan.baseline.units[unit_key(url)].end[:10], reused
        batch = []
        for week in rows(payload, "gameWeek"):
            for game in rows(week, "games"):
                if game.get("gameType") not in (2, 3) or game.get("gameScheduleState") not in (None, "OK"):
                    continue
                away = _nhl_team(game["awayTeam"])
                home = _nhl_team(game["homeTeam"])
                batch.append(
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
                for participant in batch[-1].participants:
                    team = game[f"{participant.role}Team"]
                    participant.participant_id = str(team["id"]) if team.get("id") is not None else None
                    participant.short_name = (team.get("commonName") or {}).get("default") or team.get("abbrev")
                    participant.record = _record(team.get("record"))
                    participant.final_score = _score(team.get("score")) if batch[-1].status == "finished" else None
        return payload.get("nextStartDate"), batch

    cursor = date(year, 1, 1)
    end = date(year, 12, 31)
    while cursor <= end:
        following, batch = collect(f"https://api-web.nhle.com/v1/schedule/{cursor.isoformat()}")
        events.extend(batch)
        next_cursor = date.fromisoformat(following) if following else cursor + timedelta(days=7)
        cursor = max(next_cursor, cursor + timedelta(days=1))
    for url in _pending_source_urls(plan, "https://api-web.nhle.com/v1/schedule/"):
        if int(urlsplit(url).path.rsplit("/", 1)[-1][:4]) > year:
            continue
        visited = set()
        while unit_key(url) not in plan.current and url not in visited:
            visited.add(url)
            following, batch = collect(url)
            _append_pending(events, batch)
            if not following or date.fromisoformat(following) > end:
                break
            next_url = f"https://api-web.nhle.com/v1/schedule/{following}"
            url = next_url
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
    **{
        league: ("espn", lambda year, league=league, plan=None: espn_team_events(year, league, plan=plan))
        for league in TEAM_LEAGUES
    },
}
