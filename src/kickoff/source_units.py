"""Observe source request membership before publication filters, without fetching."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from kickoff.refresh_state import SourceUnit


def unit_key(url: str) -> str:
    """HTTPS request identity; preserve repeated query values and all group filters."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError("Invalid source request URL")
    return urlunsplit(
        (
            "https",
            parts.netloc.lower(),
            parts.path,
            urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True))),
            "",
        )
    )


def _one(url: str, key: str) -> str | None:
    values = [value for name, value in parse_qsl(urlsplit(url).query, keep_blank_values=True) if name == key]
    if len(values) > 1:
        raise ValueError(f"Ambiguous {key} request parameter")
    return values[0] if values else None


def _rows(payload: dict, key: str) -> list[dict]:
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get(key), list)
        or not all(isinstance(row, dict) for row in payload[key])
    ):
        raise ValueError(f"Missing or invalid {key} collection")
    return payload[key]


def _time(value: str) -> datetime:
    if "T" not in value:
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source boundary must include timezone")
    return parsed


def _civil_bounds(prefix: str | None) -> tuple[str | None, str | None]:
    if prefix is None or not prefix.isdigit() or len(prefix) not in {4, 6, 8}:
        return None, None
    year = int(prefix[:4])
    if len(prefix) == 4:
        return f"{year:04}-01-01", f"{year + 1:04}-01-01"
    month = int(prefix[4:6])
    start = date(year, month, int(prefix[6:8]) if len(prefix) == 8 else 1)
    end = start + timedelta(days=1) if len(prefix) == 8 else date(year + month // 12, month % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def _score(value) -> bool:
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    return bool(isinstance(value, str) and re.fullmatch(r"\d+", value)) or (
        type(value) in {int, float} and value >= 0 and float(value).is_integer()
    )


def _named(name) -> bool:
    return (
        isinstance(name, str)
        and bool(name.strip())
        and name.strip().casefold() not in {"tba", "tbd", "tbc", "unknown", "undecided"}
    )


def _membership(rows: list[dict], prefix: str, id_field: str, classify) -> tuple[tuple[str, ...], dict[str, str]]:
    ids = []
    unresolved = {}
    seen = set()
    for row in rows:
        identity = row.get(id_field)
        if not isinstance(identity, (str, int)) or isinstance(identity, bool) or not str(identity):
            raise ValueError(f"Missing source {id_field}")
        key = f"{prefix}{identity}"
        if key in seen:
            unresolved[key] = "duplicate_source_id"
        else:
            ids.append(key)
            seen.add(key)
        status = classify(row)
        if status and key not in unresolved:
            unresolved[key] = status
    return tuple(ids), unresolved


def _observed(url, now, ids, unresolved, start, end, complete, children=(), *, past_season_closed=False):
    if now.tzinfo is None:
        raise ValueError("Observation time must include timezone")
    historical = start is not None and end is not None and _time(start) <= _time(end) < now - timedelta(days=2)
    return SourceUnit(
        key=unit_key(url),
        source_url=url,
        observed_at=now.isoformat(),
        event_ids=ids,
        unresolved=unresolved,
        complete=complete,
        closed=complete and (historical or past_season_closed),
        children=children,
        start=start,
        end=end,
    )


def _espn_status(row: dict) -> str | None:
    competitions = row.get("competitions") or []
    if not isinstance(competitions, list) or not all(isinstance(c, dict) for c in competitions):
        raise ValueError("Invalid ESPN competitions")
    competition = competitions[0] if competitions else {}
    statuses = [(item.get("status") or {}).get("type") or {} for item in (row, competition)]
    names = [status.get("name", "") for status in statuses]
    dropped = next(
        (
            s
            for s in names
            if s.startswith("STATUS_CANCEL") or s in {"STATUS_POSTPONED", "STATUS_SUSPENDED", "STATUS_FORFEIT"}
        ),
        None,
    )
    if dropped:
        return dropped
    competitors = competition.get("competitors") or []
    if not isinstance(competitors, list) or not all(isinstance(c, dict) for c in competitors):
        raise ValueError("Invalid ESPN competitors")
    finished = any(
        s.get("completed") is True or s.get("name") in {"STATUS_FINAL", "STATUS_FULL_TIME"} for s in statuses
    )
    if not finished:
        return next((name for name in names if name), "status_unconfirmed")
    if len(competitors) != 2 or not all(_named((c.get("team") or {}).get("displayName")) for c in competitors):
        return "result_unconfirmed"
    if not all(_score(c.get("score")) for c in competitors):
        return "result_unconfirmed"
    return None


def _espn_calendar(payload: dict) -> tuple[list, dict]:
    leagues = payload.get("leagues") or []
    if not isinstance(leagues, list) or not all(isinstance(league, dict) for league in leagues):
        raise ValueError("Invalid ESPN leagues")
    league = leagues[0] if leagues else {}
    calendar = league.get("calendar") or []
    if not isinstance(calendar, list):
        raise ValueError("Invalid ESPN calendar")
    return calendar, league


def _weekly_bounds(url: str, payload: dict) -> tuple[str | None, str | None]:
    calendar, league = _espn_calendar(payload)
    requested_year = _one(url, "dates")
    season = payload.get("season") or league.get("season") or {}
    if str(season.get("year")) != requested_year:
        return None, None
    matches = [
        entry
        for phase in calendar
        if isinstance(phase, dict) and str(phase.get("value")) == _one(url, "seasontype")
        for entry in phase.get("entries") or []
        if str(entry.get("value")) == _one(url, "week")
    ]
    if len(matches) != 1:
        return None, None
    return matches[0].get("startDate"), matches[0].get("endDate")


def _ufl_children(url: str, payload: dict, events: list[dict]) -> tuple[str, ...]:
    calendar, _ = _espn_calendar(payload)
    children = []
    for phase in calendar:
        if not isinstance(phase, dict) or not isinstance(phase.get("entries", []), list):
            raise ValueError("Invalid UFL weekly calendar")
        for entry in phase.get("entries") or []:
            if (
                not isinstance(entry, dict)
                or not str(phase.get("value", "")).isdigit()
                or not str(entry.get("value", "")).isdigit()
            ):
                raise ValueError("Invalid UFL weekly calendar entry")
            parts = urlsplit(url)
            params = [(k, v) for k, v in parse_qsl(parts.query) if k not in {"seasontype", "week"}]
            params += [("seasontype", str(phase["value"])), ("week", str(entry["value"]))]
            children.append(unit_key(urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))))
    if events and not children:
        raise ValueError("Missing UFL weekly calendar entries")
    if len(set(children)) != len(children):
        raise ValueError("Duplicate UFL weekly calendar entries")
    return tuple(children)


