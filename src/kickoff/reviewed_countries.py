"""Offline, source-backed host countries for exact reviewed appointments."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from functools import cache
from importlib.resources import files
from urllib.parse import urlparse

from kickoff.countries import ISO_CODES

# Country facts only. These hosts are not permission to ingest other schedules.
HOSTS = {
    "espn": {"site.api.espn.com", "site.web.api.espn.com"},
    "motogp": {"www.motogp.com"},
    "fia_wec": {"www.fiawec.com"},
    "nba": {"pr.nba.com", "www.nba.com"},
    "indycar": {"www.indycar.com"},
    "uci": {"www.uci.org", "www.giroditalia.it", "www.letour.fr", "www.lavuelta.es"},
}


def country_source_kind(url: str | None) -> str | None:
    host = urlparse(url or "").netloc
    return next((kind for kind, hosts in HOSTS.items() if host in hosts), None)


@cache
def reviewed_country_facts() -> tuple[dict, dict]:
    payload = json.loads(files("kickoff").joinpath("config/event-countries.json").read_text())
    sources, facts = {}, {}
    for source in payload["sources"]:
        if source["kind"] not in HOSTS or source["kind"] in sources:
            raise ValueError("Invalid reviewed country source")
        sources[source["kind"]] = source
    for fact in payload["events"]:
        if fact["event_id"] in facts or fact["country"] not in ISO_CODES:
            raise ValueError("Invalid reviewed country identity")
        kind = country_source_kind(fact["source_url"])
        if kind not in sources or urlparse(fact["source_url"]).scheme != "https":
            raise ValueError("Unreviewed country proof host")
        start, end = date.fromisoformat(fact["start_date"]), date.fromisoformat(fact["end_date"])
        if (
            end < start
            or not fact["title"]
            or not fact.get("evidence")
            or not re.fullmatch(r"[a-f0-9]{64}", fact["sha256"])
        ):
            raise ValueError("Invalid reviewed country proof")
        date.fromisoformat(fact["checked_date"])
        facts[fact["event_id"]] = fact
    return sources, facts


def fill_reviewed_countries(events):
    """Fill missing countries only; moved/renamed fixtures need another review."""
    sources, facts = reviewed_country_facts()
    added, withheld = defaultdict(list), defaultdict(list)
    for event in events:
        fact = facts.get(event.event_id)
        if event.country or not fact:
            continue
        kind = country_source_kind(fact["source_url"])
        identity = (
            event.league,
            event.title,
            event.calendar_date,
            event.end_calendar_date or event.calendar_date,
            event.venue,
        )
        reviewed = tuple(fact[key] for key in ("league", "title", "start_date", "end_date", "venue"))
        if identity != reviewed:
            withheld[kind].append(
                {
                    **{key: fact[key] for key in ("event_id", "source_url", "checked_date", "sha256")},
                    "reason": "Appointment changed since country review",
                }
            )
            continue
        event.country = fact["country"]
        event.country_source_url = fact["source_url"]
        event.country_checked_date = fact["checked_date"]
        added[kind].append(
            {key: fact[key] for key in ("event_id", "country", "source_url", "checked_date", "sha256", "evidence")}
        )
    evidence = [
        {"kind": kind, "countries_added": added[kind], "countries_withheld": withheld[kind]}
        for kind in sorted(added.keys() | withheld.keys())
    ]
    return evidence, [sources[receipt["kind"]] for receipt in evidence]
