"""Static reviewed official start-list facts. Publication performs no source reads."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from kickoff.models import CalendarEvent, Participant

LOGGER = logging.getLogger(__name__)
START_LIST_LEAGUES = {
    "IWF_WORLDS",
    "IWF_JUNIOR_WORLDS",
    "WEIGHTLIFTING_EUROPE",
    "WEIGHTLIFTING_ASIA",
    "WEIGHTLIFTING_AFRICA",
    "WEIGHTLIFTING_PAN_AMERICA",
    "WEIGHTLIFTING_OCEANIA",
    "WEIGHTLIFTING_COMMONWEALTH_GAMES",
    "WEIGHTLIFTING_ASIAN_GAMES",
}
ENTRY_FIELDS = (
    "entry_total_kg",
    "start_list_category",
    "start_list_nation",
    "start_list_guest",
    "start_list_source_url",
    "start_list_checked_date",
)
Category = tuple[str, str, str]
SessionKey = frozenset[Category]
ROSTER_HASH_SCOPE = "canonical reviewed roster facts (sessions; sorted keys, compact ASCII JSON), not raw PDF bytes"


@dataclass(frozen=True)
class Entry:
    lot: str
    name: str
    nation: str
    weight: str
    total: int
    guest: bool = False


@dataclass
class Session:
    categories: SessionKey
    entries: list[Entry]
    issue: str | None = None


def catalog() -> dict:
    return json.loads(files("kickoff").joinpath("config/weightlifting-startlists.json").read_text())


def reviewed_categories(row: dict) -> SessionKey:
    return frozenset((c["gender"], c["weight_class"], c["group"]) for c in row["categories"])


def roster_hash(sessions: list[dict]) -> str:
    return hashlib.sha256(json.dumps(sessions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reviewed_start_book(book: dict, reviewed_dir: Path) -> tuple[list[Session], dict]:
    snapshot = json.loads((reviewed_dir / book["snapshot_file"]).read_text())
    if (snapshot["league"], snapshot["year"]) != (book["league"], book["year"]):
        raise ValueError("Reviewed roster has the wrong competition")
    if snapshot["hash_scope"] != ROSTER_HASH_SCOPE or snapshot["sha256"] != roster_hash(snapshot["sessions"]):
        raise ValueError("Reviewed roster canonical-fact hash does not match")
    datetime.fromisoformat(snapshot["checked_date"])
    parsed, lots = [], []
    for row in snapshot["sessions"]:
        key = reviewed_categories(row)
        entries = [Entry(**entry) for entry in row["entries"]]
        issue = row.get("issue")
        if issue is not None and (not isinstance(issue, str) or not issue.strip() or entries):
            raise ValueError("Withheld session needs an explicit issue and no invented entries")
        if (not entries and not issue) or len(entries) != row["athlete_count"]:
            raise ValueError("Reviewed roster athlete count does not match")
        if any(entry.total <= 0 or sum(weight == entry.weight for _, weight, _ in key) != 1 for entry in entries):
            raise ValueError("Reviewed athlete class or entry total contradicts session")
        parsed.append(Session(key, entries, issue))
        lots.extend(entry.lot for entry in entries)
    if len(parsed) != snapshot["session_count"] or len(lots) != snapshot["athlete_count"]:
        raise ValueError("Reviewed roster book counts do not match")
    if len(set(lots)) != len(lots) or len({row["event_id"] for row in snapshot["sessions"]}) != len(parsed):
        raise ValueError("Reviewed roster contains duplicate athletes or sessions")
    return parsed, snapshot


class StartListLoader:
    """Publish complete dated snapshots; missing/corrupt cohorts are omitted atomically."""

    def enrich(self, events: list[CalendarEvent], reviewed_dir: Path, year: int):
        specs = catalog()
        relevant = [
            book
            for book in specs["books"]
            if book["year"] == year
            and any(event.league == book["league"] and event.event_type == "session" for event in events)
        ]
        if not relevant:
            return [], []
        try:
            definitions = {
                row["id"]: row
                for row in json.loads((reviewed_dir / f"{year}-weightlifting.json").read_text())["events"]
            }
        except Exception as error:
            LOGGER.warning("Reviewed weightlifting session definitions unavailable: %s", error)
            return [], []
        sources, evidence = [], []
        for book in relevant:
            cohort = [event for event in events if event.league == book["league"] and event.event_type == "session"]
            try:
                parsed, snapshot = reviewed_start_book(book, reviewed_dir)
                if {row["event_id"] for row in snapshot["sessions"]} != {event.event_id for event in cohort}:
                    raise ValueError("Reviewed roster does not match every current session identity")
                by_category = {session.categories: session for session in parsed}
                keys = [reviewed_categories(definitions[event.event_id]) for event in cohort]
                if len(set(keys)) != len(keys) or set(keys) != by_category.keys():
                    raise ValueError("Start list does not match every reviewed session")
                url, checked, sha = snapshot["source_url"], snapshot["checked_date"], snapshot["sha256"]
                provenance = {
                    key: snapshot[key]
                    for key in (
                        "hash_scope",
                        "revision",
                        "collection_method",
                        "source_raw_sha256",
                        "source_raw_hash_scope",
                        "source_raw_checked_date",
                        "source_raw_session_count",
                        "source_raw_athlete_count",
                    )
                    if key in snapshot
                }
                replacements, omitted = [], []
                for event, key in zip(cohort, keys, strict=True):
                    session = by_category[key]
                    if session.issue:
                        omitted.append({"event_id": event.event_id, "reason": session.issue})
                        continue
                    participants = []
                    for entry in session.entries:
                        gender, weight, group = next(category for category in key if category[1] == entry.weight)
                        metadata = {
                            "entry_total_kg": entry.total,
                            "start_list_category": f"{'Women' if gender == 'women' else 'Men'}'s {weight} kg, Group {group}",
                            "start_list_nation": entry.nation,
                            "start_list_guest": entry.guest,
                            "start_list_source_url": url,
                            "start_list_checked_date": checked,
                        }
                        country = specs["country_codes"].get(entry.nation.upper())
                        if country:
                            metadata.update(
                                country_code=country["code"],
                                country_source_url=country["source_url"],
                                country_checked_date=country["checked_date"],
                            )
                        participants.append(
                            Participant(
                                name=entry.name,
                                participant_id=f"{book['league']}:{year}:{entry.lot}",
                                entity_type="athlete",
                                metadata=metadata,
                            )
                        )
                    replacements.append((event, participants))
                for event, participants in replacements:
                    event.participants = participants
                sources.append(
                    {
                        "kind": "weightlifting",
                        "name": book["name"],
                        "publisher": book["publisher"],
                        "url": url,
                        "license": "Schedule facts; no data license granted",
                        "license_url": url,
                        "checked_date": checked,
                        "sha256": sha,
                        **provenance,
                        "changes": "Factual athlete names, source nation codes and entry totals from reviewed official start lists; no birth dates or source pages copied.",
                    }
                )
                evidence.append(
                    {
                        "kind": "weightlifting",
                        "url": url,
                        "landing_url": book["landing_url"],
                        "sha256": sha,
                        "checked_date": checked,
                        **provenance,
                        "sessions": len(replacements),
                        "parsed_sessions": len(parsed),
                        "parsed_athletes": sum(len(session.entries) for session in parsed),
                        "omitted_sessions": omitted,
                        "athletes": sum(len(participants) for _, participants in replacements),
                    }
                )
            except Exception as error:
                LOGGER.warning("Optional reviewed weightlifting roster omitted for %s: %s", book["league"], error)
        return sources, evidence
