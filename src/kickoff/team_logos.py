"""Optional ESPN team images, matched within their source competition season."""

from __future__ import annotations

import logging
import re
import zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import cache
from threading import Lock
from urllib.error import HTTPError
from urllib.parse import urlsplit

from kickoff.models import CalendarEvent, Participant
from kickoff.textutils import espn_logo_url

logger = logging.getLogger(__name__)
SITE = "https://site.api.espn.com/apis/site/v2/sports"
CORE = "https://sports.core.api.espn.com/v2/sports"
TEAM_SPORTS = {"soccer", "football", "basketball", "baseball", "hockey", "rugby", "cricket"}
LOGO_FIELDS = ("logo_url", "logo_source_url", "logo_checked_date")
NAME_FIELDS = ("displayName", "name", "shortDisplayName", "location", "abbreviation")
OPTIONAL_TIMEOUT_SECONDS = 3


class _LookupCircuit:
    def __init__(self):
        self.lock = Lock()
        self.failed = False

    def allows_request(self) -> bool:
        with self.lock:
            return not self.failed

    def stop(self) -> bool:
        with self.lock:
            first_failure = not self.failed
            self.failed = True
            return first_failure


_metadata_circuit = _LookupCircuit()


def _name(value: str) -> str:
    return " ".join(value.casefold().split())


def source_logo(team: dict) -> str | None:
    candidates = [team.get("logo")]
    if isinstance(team.get("logos"), list):
        candidates.extend(row.get("href") for row in team["logos"] if isinstance(row, dict))
    return next((logo for value in candidates if (logo := espn_logo_url(value))), None)


@cache
def league_paths() -> dict[str, str]:
    from kickoff import feeds
    from kickoff.start_times import football_teams

    result = {league: row[0] for league, row in feeds.TEAM_LEAGUES.items()}
    result.update({league: f"rugby/{row[0]}" for league, row in feeds.RUGBY_LEAGUES.items()})
    result.update({league: f"soccer/{row['espn_path']}" for league, row in football_teams().items()})
    result.update(
        NFL="football/nfl",
        NBA="basketball/nba",
        MLB="baseball/mlb",
        NHL="hockey/nhl",
        UEFA_CHAMPIONS_LEAGUE="soccer/uefa.champions",
        FIFA_WORLD_CUP="soccer/fifa.world",
        FIFA_WOMENS_WORLD_CUP="soccer/fifa.wwc",
    )
    return result


def competition_season(event: CalendarEvent) -> int | None:
    if event.league == "NHL":
        return int(event.season[4:]) if re.fullmatch(r"\d{8}", event.season) else None
    if re.fullmatch(r"\d{4}-\d{2}", event.season):
        start = int(event.season[:4])
        return start if int(event.season[5:]) == (start + 1) % 100 else None
    return int(event.season) if re.fullmatch(r"\d{4}", event.season) else None


@cache
def _optional_json(url: str) -> dict | None:
    from kickoff.feeds import get_json

    circuit = _metadata_circuit
    if not circuit.allows_request():
        return None
    try:
        payload = get_json(url, missing_ok=True, retries=1, timeout=OPTIONAL_TIMEOUT_SECONDS)
    except (HTTPError, OSError, TimeoutError, ValueError, EOFError, zlib.error) as error:
        if circuit.stop():
            logger.warning("Optional ESPN image lookup failed; stopping further image requests: %s: %s", url, error)
        return None
    return payload if isinstance(payload, dict) else None


def _core_url(path: str, season: int, team_id: str | None = None) -> str:
    sport, league = path.split("/", 1)
    base = f"{CORE}/{sport}/leagues/{league}/seasons/{season}/teams"
    return f"{base}/{team_id}?lang=en&region=us" if team_id is not None else f"{base}?limit=1000"


@cache
def _core_team(path: str, season: int, team_id: str) -> tuple[dict, str] | None:
    url = _core_url(path, season, team_id)
    team = _optional_json(url)
    return (team, url) if team and str(team.get("id")) == team_id else None


@cache
def _season_teams(path: str, season: int) -> dict[str, tuple[dict, str]] | None:
    url = _core_url(path, season)
    first = _optional_json(url)
    if first is None or not isinstance(first.get("items"), list):
        return None
    pages, count = first.get("pageCount"), first.get("count")
    if type(pages) is not int or pages < 1 or type(count) is not int or count < 0:
        return None
    ids = set()
    for page in range(1, pages + 1):
        payload = first if page == 1 else _optional_json(f"{url}&page={page}")
        if payload is None or not isinstance(payload.get("items"), list):
            return None
        for row in payload["items"]:
            reference = row.get("$ref") if isinstance(row, dict) else None
            if not isinstance(reference, str):
                return None
            try:
                parsed = urlsplit(reference)
            except ValueError:
                return None
            prefix = urlsplit(_core_url(path, season)).path + "/"
            team_id = parsed.path.removeprefix(prefix)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != "sports.core.api.espn.com":
                return None
            if not parsed.path.startswith(prefix) or not team_id.isdigit():
                return None
            ids.add(team_id)
    if len(ids) != count:
        return None
    with ThreadPoolExecutor(max_workers=6) as executor:
        fetched = list(executor.map(lambda identity: (identity, _core_team(path, season, identity)), sorted(ids)))
    if any(team is None for _, team in fetched):
        return None
    return dict(fetched)


