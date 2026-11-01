"""Publish trusted collector output as a metadata index and independent sports."""

import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path


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
    for receipt in receipts:
        if receipt["kind"] not in kinds:
            continue
        fields = [key for key in ("clocks_added", "team_facts_added") if key in receipt]
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
            groups[event["sport"]].append(event)
        catalog = []
        for sport, events in sorted(groups.items()):
            name = f"{year}-{sport}.json"
            kinds = {event["source"] for event in events} | {event.get("start_time_source") for event in events}
            kinds.update(
                p["country_source_kind"]
                for event in events
                for p in event["participants"]
                if p.get("country_source_kind")
            )
            if any(
                p.get("team_source_url", "").startswith(
                    ("https://www.espn.com/", "https://site.api.espn.com/", "https://site.web.api.espn.com/")
                )
                for event in events
                for p in event["participants"]
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
            catalog.append({"value": sport, "count": len(events), "file": name})
            links.append(
                f'<li><a href="{escape(name)}">{year} · {escape(sport)} · {len(events):,} events (JSON)</a></li>'
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
