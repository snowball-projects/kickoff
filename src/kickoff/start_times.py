"""Fill absent single-event clocks and team facts from the existing ESPN source.

Reviewed identities join sources exactly. Dates, existing clocks, spans and
unmatched records remain intact; an API date alone never establishes a time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import cache
from importlib.resources import files
from zoneinfo import ZoneInfo

from kickoff import feeds
from kickoff.models import CalendarEvent

logger = logging.getLogger(__name__)


@cache
def football_teams() -> dict:
    return json.loads(files("kickoff").joinpath("config/football-espn-teams.json").read_text())


@cache
def combat_identities() -> dict:
    payload = json.loads(files("kickoff").joinpath("config/combat-espn-events.json").read_text())
    return {row["event_id"]: row for row in payload["events"]}


def _confirmed_clock(row: dict, zone: str, day: str, *, card: bool = False) -> str | None:
    competitions = row.get("competitions") or []
    utc = feeds._iso_utc(row["date"])
    if card:
        # MMA cards contain one competition per bout, often split into prelims
        # and main-card blocks. Confirm the event header against its own block.
        competitions = [c for c in competitions if c.get("date") and feeds._iso_utc(c["date"]) == utc]
    if not competitions or (not card and len(competitions) != 1):
        return None
    competition = competitions[0]
    if competition.get("timeValid") is not True:
        return None
    for item in (row, competition):
        status = (item.get("status") or {}).get("type") or {}
        name = status.get("name", "")
        if name in feeds.DROPPED_STATUSES or name.startswith("STATUS_CANCEL"):
            return None
        if any("tbd" in str(status.get(key, "")).lower() for key in ("detail", "shortDetail")):
            return None
    if competition.get("date") and feeds._iso_utc(competition["date"]) != utc:
        return None
    return utc if feeds._local_date(utc, ZoneInfo(zone)) == day else None


def _team_pair(row: dict) -> tuple[str | None, str | None]:
    competitors = row["competitions"][0].get("competitors") or []
    home = [(c.get("team") or {}).get("id") for c in competitors if c.get("homeAway") == "home"]
    away = [(c.get("team") or {}).get("id") for c in competitors if c.get("homeAway") == "away"]
    return (home[0], away[0]) if len(home) == len(away) == 1 else (None, None)


@cache
def team_aliases() -> dict:
    return json.loads(files("kickoff").joinpath("config/espn-team-aliases.json").read_text())


def _same_day(event: CalendarEvent, row: dict, zone: str) -> bool:
    utc = feeds._iso_utc(row["date"])
    # Venue-local dates can differ from Eastern/UTC, particularly West Coast
    # baseball and World Cup games. An equal supplied instant is also exact.
    source_zone = ZoneInfo(zone)
    if event.start_time_local:
        local = datetime.fromisoformat(event.start_time_local)
        if local.tzinfo:
            source_zone = local.tzinfo
    return feeds._local_date(utc, source_zone) == event.calendar_date or bool(
        event.start_time_utc and feeds._iso_utc(event.start_time_utc) == utc
    )


def _soccer_identity(event: CalendarEvent) -> tuple | None:
    config = football_teams().get(event.league)
    if event.source != "openfootball" or not config or not (event.home_participant and event.away_participant):
        return None
    season = event.season
    if config["season_format"] == "start_year":
        parts = re.fullmatch(r"(\d{4})-(\d{2})", season)
        if not parts or int(parts[2]) != (int(parts[1]) + 1) % 100:
            return None
        year = int(parts[1])
    else:
        if not re.fullmatch(r"\d{4}", season):
            return None
        year = int(season)
    home = config["teams"].get(event.home_participant.name)
    away = config["teams"].get(event.away_participant.name)
    return (event.league, year, home, away) if home and away else None


def _hockey_identity(event: CalendarEvent) -> tuple | None:
    if event.source != "nhl" or not event.start_time_utc or not (event.home_participant and event.away_participant):
        return None
    names = team_aliases().get(event.league, {}).get("teams", {})
    pair = sorted(names.get(p.name, p.name) for p in (event.home_participant, event.away_participant))
    return (event.league, feeds._iso_utc(event.start_time_utc), *pair)


def fill_missing_start_times(events: list[CalendarEvent], year: int) -> list[dict]:
    """Return source receipts for independently missing clocks and team facts."""
    requests = defaultdict(list)
    primary_pairs = Counter(
        identity for event in events if (identity := _soccer_identity(event) or _hockey_identity(event))
    )
    identities = combat_identities()
    for event in events:
        if event.calendar_date != event.end_calendar_date or event.event_type not in {"game", "tournament"}:
            continue
        missing_clock = not (event.start_time_utc or event.start_time_local)
        missing_facts = event.event_type == "game" and any(
            p and (p.short_name is None or p.record is None) for p in (event.home_participant, event.away_participant)
        )
        if not (missing_clock or missing_facts):
            continue
        if event.source == "openfootball" and event.league in football_teams():
            path = football_teams()[event.league]["espn_path"]
            requests[f"{feeds.ESPN}/soccer/{path}/scoreboard?dates={year}&limit=1000"].append(event)
        elif event.source in {"mlb", "nhl"}:
            path = "baseball/mlb" if event.source == "mlb" else "hockey/nhl"
            month = event.calendar_date[:7].replace("-", "")
            requests[f"{feeds.ESPN}/{path}/scoreboard?dates={month}&limit=1000"].append(event)
        elif missing_clock and event.event_id in identities:
            requests[f"{feeds.ESPN}/mma/all/scoreboard?dates={year}&limit=1000"].append(event)
    receipts = []
    for url, selected in requests.items():
        try:
            receipt, updates = _lookup_clocks(url, selected, identities, primary_pairs)
        except Exception as error:
            # Optional third-party facts must never prevent publishing schedules.
            logger.warning("ESPN clock lookup failed; keeping source schedules unchanged: %s: %s", url, error)
            continue
        for item, fields in updates:
            for name, value in fields.items():
                setattr(item, name, value)
        receipts.append(receipt)
    return receipts


def _lookup_clocks(
    url: str, selected: list[CalendarEvent], identities: dict, primary_pairs: Counter
) -> tuple[dict, list]:
    """Stage a response before applying clocks, team facts or source credits."""
    payload = feeds.get_json(url)
    rows = feeds.rows(payload, "events")
    if len(rows) >= 1000:
        raise ValueError(f"Possibly truncated ESPN clock lookup: {url}")
    by_id, by_pair, by_names, by_unordered = (defaultdict(list) for _ in range(4))
    for row in rows:
        by_id[str(row["id"])].append(row)
        if len(row.get("competitions") or []) == 1:
            by_pair[_team_pair(row)].append(row)
            competitors = row["competitions"][0].get("competitors") or []
            home = [c.get("team", {}).get("displayName") for c in competitors if c.get("homeAway") == "home"]
            away = [c.get("team", {}).get("displayName") for c in competitors if c.get("homeAway") == "away"]
            if len(home) == len(away) == 1:
                by_names[(home[0], away[0])].append(row)
                by_unordered[frozenset((home[0], away[0]))].append(row)
    changes, team_changes, updates = [], [], []
    for event in selected:
        if event.source == "openfootball":
            config = football_teams()[event.league]
            teams = config["teams"]
            home = teams.get(event.home_participant.name) if event.home_participant else None
            away = teams.get(event.away_participant.name) if event.away_participant else None
            zone = config["timezone"]
            pair = by_pair[(home, away)] if home and away else []
            candidates = [row for row in pair if _same_day(event, row, zone)]
            # A rescheduled domestic league game still has one exact paired
            # team identity in its season. Use it for team facts only; clock
            # confirmation below still requires the original source day.
            identity = _soccer_identity(event)
            if (
                not candidates
                and identity
                and primary_pairs[identity] == 1
                and event.league != "FIFA_WORLD_CUP"
                and event.competition_phase == "regular_season"
            ):
                candidates = [row for row in pair if (row.get("season") or {}).get("year") == identity[1]]
        elif event.source in {"mlb", "nhl"}:
            zone = "America/New_York"
            names = team_aliases().get(event.league, {}).get("teams", {})
            home = (
                names.get(event.home_participant.name, event.home_participant.name) if event.home_participant else None
            )
            away = (
                names.get(event.away_participant.name, event.away_participant.name) if event.away_participant else None
            )
            candidates = [row for row in by_names[(home, away)] if home and away and _same_day(event, row, zone)]
            identity = _hockey_identity(event)
            if not candidates and identity and primary_pairs[identity] == 1:
                # Neutral NHL games can disagree about home/away. Exact
                # teams and an equal known instant identify the same game;
                # facts below attach by team identity, preserving source roles.
                candidates = [
                    row
                    for row in by_unordered[frozenset((home, away))]
                    if row["competitions"][0].get("neutralSite") is True and feeds._iso_utc(row["date"]) == identity[1]
                ]
            number = event.raw_source_payload.get("game_number")
            numbered = [
                (
                    row,
                    {
                        int(match)
                        for note in row["competitions"][0].get("notes", [])
                        for match in re.findall(r"\bDoubleheader - Game (\d+)\b", note.get("headline", ""))
                    },
                )
                for row in candidates
            ]
            # A missing sibling must not turn the wrong numbered game into
            # a unique match. Missing clocks still require matching explicit
            # game numbers, even for a single doubleheader candidate.
            if event.source == "mlb" and (
                len(candidates) > 1
                or event.raw_source_payload.get("double_header") in {"Y", "S"}
                or number not in (None, 1)
                or any(numbers for _, numbers in numbered)
            ):
                candidates = [row for row, numbers in numbered if number and numbers == {number}]
                if not candidates and event.start_time_utc:
                    # ESPN sometimes omits doubleheader numbers. An exact
                    # existing primary instant distinguishes the two games
                    # for facts without guessing or filling a missing clock.
                    candidates = [
                        row
                        for row, numbers in numbered
                        if not numbers and feeds._iso_utc(row["date"]) == feeds._iso_utc(event.start_time_utc)
                    ]
        else:
            identity = identities[event.event_id]
            zone = identity["timezone"]
            candidates = by_id[identity["espn_id"]] if identity["league"] == event.league else []
        if len(candidates) != 1:
            continue
        row = candidates[0]
        statuses = [
            ((item.get("status") or {}).get("type") or {}).get("name", "") for item in (row, row["competitions"][0])
        ]
        if any(status in feeds.DROPPED_STATUSES or status.startswith("STATUS_CANCEL") for status in statuses):
            continue
        source_url = feeds._espn_link(row, url)
        if event.source in {"openfootball", "mlb", "nhl"}:
            competitors = row["competitions"][0].get("competitors") or []
            added = False
            for competitor in competitors:
                role = competitor.get("homeAway")
                participant = (
                    event.home_participant if role == "home" else event.away_participant if role == "away" else None
                )
                if event.source == "nhl":
                    names = team_aliases().get(event.league, {}).get("teams", {})
                    name = (competitor.get("team") or {}).get("displayName")
                    participant = next(
                        (
                            p
                            for p in (event.home_participant, event.away_participant)
                            if p and names.get(p.name, p.name) == name
                        ),
                        None,
                    )
                if participant is None:
                    continue
                short = (competitor.get("team") or {}).get("shortDisplayName")
                record = feeds._espn_record(competitor, event.sport)
                facts = {}
                if participant.short_name is None and isinstance(short, str) and short.strip():
                    facts["short_name"] = short
                if participant.record is None and record is not None:
                    facts["record"] = record
                if facts:
                    facts["team_source_url"] = source_url
                    peers = [participant] + [
                        p for p in event.participants if p.role == participant.role and p is not participant
                    ]
                    updates.extend((peer, facts) for peer in peers)
                    added = True
            if added:
                team_changes.append({"event_id": event.event_id, "team_source_url": source_url})
                updates.append((event, {"facts_checked_date": datetime.now(UTC).date().isoformat()}))
        if event.start_time_utc or event.start_time_local:
            continue
        utc = _confirmed_clock(row, zone, event.calendar_date, card=event.event_id in identities)
        if utc is None:
            continue
        changes.append(
            {"event_id": event.event_id, "schedule_source_url": event.source_url, "time_source_url": source_url}
        )
        # The original schedule and its licence still cover titles, dates
        # and venues. Attribute the separately supplied clock to ESPN.
        updates.append(
            (
                event,
                {
                    "start_time_source": "espn",
                    "start_time_source_url": source_url,
                    "start_time_utc": utc,
                    "start_time_local": datetime.fromisoformat(utc.replace("Z", "+00:00"))
                    .astimezone(ZoneInfo(zone))
                    .isoformat(),
                    "timezone": zone,
                },
            )
        )
    receipt = {
        "url": url,
        "checked_date": datetime.now(UTC).date().isoformat(),
        "canonical_json_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "parsed_events": len(rows),
        "clocks_added": changes,
        "team_facts_added": team_changes,
    }
    return receipt, updates
