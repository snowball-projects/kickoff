"""Optional F1DB race/sprint podiums, joined to the pinned schedule source."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable, MutableMapping
from datetime import date

LOGGER = logging.getLogger(__name__)
RAW = "https://raw.githubusercontent.com/f1db/f1db"
BLOB = "https://github.com/f1db/f1db/blob"
RACE_PATH = re.compile(r"src/data/seasons/(\d{4})/races/\d{2}-[a-z0-9-]+")
IDENTITY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _fields(body: bytes, keys: set[str]) -> dict[str, str]:
    """Read selected top-level scalars; unrelated nested biography is private."""
    fields = {}
    for line in body.decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*):(?: (.*))?", line)
        if not match or match[1] not in keys:
            continue
        if match[1] in fields:
            raise ValueError("Duplicate F1DB scalar field")
        fields[match[1]] = match[2] or ""
    return fields


def _name(value: str) -> str:
    # F1DB uses scalar YAML names. Do not derive a display name from its ID.
    if value.startswith('"'):
        value = json.loads(value)
    elif value.startswith("'"):
        if not value.endswith("'") or len(value) < 2:
            raise ValueError("Unclosed F1DB name")
        value = value[1:-1].replace("''", "'")
    elif any(token in value for token in ("#", ": ", "[", "{", "&", "*", "!", "|", ">")):
        raise ValueError("Unsupported F1DB name scalar")
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError("Missing F1DB driver name")
    return value


def _podium(body: bytes) -> list[tuple[int, str]]:
    """Read F1DB's scalar classification rows; list/grid order is irrelevant."""
    rows: list[dict[str, str]] = []
    for line in body.decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(- |  )([A-Za-z][A-Za-z0-9]*):(?: (.*))?", line)
        if not match:
            raise ValueError("Unsupported F1DB classification row")
        prefix, key, value = match.groups()
        if prefix == "- ":
            if key != "position":
                raise ValueError("F1DB classification row lacks a position")
            rows.append({})
        if not rows or key in rows[-1]:
            raise ValueError("Duplicate or misplaced F1DB classification field")
        rows[-1][key] = value or ""
    ranked = {}
    for row in rows:
        position = row["position"]
        if not re.fullmatch(r"[1-9][0-9]*", position):
            continue  # Retirements / disqualifications are not a finishing rank.
        rank = int(position)
        if rank in ranked:
            raise ValueError("Duplicate F1DB finishing rank")
        ranked[rank] = row.get("driverId", "")
    if not {1, 2, 3}.issubset(ranked):
        raise ValueError("No complete explicit F1DB podium")
    podium = [(rank, ranked[rank]) for rank in (1, 2, 3)]
    if len({driver for _, driver in podium}) != 3 or any(not IDENTITY.fullmatch(d) for _, d in podium):
        raise ValueError("Missing or repeated F1DB podium driver")
    return podium


def load_f1_result(
    *,
    event_id: str,
    event_type: str,
    race_path: str,
    race_body: bytes,
    revision: str,
    checked_date: str,
    read_bytes: Callable[[str], bytes | None],
    driver_cache: MutableMapping[str, bytes | None] | None = None,
) -> dict | None:
    """Return a source-confirmed podium, or None without interrupting schedules.

    Pass the race directory and already-read race.yml bytes from the same pinned
    revision as the schedule. Share driver_cache across events/years in one run;
    exact revision URLs cache missing/failed driver reads too. checked_date is
    the actual date of these source reads, never the event's scheduled date.
    A result file's explicit 1/2/3 classification confirms this session's result;
    neither the calendar date nor a qualifying result is used as completion.
    """
    if event_type not in {"race", "sprint"}:
        return None
    cache = driver_cache if driver_cache is not None else {}
    try:
        path_match = RACE_PATH.fullmatch(race_path)
        if not path_match or not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError("Unpinned or invalid F1DB race path")
        date.fromisoformat(checked_date)
        fields = _fields(race_body, {"id", "date", "sprintRaceDate"})
        race_id = fields.get("id", "")
        suffix, filename, date_field = (
            ("race", "race-results.yml", "date")
            if event_type == "race"
            else ("sprintRace", "sprint-race-results.yml", "sprintRaceDate")
        )
        if not race_id.isdecimal() or event_id != f"f1db-{race_id}-{suffix}":
            raise ValueError("F1DB result does not match the schedule event")
        if str(date.fromisoformat(fields[date_field]).year) != path_match[1]:
            raise ValueError("F1DB result does not match the schedule year/session")
        result_path = f"{race_path}/{filename}"
        result_url = f"{RAW}/{revision}/{result_path}"
        body = read_bytes(result_url)
        if body is None:
            return None
        podium = _podium(body)
        rows = []
        inputs = [
            {"url": f"{RAW}/{revision}/{race_path}/race.yml", "sha256": hashlib.sha256(race_body).hexdigest()},
            {"url": result_url, "sha256": hashlib.sha256(body).hexdigest()},
        ]
        for rank, driver_id in podium:
            driver_url = f"{RAW}/{revision}/src/data/drivers/{driver_id}.yml"
            if driver_url not in cache:
                try:
                    cache[driver_url] = read_bytes(driver_url)
                except Exception:
                    cache[driver_url] = None
                    raise
            driver_body = cache[driver_url]
            if driver_body is None:
                return None
            driver = _fields(driver_body, {"id", "name"})
            if driver.get("id") != driver_id:
                raise ValueError("F1DB driver identity does not match its classification")
            rows.append({"rank": rank, "name": _name(driver["name"]), "participant_id": driver_id})
            inputs.append({"url": driver_url, "sha256": hashlib.sha256(driver_body).hexdigest()})
        return {
            "kind": "podium",
            "rows": rows,
            "source_url": f"{BLOB}/{revision}/{result_path}",
            "checked_date": checked_date,
            "sha256": hashlib.sha256(body).hexdigest(),
            "revision": revision,
            "inputs": inputs,
        }
    except Exception as error:
        LOGGER.warning("Optional F1DB result unavailable for %s: %s", event_id, error)
        return None
