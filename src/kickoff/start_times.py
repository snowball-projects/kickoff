"""Fill absent single-event clocks from the calendar's existing ESPN source.

Reviewed identities join sources exactly. Dates, existing clocks, spans and
unmatched records remain intact; an API date alone never establishes a time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
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


def fill_missing_start_times(events: list[CalendarEvent], year: int) -> list[dict]:
    """Return source receipts, updating only independently confirmed missing clocks."""
    pending = [
        e
        for e in events
        if not (e.start_time_utc or e.start_time_local)
        and e.calendar_date == e.end_calendar_date
        and e.event_type in {"game", "tournament"}
        and "final date only" not in e.tags
    ]
    requests = defaultdict(list)
    identities = combat_identities()
    for event in pending:
        if event.source == "openfootball" and event.league in football_teams():
            path = football_teams()[event.league]["espn_path"]
            requests[f"{feeds.ESPN}/soccer/{path}/scoreboard?dates={year}&limit=1000"].append(event)
        elif event.source == "mlb":
            day = event.calendar_date.replace("-", "")
            requests[f"{feeds.ESPN}/baseball/mlb/scoreboard?dates={day}&limit=1000"].append(event)
        elif event.event_id in identities:
            requests[f"{feeds.ESPN}/mma/all/scoreboard?dates={year}&limit=1000"].append(event)
    receipts = []
    for url, selected in requests.items():
        try:
            receipt, updates = _lookup_clocks(url, selected, identities)
        except Exception as error:
            # Optional third-party clocks must never prevent publishing schedules.
            logger.warning("ESPN clock lookup failed; keeping source schedules unchanged: %s: %s", url, error)
            continue
        for event, fields in updates:
            for name, value in fields.items():
                setattr(event, name, value)
        receipts.append(receipt)
    return receipts


def _lookup_clocks(url: str, selected: list[CalendarEvent], identities: dict) -> tuple[dict, list]:
    """Stage a whole response before applying any clocks or source credits."""
    payload = feeds.get_json(url)
    rows = feeds.rows(payload, "events")
    if len(rows) >= 1000:
        raise ValueError(f"Possibly truncated ESPN clock lookup: {url}")
    by_id, by_pair = defaultdict(list), defaultdict(list)
    for row in rows:
        by_id[str(row["id"])].append(row)
        if len(row.get("competitions") or []) == 1:
            by_pair[_team_pair(row)].append(row)
    changes, updates = [], []
    for event in selected:
        if event.source == "openfootball":
            config = football_teams()[event.league]
            teams = config["teams"]
            home = teams.get(event.home_participant.name) if event.home_participant else None
            away = teams.get(event.away_participant.name) if event.away_participant else None
            zone = config["timezone"]
            candidates = [
                row
                for row in by_pair[(home, away)]
                if home and away and feeds._local_date(row["date"], ZoneInfo(zone)) == event.calendar_date
            ]
        elif event.source == "mlb":
            zone = "America/New_York"
            candidates = []
            for row in rows:
                competitions = row.get("competitions") or []
                if len(competitions) != 1:
                    continue
                competitors = competitions[0].get("competitors") or []
                home = [c.get("team", {}).get("displayName") for c in competitors if c.get("homeAway") == "home"]
                away = [c.get("team", {}).get("displayName") for c in competitors if c.get("homeAway") == "away"]
                if (
                    event.home_participant
                    and event.away_participant
                    and home == [event.home_participant.name]
                    and away == [event.away_participant.name]
                    and feeds._local_date(row["date"], ZoneInfo(zone)) == event.calendar_date
                ):
                    candidates.append(row)
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
            # a unique match. Either feed's doubleheader evidence requires
            # the same explicit game number, even for one candidate.
            if (
                len(candidates) > 1
                or event.raw_source_payload.get("double_header") in {"Y", "S"}
                or number not in (None, 1)
                or any(numbers for _, numbers in numbered)
            ):
                candidates = [row for row, numbers in numbered if number and numbers == {number}]
        else:
            identity = identities[event.event_id]
            zone = identity["timezone"]
            candidates = by_id[identity["espn_id"]] if identity["league"] == event.league else []
        if len(candidates) != 1:
            continue
        row = candidates[0]
        utc = _confirmed_clock(row, zone, event.calendar_date, card=event.event_id in identities)
        if utc is None:
            continue
        source_url = feeds._espn_link(row, url)
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
    }
    return receipt, updates