def espn_unit(url: str, payload: dict | None, league: str, now: datetime) -> SourceUnit:
    """Civil dates use exclusive next-day/month/year end; week endpoints stay literal.

    UFL annual units require every calendar-listed supplemental week. Saturated
    date windows stay incomplete until the caller observes and attaches children.
    NBA's past requestedSeason proof can close a nonempty unbounded season only
    when every raw row has a complete, source-finished team result.
    """
    start, end = _civil_bounds(_one(url, "dates"))
    if payload is None:
        return _observed(url, now, (), {}, start, end, False)
    events = _rows(payload, "events")
    selected = [
        row for row in events if not (league in {"COLLEGE_FOOTBALL", "LPGA_TOUR", "MAJOR_LEAGUE_RUGBY"} and row == {})
    ]
    ids, unresolved = _membership(selected, f"espn-{league.lower()}-", "id", _espn_status)
    weekly = _one(url, "week") is not None
    if weekly:
        start, end = _weekly_bounds(url, payload)
    team_schedule = "/teams/" in urlsplit(url).path and urlsplit(url).path.endswith("/schedule")
    limit_value = _one(url, "limit")
    limit = int(limit_value) if limit_value is not None else None if team_schedule else 25
    if limit is not None and limit <= 0:
        raise ValueError("Invalid ESPN request limit")
    complete = limit is None or len(events) < limit
    children = ()
    if league == "UFL" and len(_one(url, "dates") or "") == 4 and not weekly:
        children = _ufl_children(url, payload, events)
        if children:
            complete = False  # caller finalizes only after every real child was observed
    past_season = False
    if team_schedule:
        requested = payload.get("requestedSeason") or {}
        current = payload.get("season") or {}
        expected_year, expected_type = _one(url, "season"), _one(url, "seasontype")
        correct = str(requested.get("year")) == expected_year and (
            expected_type is None or str(requested.get("type")) == expected_type
        )
        season = requested if correct else {}
        start, end = season.get("startDate"), season.get("endDate")
        if not (start and end):
            start = end = None
        past_season = bool(
            correct
            and type(current.get("year")) is int
            and type(requested.get("year")) is int
            and requested["year"] < current["year"]
            and events
            and not unresolved
        )
        if payload.get("next") or payload.get("nextPage") or payload.get("pagination"):
            complete = False
    return _observed(url, now, ids, unresolved, start, end, complete, children, past_season_closed=past_season)


