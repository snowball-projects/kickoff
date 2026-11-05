"""Publish trusted collector output as a metadata index and independent leagues."""

import json
import zlib
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
from html import escape
from pathlib import Path

from kickoff.reviewed_countries import country_source_kind
from kickoff.weightlifting_startlists import ENTRY_FIELDS


class PublishedWindow:
    """Copy old event dictionaries verbatim; unreadable league files rebuild in full."""

    def __init__(self, now, bundles=None):
        self.now = now
        self.cutoff = now.date() - timedelta(days=7)
        self.bundles = bundles or {}
        self.events = {e["event_id"]: e for b in self.bundles.values() for e in b["events"]}
        self.receipts = {}
        self.responses = {}
        self.f1_contexts = {}

    def since(self, league, year):
        return self.cutoff if (year, league) in self.bundles else date.min

    def old(self, row):
        return (row.get("end_calendar_date") or row["calendar_date"]) < self.cutoff.isoformat()

    def active(self, event, year):
        previous = self.events.get(event.event_id)
        return (
            not (previous is not None and self.old(previous))
            and (event.end_calendar_date or event.calendar_date) >= self.since(event.league, year).isoformat()
        )

    def restore_results(self, events):
        for event in events:
            previous = self.events.get(event.event_id) or {}
            if (
                (event.source == "f1db" or event.sport in {"climbing", "weightlifting"})
                and event.result is None
                and previous.get("result") is not None
            ):
                event.result = deepcopy(previous["result"])
                event.result_complete = event.result.get("complete", True)
                event.status = previous["status"]

    def merge(self, fresh, year):
        events = {
            e["event_id"]: e
            for e in fresh
            if not (e["event_id"] in self.events and self.old(self.events[e["event_id"]]))
        }
        for (season, _league), bundle in self.bundles.items():
            if season == year:
                events.update((e["event_id"], deepcopy(e)) for e in bundle["events"] if self.old(e))
        return sorted(
            events.values(),
            key=lambda e: (
                e["calendar_date"] or "9999-12-31",
                e.get("start_time_utc") is None,
                e.get("start_time_utc") or e.get("start_time_local") or "",
                e["league"],
                e["title"],
                e["event_id"],
            ),
        )


def load_published_window(read_bytes, now, read_many=None):
    window = PublishedWindow(now)
    try:
        manifest = json.loads(read_bytes("manifest.json"))
        if manifest["schema_version"] != "1":
            return window
        catalog = [(int(year), item) for year, season in manifest["seasons"].items() for item in season["sports"]]
        generations = {int(year): season["updated_at"] for year, season in manifest["seasons"].items()}
        names = [item["file"] for _year, item in catalog]
        if any("/" in name or "\\" in name or not name.endswith(".json") for name in names) or len(set(names)) != len(
            names
        ):
            return window
    except (OSError, ValueError, KeyError, TypeError, AttributeError, EOFError, zlib.error):
        return window
    if read_many is None:
        bodies = {}
        for name in names:
            try:
                bodies[name] = read_bytes(name)
            except (OSError, ValueError, KeyError, EOFError, zlib.error):
                pass
    else:
        try:
            bodies = read_many(names)
        except (OSError, ValueError, EOFError, zlib.error):
            return window
    for year, item in catalog:
        try:
            bundle = json.loads(bodies[item["file"]])
            events = bundle["events"]
            if (
                bundle["schema_version"] != "1"
                or bundle["season"] != year
                or bundle["sport"] != item["value"]
                or bundle["updated_at"] != generations[year]
                or len(events) != item["count"]
                or len({e["event_id"] for e in events}) != len(events)
                or {e["league"] for e in events} != set(item["leagues"])
            ):
                continue
            for event in events:
                date.fromisoformat(event.get("end_calendar_date") or event["calendar_date"])
            for league in item["leagues"]:
                window.bundles[year, league] = bundle
        except (OSError, ValueError, KeyError, TypeError, AttributeError, EOFError, zlib.error):
            continue
    window.events = {e["event_id"]: e for b in window.bundles.values() for e in b["events"]}
    return window


