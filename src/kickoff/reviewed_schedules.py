"""Small, explicitly reviewed schedule registries; never scrape them during a build."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from kickoff.models import CalendarEvent, Participant
from kickoff.semantics import COMPETITION_PHASES, classification_fields
from kickoff.timeutils import get_zoneinfo, isoformat_z
from kickoff.validation import validate_batch

LICENSES = {
    "en.wikipedia.org": ("wikipedia", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "www.wikidata.org": ("wikidata", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
}


# Owner-requested October 15 review: factual sessions from these two stops only.
CLIMBING_SOURCES = {
    "https://www.worldclimbing.com/events/world-climbing-series-salt-lake-city-2026": (
        "America/Denver",
        "2026-10-16",
        "2026-10-18",
        {"Boulder"},
    ),
    "https://www.worldclimbing.com/events/world-climbing-series-santiago-2026": (
        "America/Santiago",
        "2026-10-23",
        "2026-10-25",
        {"Lead", "Speed"},
    ),
}
CLIMBING_LICENSE = "Schedule facts; no data license granted"
CLIMBING_TERMS = "https://www.worldclimbing.com/terms-and-conditions/index"
WEIGHTLIFTING_LICENSE = "Schedule facts; no data license granted"
WEIGHTLIFTING_HOSTS = {
    "iwf.sport",
    "ewf.sport",
    "awf.sport",
    "www.commonwealthweightlifting.com",
    "www.imwla.com",
    "www.panamsports.org",
    "resources.cwg-qbr.pulselive.com",
    "results.asiangames2026.org",
    "drive.google.com",
}


def reviewed_events(payload: dict, year: int) -> tuple[list[CalendarEvent], list[dict]]:
    """Validate reviewed dates and the explicitly allowed official session clocks."""
    if payload.get("schema_version") != 1 or not payload.get("events") or not payload.get("sources"):
        raise ValueError("Invalid or empty reviewed registry")
    sources = {}
    for source in payload["sources"]:
        url = urlparse(source["url"])
        policy = LICENSES.get(url.netloc)
        official = source["url"] in CLIMBING_SOURCES
        if official:
            policy = ("world_climbing", CLIMBING_LICENSE, CLIMBING_TERMS)
        if source.get("kind") == "weightlifting" and url.netloc in WEIGHTLIFTING_HOSTS:
            official = True
            policy = ("weightlifting", WEIGHTLIFTING_LICENSE, source["url"])
        if not policy or url.scheme != "https":
            raise ValueError("Unreviewed registry source")
        kind, license_name, license_url = policy
        titles = parse_qs(url.query).get("title", [])
        if not official and (url.path != "/w/index.php" or len(titles) != 1):
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
        if not official and (not revision.isdigit() or parse_qs(url.query).get("oldid") != [revision]):
            raise ValueError("Registry source must pin its exact revision")
        if source["license"] != license_name or source["license_url"] != license_url:
            raise ValueError("Incorrect registry data license")
        if not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
            raise ValueError("Missing source SHA-256")
        if not source.get("changes") or not source.get("name"):
            raise ValueError("Missing attribution or transformation notice")
        if kind == "weightlifting":
            date.fromisoformat(source["checked_date"])
        elif datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00")).tzinfo is None:
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
        disciplines = row.get("disciplines", [])
        if not isinstance(disciplines, list) or any(d not in {"Boulder", "Lead", "Speed"} for d in disciplines):
            raise ValueError("Unknown climbing discipline")
        local = None
        zone = None
        gender_tags = []
        time_scope = row.get("start_time_scope", "event")
        if source["kind"] == "world_climbing":
            zone, first, last, allowed = CLIMBING_SOURCES[source["url"]]
            if (
                row["league"] != "IFSC_WORLD_CUP"
                or row["sport"] != "climbing"
                or row["event_type"] != "session"
                or len(disciplines) != 1
                or disciplines[0] not in allowed
            ):
                raise ValueError("Official climbing registry only accepts single-discipline sessions")
            if row.get("gender") not in {"men", "women"} or row.get("round_or_stage") not in {
                "qualification",
                "semi-final",
                "final",
            }:
                raise ValueError("Official climbing round needs one gender and a scheduled stage")
            gender_tags = [row["gender"].title()]
            if start != end or not first <= start.isoformat() <= last:
                raise ValueError("Official climbing session outside reviewed stop dates")
            if row.get("local_time") is not None:
                if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", row["local_time"]):
                    raise ValueError("Invalid climbing session clock")
                local = datetime.combine(start, time.fromisoformat(row["local_time"]), get_zoneinfo(zone))
            elif not row.get("notes"):
                raise ValueError("Unknown climbing time needs an explanation")
        elif source["kind"] == "weightlifting":
            if row["sport"] != "weightlifting":
                raise ValueError("Weightlifting source needs a weightlifting event")
            date.fromisoformat(row["checked_date"])
            zone = row["event_timezone"]
            get_zoneinfo(zone)
            if row.get("local_time") is not None:
                if start != end or row["event_type"] != "session":
                    raise ValueError("Weightlifting clock needs a single-day session")
                if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", row["local_time"]):
                    raise ValueError("Invalid weightlifting session clock")
                local = datetime.combine(start, time.fromisoformat(row["local_time"]), get_zoneinfo(zone))
            gender_tags = row.get("tags", [])
        elif row.get("local_time") is not None or time_scope != "event":
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
                start_time_utc=isoformat_z(local),
                start_time_local=local.isoformat() if local else None,
                timezone=zone if local or source["kind"] == "weightlifting" else None,
                start_time_scope=time_scope,
                status="past schedule" if end < datetime.now(timezone.utc).date() else "scheduled",
                venue=row.get("venue"),
                city=row.get("city"),
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
                round_or_stage=row.get("round_or_stage"),
                tags=(["session"] if row["event_type"] == "session" else ["event dates"])
                + disciplines
                + gender_tags
                + (["final date only"] if date_scope == "final_date" else []),
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
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("Duplicate event identity across reviewed registries")
    return events, sources, exclusions
