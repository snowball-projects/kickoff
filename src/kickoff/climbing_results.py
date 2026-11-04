"""Optional World Climbing podiums, scoped to reviewed final sessions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from kickoff.models import CalendarEvent


class _Canonical(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and "canonical" in (values.get("rel") or "").split():
            self.urls.append(values.get("href") or "")


def _event_url(value: str) -> str | None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in {"worldclimbing.com", "www.worldclimbing.com"}
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/events/[a-z0-9-]+/?", parsed.path)
    ):
        return None
    return "https://www.worldclimbing.com" + parsed.path.rstrip("/")


def _objects(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _records(text: str):
    # Next's public SSR payload is JSON, never executable source evaluated here.
    decoder = json.JSONDecoder()
    chunks = []
    for match in re.finditer(r"self\.__next_f\.push\(", text):
        value, _ = decoder.raw_decode(text[match.end() :])
        if isinstance(value, list) and len(value) == 2 and value[0] == 1 and isinstance(value[1], str):
            chunks.append(value[1])
    for line in "".join(chunks).splitlines():
        identity, separator, payload = line.partition(":")
        if not separator or not re.fullmatch(r"[0-9a-f]+", identity):
            continue
        # Import/reference/text records are not podium objects.
        if not payload.startswith(("[", "{")):
            continue
        yield json.loads(payload)


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _category(item: dict, url: str, checked_date: str, sha256: str) -> dict | None:
    identity = item.get("dcat_id")
    discipline, category = item.get("discipline_kind"), item.get("category_name")
    label, athletes = item.get("dcat_name"), item.get("athletes")
    if (
        not _positive_integer(identity)
        or discipline not in {"boulder", "lead", "speed", "speed_relay"}
        or not isinstance(category, str)
        or not category.strip()
        or not isinstance(label, str)
        or not label.strip()
        or not isinstance(athletes, list)
    ):
        return None
    rows = []
    identities = set()
    for athlete in athletes:
        if not isinstance(athlete, dict) or not _positive_integer(athlete.get("rank")):
            return None
        if athlete["rank"] > 3:
            continue
        country = athlete.get("country")
        country = country if isinstance(country, str) and re.fullmatch(r"[A-Z]{3}", country) else None
        athlete_id, first, last = athlete.get("athlete_id"), athlete.get("firstname"), athlete.get("lastname")
        if discipline == "speed_relay":
            # The official relay classification supplies national teams by NOC,
            # not athlete IDs/names. Keep that literal identity, never invent a
            # nation name, a squad ID, or individual relay members.
            if not country or athlete_id is not None or first is not None or last is not None:
                return None
            # Multiple unnamed national squads may share a country. Their
            # explicit different award ranks remain separate source facts.
            primary = (athlete["rank"], country)
            row = {"rank": athlete["rank"], "name": country, "country": country}
        else:
            if (
                not _positive_integer(athlete_id)
                or not isinstance(first, str)
                or not first.strip()
                or not isinstance(last, str)
                or not last.strip()
            ):
                return None
            primary = str(athlete_id)
            row = {"rank": athlete["rank"], "name": f"{first.strip()} {last.strip()}", "participant_id": primary}
            if country:
                row["country"] = country
        if primary in identities:
            return None
        identities.add(primary)
        rows.append(row)
    # Fewer rows cannot establish that all requested podium places were supplied.
    # Three or more preserves explicit shared ranks, including a tied third.
    if len(rows) < 3 or not any(row["rank"] == 1 for row in rows):
        return None
    return {
        "kind": "podium",
        "rows": sorted(rows, key=lambda row: row["rank"]),
        "source_url": url,
        "checked_date": checked_date,
        "sha256": sha256,
        "scope": {
            "event_url": url,
            "discipline": discipline,
            "category": " ".join(category.lower().split()),
            "category_id": str(identity),
            "label": label,
            "competitor_kind": "national_team" if discipline == "speed_relay" else "athlete",
        },
        "_complete": True,
        "_completion_evidence": "official_podium",
    }


def parse_climbing_podiums(body: bytes | None, *, source_url: str, checked_date: str) -> list[dict]:
    """Parse one public event overview once; absent/ambiguous sources return [].

    Only the canonical event's explicitly labelled SSR Podium section counts as
    result/completion evidence. Other rankings, array position, URL gender query,
    photos, old dates and a client-only Results shell are not result evidence.
    checked_date must be the actual source observation date supplied by caller.
    """
    try:
        url = _event_url(source_url)
        date.fromisoformat(checked_date)
        if not url or not body:
            return []
        text = body.decode("utf-8")
        canonical = _Canonical()
        canonical.feed(text)
        if len(canonical.urls) != 1 or _event_url(canonical.urls[0]) != url:
            return []
        sections = [
            item
            for record in _records(text)
            for item in _objects(record)
            if "d3-event-podium-athletes" in str(item.get("className", "")).split()
        ]
        if len(sections) != 1:
            return []
        props = [item for item in _objects(sections[0]) if item.get("headerTitle") == "The Podium" and "dcats" in item]
        if len(props) != 1 or not isinstance(props[0]["dcats"], list):
            return []
        digest = hashlib.sha256(body).hexdigest()
        result = []
        for item in props[0]["dcats"]:
            if isinstance(item, dict) and (podium := _category(item, url, checked_date, digest)) is not None:
                result.append(podium)
        return result
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
        # Optional malformed HTML/JSON must not interrupt schedule publication.
        return []


def _allocated_result(event: CalendarEvent, podiums: list[dict], allocation: dict) -> dict | None:
    scope_tags = {
        tag
        for tag in event.tags
        if tag in {"Boulder", "Lead", "Speed", "Men", "Women", "Para", "Youth"} or re.fullmatch(r"U[0-9]+", tag)
    }
    if (
        allocation.get("event_id") != event.event_id
        or allocation.get("event_title") != event.title
        or allocation.get("calendar_date") != event.calendar_date
        or _event_url(allocation.get("event_source_url", "")) != _event_url(event.source_url or "")
        or set(allocation.get("scope_tags", [])) != scope_tags
    ):
        return None
    expected = allocation.get("categories", [])
    expected_count = allocation.get("expected_category_count")
    if not isinstance(expected, list) or not expected or not _positive_integer(expected_count):
        return None
    identities = [row["category_id"] for row in expected]
    if len(identities) != len(set(identities)):
        return None
    selected = []
    url = _event_url(event.source_url or "")
    for category in expected:
        matches = [
            podium
            for podium in podiums
            if podium["scope"]["event_url"] == url
            and all(podium["scope"][key] == category[key] for key in ["category_id", "category", "discipline"])
        ]
        if len(matches) == 1:
            selected.append(matches[0])
    if not selected or len({(row["source_url"], row["checked_date"], row["sha256"]) for row in selected}) != 1:
        return None
    complete = (
        len(selected) == expected_count == len(expected)
        and allocation.get("allocation_complete") is True
        and all(row["_complete"] for row in selected)
    )
    source = selected[0]
    if expected_count == 1:
        result = dict(source)
    else:
        result = {
            "kind": "podiums",
            "categories": [{"label": row["scope"]["label"], "rows": row["rows"]} for row in selected],
            "source_url": source["source_url"],
            "checked_date": source["checked_date"],
            "sha256": source["sha256"],
            "scope": {
                "event_url": url,
                "category_ids": [row["scope"]["category_id"] for row in selected],
                "expected_category_count": expected_count,
            },
        }
    result.update(
        allocation_source=allocation["allocation_source"],
        _complete=complete,
        _completion_evidence="official_podium_and_reviewed_final_block",
    )
    return result


def climbing_result(event: CalendarEvent, podiums: list[dict], *, allocation: dict | None = None) -> dict | None:
    """Join exact source, final, discipline, gender and published youth age.

    A reviewed full-programme allocation may identify grouped final blocks.
    Without that separate primary-source proof, category-free/para blocks stay
    unallocated. Missing expected categories remain partial and refreshable;
    the result observation never rewrites the schedule's clocks/check dates.
    """
    if event.sport != "climbing" or event.event_type != "session" or event.round_or_stage != "final":
        return None
    if allocation is not None:
        return _allocated_result(event, podiums, allocation)
    if "Para" in event.tags or "Mixed Team" in event.title:
        return None
    disciplines = [tag.lower() for tag in event.tags if tag in {"Boulder", "Lead", "Speed"}]
    genders = [tag.lower() for tag in event.tags if tag in {"Men", "Women"}]
    ages = [tag.lower() for tag in event.tags if re.fullmatch(r"U[0-9]+", tag)]
    if len(disciplines) != 1 or len(ages) > 1 or ("Youth" in event.tags and not ages):
        return None
    discipline = disciplines[0]
    if re.search(r"\bspeed relay\b", event.title, re.IGNORECASE):
        if discipline != "speed":
            return None
        discipline = "speed_relay"
        if re.search(r"\bmixed\b", event.title, re.IGNORECASE) and set(genders) == {"men", "women"}:
            genders = ["mixed"]
    if len(genders) != 1:
        return None
    category = " ".join([*ages, genders[0]])
    url = _event_url(event.source_url or "")
    matches = [
        podium
        for podium in podiums
        if podium["scope"]["event_url"] == url
        and podium["scope"]["discipline"] == discipline
        and podium["scope"]["category"] == category
    ]
    return dict(matches[0]) if len(matches) == 1 else None