def _mlb_status(game: dict) -> str | None:
    status = game.get("status") or {}
    detail = status.get("detailedState", "")
    if any(word in detail.casefold() for word in ("postpon", "cancel", "suspend")):
        return detail
    teams = game.get("teams") or {}
    sides = [teams.get(side) or {} for side in ("home", "away")]
    names = [(side.get("team") or {}).get("name") for side in sides]
    if not all(
        _named(name) and not any(word in name.casefold() for word in ("seed", "league champion")) for name in names
    ):
        return "undecided_opponents"
    if status.get("abstractGameState") != "Final" and detail not in {"Final", "Game Over"}:
        return detail or "status_unconfirmed"
    return None if all(_score(side.get("score")) for side in sides) else "result_unconfirmed"


def mlb_unit(url: str, payload: dict, now: datetime) -> SourceUnit:
    """Season civil-year bounds; explicit startDate/endDate are inclusive API dates."""
    days = _rows(payload, "dates")
    games = [game for day in days for game in _rows(day, "games")]
    ids, unresolved = _membership(games, "mlb-mlb-", "gamePk", _mlb_status)
    start, end = _civil_bounds(_one(url, "season"))
    if value := _one(url, "startDate"):
        start = date.fromisoformat(value).isoformat()
    if value := _one(url, "endDate"):
        end = (date.fromisoformat(value) + timedelta(days=1)).isoformat()
    complete = all(day.get("totalGames", len(day["games"])) == len(day["games"]) for day in days)
    complete = complete and payload.get("totalGames", len(games)) == len(games)
    return _observed(url, now, ids, unresolved, start, end, complete)


def _nhl_status(game: dict) -> str | None:
    if game.get("gameScheduleState") not in {None, "OK"}:
        return str(game["gameScheduleState"])
    if game.get("gameType") not in {2, 3}:
        return "outside_published_game_type"
    teams = [game.get(f"{side}Team") or {} for side in ("home", "away")]
    names = [(team.get("commonName") or {}).get("default") or team.get("abbrev") for team in teams]
    if not all(_named(name) for name in names):
        return "undecided_opponents"
    if game.get("gameState") not in {"FINAL", "OFF"}:
        return str(game.get("gameState") or "status_unconfirmed")
    return None if all(_score(team.get("score")) for team in teams) else "result_unconfirmed"


def nhl_unit(url: str, payload: dict, now: datetime) -> SourceUnit:
    """Actual gameWeek dates; nextStartDate is exclusive end/navigation, never a child."""
    days = _rows(payload, "gameWeek")
    dates = [date.fromisoformat(day["date"]) for day in days]
    games = [game for day in days for game in _rows(day, "games")]
    ids, unresolved = _membership(games, "nhl-nhl-", "id", _nhl_status)
    start = min(dates).isoformat() if dates else None
    end = (max(dates) + timedelta(days=1)).isoformat() if dates else None
    if payload.get("nextStartDate"):
        following = date.fromisoformat(payload["nextStartDate"])
        if dates and following > max(dates):
            end = following.isoformat()
        else:
            end = None  # no safe reusable advance cursor for inconsistent navigation
    complete = all(day.get("numberOfGames", len(day["games"])) == len(day["games"]) for day in days)
    complete = complete and payload.get("numberOfGames", len(games)) == len(games)
    return _observed(url, now, ids, unresolved, start, end, complete)