def facet(values):
    counts = Counter(value for value in values if value)
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def filters_for(bundle):
    events = bundle["events"]
    sports = {event["league"]: event["sport"] for event in events}
    return {
        "season": bundle["season"],
        "total_events": len(events),
        "available_seasons": bundle["available_seasons"],
        "leagues": [{**item, "sport": sports[item["value"]]} for item in facet(event["league"] for event in events)],
        "sports": facet(event["sport"] for event in events),
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")


def sport_evidence(receipts, kinds, events):
    identities = {event["event_id"] for event in events}
    leagues = {event["league"] for event in events}
    for receipt in receipts:
        if receipt.get("league") and receipt["league"] not in leagues:
            continue
        if receipt["kind"] not in kinds:
            continue
        fields = [
            key
            for key in ("clocks_added", "team_facts_added", "countries_added", "countries_withheld")
            if key in receipt
        ]
        if not fields:
            yield receipt
            continue
        selected = {key: [row for row in receipt[key] if row["event_id"] in identities] for key in fields}
        if any(selected.values()):
            yield {**receipt, **selected}


def publish_sports(bundles: list[dict], output: Path) -> Path:
    """Split already-validated facts; retain source-specific licenses and evidence."""
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("*.json"):
        old.unlink()
    manifest = {
        "schema_version": "1",
        "available_seasons": sorted(bundle["season"] for bundle in bundles),
        "seasons": {},
    }
    links = []
    for bundle in bundles:
        year = bundle["season"]
        groups = defaultdict(list)
        for event in bundle["events"]:
            sport = event["sport"]
            if sport == "weightlifting" and event.get("result") is not None:
                event = {
                    **event,
                    "participants": [p for p in event["participants"] if not any(key in p for key in ENTRY_FIELDS)],
                }
            group = f"{sport}-{event['league'].lower().replace('_', '-')}"
            groups[group].append(event)
        catalog = []
        for group, events in sorted(groups.items()):
            sport = events[0]["sport"]
            leagues = sorted({event["league"] for event in events})
            name = f"{year}-{group}.json"
            kinds = {event["source"] for event in events} | {event.get("start_time_source") for event in events}
            kinds.update(country_source_kind(event.get("country_source_url")) for event in events)
            identities = {event["event_id"] for event in events}
            kinds.update(
                receipt["kind"]
                for receipt in bundle["input_evidence"]
                if any(row["event_id"] in identities for row in receipt.get("countries_withheld", []))
            )
            kinds.update(
                p["country_source_kind"]
                for event in events
                for p in event["participants"]
                if p.get("country_source_kind")
            )
            if any(
                p.get(field, "").startswith(
                    (
                        "https://www.espn.com/",
                        "https://site.api.espn.com/",
                        "https://site.web.api.espn.com/",
                        "https://sports.core.api.espn.com/",
                    )
                )
                for event in events
                for p in event["participants"]
                for field in ("team_source_url", "logo_source_url")
            ):
                kinds.add("espn")
            payload = {
                "schema_version": "1",
                "season": year,
                "sport": sport,
                "updated_at": bundle["updated_at"],
                "events": events,
                "sources": [source for source in bundle["sources"] if source["kind"] in kinds],
                "data_licenses": {kind: license for kind, license in bundle["data_licenses"].items() if kind in kinds},
                "data_license_notice": bundle["data_license_notice"],
                "input_evidence": list(sport_evidence(bundle["input_evidence"], kinds, events)),
            }
            write_json(output / name, payload)
            catalog.append({"value": sport, "count": len(events), "file": name, "leagues": leagues})
            links.append(
                f'<li><a href="{escape(name)}">{year} · {escape(group)} · {len(events):,} events (JSON)</a></li>'
            )
        facets = filters_for(bundle)
        manifest["seasons"][str(year)] = {
            "season": year,
            "available_seasons": manifest["available_seasons"],
            "all_events": len(bundle["events"]),
            "updated_at": bundle["updated_at"],
            "sports": catalog,
            "leagues": facets["leagues"],
            "sources": bundle["sources"],
            "coverage": bundle["coverage"],
            "providers": bundle["providers"],
            "data_licenses": bundle["data_licenses"],
            "data_license_notice": bundle["data_license_notice"],
            "exclusions": bundle["exclusions"],
        }
    destination = output / "manifest.json"
    write_json(destination, manifest)
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; base-uri 'none'\">"
        "<title>kickoff schedule data</title><h1>kickoff schedule data</h1>"
        '<p><a href="manifest.json">Manifest, sources and licenses (JSON)</a> · '
        '<a href="../THIRD-PARTY-NOTICES.md">Licenses</a> · <a href="../">kickoff</a></p><ul>'
        + "".join(links)
        + "</ul></html>\n"
    )
    return destination
