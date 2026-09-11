"""Small, explicitly reviewed date registries; never scrape them during a build."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sportsbro.models import CalendarEvent, Participant
from sportsbro.semantics import COMPETITION_PHASES, classification_fields
from sportsbro.validation import validate_batch

LICENSES = {
    "en.wikipedia.org": ("wikipedia", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "www.wikidata.org": ("wikidata", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
}


def reviewed_events(payload: dict, year: int) -> tuple[list[CalendarEvent], list[dict]]:
    """Validate the publication boundary before converting inclusive calendar dates."""
    if payload.get("schema_version") != 1 or not payload.get("events") or not payload.get("sources"):
        raise ValueError("Invalid or empty reviewed registry")
    sources = {}
    for source in payload["sources"]:
        url = urlparse(source["url"])
        policy = LICENSES.get(url.netloc)
        if not policy or url.scheme != "https":
            raise ValueError("Unreviewed registry source")
        kind, license_name, license_url = policy
        titles = parse_qs(url.query).get("title", [])
        if url.path != "/w/index.php" or len(titles) != 1:
            raise ValueError("Registry source needs a pinned article or entity URL")
        if kind == "wikidata" and not re.fullmatch(r"Q[1-9][0-9]*", titles[0]):
            raise ValueError("Only structured Wikidata items carry the reviewed CC0 grant")
        if kind == "wikipedia" and titles[0].split(":", 1)[0].lower() in {
            "wikipedia",
            "file",
            "template",
            "user",
            "category",
            "mediawiki",
            "help",
            "talk",
            "portal",
            "draft",
        }:
            raise ValueError("Registry expects a Wikipedia article")
        revision = str(source["revision"])
        if not revision.isdigit() or parse_qs(url.query).get("oldid") != [revision]:
            raise ValueError("Registry source must pin its exact revision")
        if source["license"] != license_name or source["license_url"] != license_url:
            raise ValueError("Incorrect registry data license")
        if not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
            raise ValueError("Missing source SHA-256")
        if not source.get("changes") or not source.get("name"):
            raise ValueError("Missing attribution or transformation notice")
        if datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Source retrieval time needs an offset")
        if source["id"] in sources:
            raise ValueError("Duplicate registry source identity")
        sources[source["id"]] = {**source, "kind": kind}
    events = []
    for row in payload["events"]:
        source = sources[row["source_id"]]
        start, end = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
        if end < start or (end - start).days > 31:
            raise ValueError("Invalid reviewed event span")
        date_scope = row.get("date_scope", "span")
        if date_scope not in {"span", "final_date"} or (date_scope == "final_date" and start != end):
            raise ValueError("Invalid reviewed date scope")
        if any(row.get(key) for key in ("start_time_utc", "start_time_local", "timezone")):
            raise ValueError("Reviewed date registry cannot establish a clock time")
        phase = row.get("competition_phase", "regular_season")
        if phase not in COMPETITION_PHASES:
            raise ValueError("Unknown reviewed competition phase")
        if start.year > year or end.year < year:
            continue
        home, away = None, None
        if row["event_type"] == "game":
            if not row.get("home_team") or not row.get("away_team"):
                raise ValueError("Reviewed game needs both participants")
            home = Participant(name=row["home_team"], role="home")
            away = Participant(name=row["away_team"], role="away")
        events.append(
            CalendarEvent(
                event_id=row["id"],
                source=source["kind"],
                sport=row["sport"],
                league=row["league"],
                season=str(start.year),
                event_type=row["event_type"],
                title=row["title"],
                subtitle=row.get("notes"),
                start_time_utc=None,
                start_time_local=None,
                timezone=None,
                status="past schedule" if end < datetime.now(timezone.utc).date() else "scheduled",
                venue=row.get("venue"),
                city=None,
                region=None,
                country=row.get("country"),
                home_participant=home,
                away_participant=away,
                participants=[away, home] if home and away else [],
                calendar_date=start.isoformat(),
                end_calendar_date=end.isoformat(),
                source_url=source["url"],
                **classification_fields(
                    "championship" if row["league"] in {"IWF_WORLDS", "GOLF_MAJORS_MEN", "GOLF_MAJORS_WOMEN"} else phase
                ),
                tags=["event dates"] + (["final date only"] if date_scope == "final_date" else []),
            )
        )
    errors = validate_batch(events)
    if errors:
        raise ValueError("\n".join(errors))
    used = {event.source_url for event in events}
    return events, [source for source in sources.values() if source["url"] in used]


def load_reviewed_schedules(directory: Path, year: int) -> tuple[list[CalendarEvent], list[dict], list[dict]]:
    events, sources, exclusions = [], [], []
    for path in sorted(directory.glob(f"{year}-*.json")):
        payload = json.loads(path.read_text())
        parsed, notices = reviewed_events(payload, year)
        events.extend(parsed)
        sources.extend(notices)
        exclusions.extend(payload.get("exclusions", []))
    errors = validate_batch(events)
    if errors:
        raise ValueError("\n".join(errors))
    return events, sources, exclusions