def _names(team: dict) -> set[str]:
    return {_name(team[key]) for key in NAME_FIELDS if isinstance(team.get(key), str) and team[key].strip()}


def _matches(participant: Participant, team: dict) -> bool:
    return any(_name(value) in _names(team) for value in (participant.name, participant.short_name) if value)


@cache
def _name_index(path: str, season: int) -> dict[str, dict[str, tuple[dict, str]]] | None:
    teams = _season_teams(path, season)
    if teams is None:
        return None
    index = defaultdict(dict)
    for identity, item in teams.items():
        for value in _names(item[0]):
            index[value][identity] = item
    return dict(index)


def _match_name(path: str, season: int, participant: Participant) -> tuple[tuple[dict, str] | None, str]:
    index = _name_index(path, season)
    if index is None:
        return None, "unavailable_metadata"
    candidates = index.get(_name(participant.name), {})
    if len(candidates) != 1 and participant.short_name:
        short = index.get(_name(participant.short_name), {})
        candidates = {key: item for key, item in short.items() if not candidates or key in candidates}
    if len(candidates) != 1:
        return None, "ambiguous_name" if candidates else "unmatched_name"
    return next(iter(candidates.values())), "matched"


def _by_source_id(path: str, season: int | None, participant: Participant) -> tuple[tuple[dict, str] | None, str]:
    identity = participant.participant_id
    if not identity or not identity.isdigit():
        return None, "missing_source_id"
    historical = _core_team(path, season, identity) if season is not None else None
    if historical and _matches(participant, historical[0]):
        if source_logo(historical[0]):
            return historical, "matched"
    # The current Site endpoint is only safe when the source identity name still agrees.
    # It is never treated as a historical season roster.
    url = f"{SITE}/{path}/teams/{identity}"
    payload = _optional_json(url)
    current = payload.get("team") if payload else None
    if isinstance(current, dict) and str(current.get("id")) == identity and _name(participant.name) in _names(current):
        return (current, url), "matched"
    if historical and _matches(participant, historical[0]):
        return historical, "matched"
    return None, "identity_conflict" if historical or current else "unavailable_metadata"


def _apply(event: CalendarEvent, participant: Participant, logo: str, source_url: str, checked: str) -> None:
    for target in (participant, event.home_participant, event.away_participant):
        if target is not None and target.role == participant.role and target.name == participant.name:
            target.metadata.update(logo_url=logo, logo_source_url=source_url, logo_checked_date=checked)


def _identity(event: CalendarEvent, participant: Participant) -> tuple:
    return (
        event.league,
        event.source,
        event.season,
        participant.participant_id,
        participant.name,
        participant.short_name,
    )


def enrich_team_logos(events: list[CalendarEvent]) -> list[dict]:
    """Return private coverage observations; only source-linked image fields are added."""
    global _metadata_circuit
    if not _metadata_circuit.allows_request():
        for lookup in (_optional_json, _core_team, _season_teams, _name_index):
            lookup.cache_clear()
    _metadata_circuit = _LookupCircuit()
    checked = datetime.now(UTC).date().isoformat()
    observations = {}
    choices = {}
    supplied_images = {}
    for event in events:
        if event.sport in TEAM_SPORTS:
            for participant in event.participants:
                logo = espn_logo_url(participant.metadata.get("logo_url"))
                source_url = participant.metadata.get("logo_source_url")
                if logo and isinstance(source_url, str):
                    supplied_images[_identity(event, participant)] = (
                        logo,
                        source_url,
                        participant.metadata.get("logo_checked_date") or checked,
                    )
    for event in events:
        if event.sport not in TEAM_SPORTS:
            continue
        path = league_paths().get(event.league)
        season = competition_season(event)
        for participant in event.participants:
            if participant.entity_type not in {"team", "club", "national_team"}:
                continue
            key = _identity(event, participant)
            own_logo = espn_logo_url(participant.metadata.get("logo_url"))
            own_source = participant.metadata.get("logo_source_url")
            supplied = (
                (own_logo, own_source, participant.metadata.get("logo_checked_date") or checked)
                if own_logo and isinstance(own_source, str)
                else supplied_images.get(key)
            )
            if supplied:
                logo, source_url, source_checked = supplied
                _apply(event, participant, logo, source_url, source_checked)
                observations[key] = {
                    "league": event.league,
                    "season": event.season,
                    "participant_id": participant.participant_id,
                    "name": participant.name,
                    "status": "logo",
                    "logo_url": logo,
                    "source_url": source_url,
                }
                continue
            if key not in choices:
                if path is None:
                    match, reason = None, "unsupported_league"
                elif event.source == "espn":
                    match, reason = _by_source_id(path, season, participant)
                elif season is not None:
                    match, reason = _match_name(path, season, participant)
                else:
                    match, reason = None, "unknown_source_season"
                logo = source_logo(match[0]) if match else None
                choices[key] = (
                    logo,
                    match[1] if match else None,
                    "logo" if logo else "missing_image" if match else reason,
                )
            logo, source_url, reason = choices[key]
            if logo:
                _apply(event, participant, logo, source_url, checked)
            observations[key] = {
                "league": event.league,
                "season": event.season,
                "participant_id": participant.participant_id,
                "name": participant.name,
                "status": reason,
                "logo_url": logo,
                "source_url": source_url,
            }
    return list(observations.values())
