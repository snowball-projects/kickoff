"""Public calendar inputs with explicit data licenses; separate from private fetches."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from sportsbro.models import CalendarEvent, Participant
from sportsbro.normalize import stable_event_id
from sportsbro.reviewed_schedules import load_reviewed_schedules
from sportsbro.semantics import classification_fields
from sportsbro.settings import Settings
from sportsbro.validation import validate_batch
from sportsbro.web import export_web_bundle

FOOTBALL = {
    "en.1": ("EPL", "Premier League", "England"),
    "de.1": ("BUNDESLIGA", "Bundesliga", "Germany"),
    "es.1": ("LA_LIGA", "La Liga", "Spain"),
    "it.1": ("SERIE_A", "Serie A", "Italy"),
    "fr.1": ("LIGUE_1", "Ligue 1", "France"),
    "en.2": ("CHAMPIONSHIP", "Championship", "England"),
    "nl.1": ("EREDIVISIE", "Eredivisie", "Netherlands"),
    "pt.1": ("PRIMEIRA_LIGA", "Primeira Liga", "Portugal"),
    "br.1": ("BRASILEIRAO", "Brazil Série A", "Brazil"),
}
SOURCES = [
    {
        "name": "openfootball contributors",
        "url": "https://github.com/openfootball/football.json",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
    },
    {
        "name": "F1DB and contributors",
        "url": "https://github.com/f1db/f1db",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
    },
]
REVIEWED_LABELS = {
    "IFSC_WORLD_CUP": "World Climbing stops",
    "NASCAR_CUP": "NASCAR Cup races",
    "INDYCAR": "IndyCar races",
    "IWF_WORLDS": "IWF Worlds span",
    "UFC": "UFC cards",
    "PFL": "PFL global cards",
    "RIZIN": "RIZIN cards",
    "ONE": "ONE Fight Night/Samurai cards",
    "BOXING_MAJOR": "selected boxing unification",
    "GOLF_MAJORS_MEN": "men's golf majors",
    "GOLF_MAJORS_WOMEN": "women's golf majors",
    "NFL": "selected NFL opener, international and holiday games (not the full schedule)",
}


def read_url(url: str) -> bytes:
    request = Request(
        url, headers={"User-Agent": "sportsbro-open-schedule/0.2 (https://github.com/snowball-projects/sportsbro)"}
    )
    with urlopen(request, timeout=40) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError(f"Source exceeds size limit: {url}")
    return data


def _event(
    *,
    event_id: str,
    source: str,
    sport: str,
    league: str,
    season: str,
    title: str,
    day: str,
    utc: str | None = None,
    event_type: str = "game",
    **kwargs,
) -> CalendarEvent:
    date.fromisoformat(day)
    if utc:
        datetime.fromisoformat(utc.replace("Z", "+00:00"))
    return CalendarEvent(
        event_id=event_id,
        source=source,
        sport=sport,
        league=league,
        season=season,
        title=title,
        event_type=event_type,
        calendar_date=day,
        end_calendar_date=day,
        start_time_utc=utc,
        start_time_local=None,
        timezone="UTC" if utc else None,
        subtitle=kwargs.pop("subtitle", None),
        status=kwargs.pop("status", "scheduled"),
        venue=kwargs.pop("venue", None),
        city=None,
        region=None,
        country=kwargs.pop("country", None),
        **classification_fields(kwargs.pop("competition_phase", "regular_season")),
        **kwargs,
    )


def football_events(payload: dict, key: str, season: str, source_url: str) -> list[CalendarEvent]:
    league, label, country = FOOTBALL[key]
    rows = payload.get("matches")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Missing matches: {key} {season}")
    events = []
    for row in rows:
        day = row.get("date")
        if not day or row.get("status", "").lower() in {"canceled", "cancelled", "postponed"}:
            # An old date on a canceled/postponed match is not a current appointment.
            continue
        home, away = row["team1"], row["team2"]
        score = row.get("score")
        full_time = score.get("ft") if isinstance(score, dict) else score
        finished = isinstance(full_time, list) and len(full_time) == 2 and all(isinstance(x, int) for x in full_time)
        events.append(
            _event(
                event_id=stable_event_id("openfootball", key, season, home, away, row.get("round")),
                source="openfootball",
                sport="soccer",
                league=league,
                season=season,
                title=f"{home} vs {away}",
                day=day,
                country=country,
                subtitle=row.get("round"),
                status="finished" if finished else "scheduled",
                competition_phase="postseason" if row.get("round") == "Playoffs" else "regular_season",
                participants=[Participant(name=home, role="home"), Participant(name=away, role="away")],
                home_participant=Participant(name=home, role="home"),
                away_participant=Participant(name=away, role="away"),
                source_url=source_url,
                tags=["football"],
                round_or_stage=row.get("round"),
            )
        )
    return events


def f1_fields(text: str) -> dict[str, str]:
    """Read only whitelisted scalar fields; fail on unsupported YAML syntax."""
    fields = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([A-Za-z0-9]+):\s*(.*)", line)
        if not match:
            continue
        key, value = match.groups()
        if key in {"id", "round", "date", "time", "grandPrixId", "circuitId"} or key.endswith(("Date", "Time")):
            if not re.fullmatch(r"[A-Za-z0-9:_-]+", value):
                raise ValueError(f"Unsupported F1 field: {key}")
            fields[key] = value
    return fields


def f1_events(text: str, year: int, source_url: str) -> list[CalendarEvent]:
    row = f1_fields(text)
    title = row["grandPrixId"].replace("-", " ").title() + " Grand Prix"
    sessions = [
        ("", "race", "Race"),
        ("freePractice1", "practice", "Practice 1"),
        ("freePractice2", "practice", "Practice 2"),
        ("freePractice3", "practice", "Practice 3"),
        ("qualifying", "qualifying", "Qualifying"),
        ("sprintQualifying", "qualifying", "Sprint qualifying"),
        ("sprintRace", "sprint", "Sprint"),
    ]
    events = []
    for prefix, kind, label in sessions:
        day, time = row.get(prefix + "Date" if prefix else "date"), row.get(prefix + "Time" if prefix else "time")
        if not day:
            continue
        utc = f"{day}T{time}:00Z" if time else None
        events.append(
            _event(
                event_id=f"f1db-{row['id']}-{prefix or 'race'}",
                source="f1db",
                sport="motorsport",
                league="F1",
                season=str(year),
                title=title if kind == "race" else f"{title} · {label}",
                day=day,
                utc=utc,
                event_type=kind,
                subtitle=f"Round {row['round']} · {label}",
                venue=row.get("circuitId", "").replace("-", " ").title() or None,
                source_url=source_url,
                tags=["f1", kind],
                round_or_stage=f"Round {row['round']}",
                status="past schedule" if day < datetime.now(timezone.utc).date().isoformat() else "scheduled",
            )
        )
    return events


def refresh_open_schedules(year: int, working_dir: Path, output_dir: Path, reviewed_dir: Path | None = None) -> Path:
    """Fetch at fixed upstream commits; export only approved source records."""
    working_dir.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    revisions = {}
    for repo, branch in [("openfootball/football.json", "master"), ("f1db/f1db", "main")]:
        revisions[repo] = json.loads(read_url(f"https://api.github.com/repos/{repo}/commits/{branch}"))["sha"]
    jobs = []
    for start in [year - 1, year]:
        season = f"{start}-{str(start + 1)[-2:]}"
        for key in FOOTBALL:
            if key == "br.1":
                continue
            path = f"{season}/{key}.json"
            jobs.append(
                (
                    "football",
                    key,
                    season,
                    path,
                    f"https://raw.githubusercontent.com/openfootball/football.json/{revisions['openfootball/football.json']}/{path}",
                )
            )
    path = f"{year}/br.1.json"
    jobs.append(
        (
            "football",
            "br.1",
            str(year),
            path,
            f"https://raw.githubusercontent.com/openfootball/football.json/{revisions['openfootball/football.json']}/{path}",
        )
    )
    f1dir = f"src/data/seasons/{year}/races"
    f1rev = revisions["f1db/f1db"]
    races = json.loads(read_url(f"https://api.github.com/repos/f1db/f1db/contents/{f1dir}?ref={f1rev}"))
    for item in races:
        if item["type"] == "dir":
            path = item["path"] + "/race.yml"
            jobs.append(("f1", "", str(year), path, f"https://raw.githubusercontent.com/f1db/f1db/{f1rev}/{path}"))
    if not races:
        raise ValueError("No F1 races returned")
    with ThreadPoolExecutor(max_workers=4) as pool:
        bodies = list(pool.map(lambda job: read_url(job[4]), jobs))
    events, evidence = [], []
    for job, body in zip(jobs, bodies, strict=True):
        kind, key, season, path, url = job
        digest = hashlib.sha256(body).hexdigest()
        raw = working_dir / "raw" / digest
        raw.parent.mkdir(exist_ok=True)
        raw.write_bytes(body)
        if kind == "football":
            src = f"https://github.com/openfootball/football.json/blob/{revisions['openfootball/football.json']}/{path}"
            parsed = football_events(json.loads(body), key, season, src)
        else:
            src = f"https://github.com/f1db/f1db/blob/{f1rev}/{path}"
            parsed = f1_events(body.decode(), year, src)
        events.extend(e for e in parsed if e.calendar_date and e.calendar_date.startswith(str(year)))
        evidence.append({"url": url, "sha256": digest, "parsed_events": len(parsed)})
    reviewed, notices, exclusions = load_reviewed_schedules(reviewed_dir or output_dir.parent / "reviewed", year)
    events.extend(reviewed)
    errors = validate_batch(events)
    if errors:
        raise ValueError("\n".join(errors))
    if not events:
        raise ValueError("Refusing to replace the calendar with an empty schedule")
    target = working_dir / "data" / "normalized" / str(year)
    target.mkdir(parents=True, exist_ok=True)
    (target / "all_events.json").write_text(json.dumps([e.to_dict() for e in events]))
    (target / "manifest.json").write_text(json.dumps({"providers": []}))
    bundle_path = export_web_bundle(Settings.load(working_dir), year, working_dir / "public")
    bundle = json.loads(bundle_path.read_text())
    bundle["updated_at"] = retrieved
    reviewed_counts = Counter(event.league for event in reviewed)
    reviewed_coverage = ", ".join(
        f"{count} {REVIEWED_LABELS[league]}" for league, count in sorted(reviewed_counts.items())
    )
    bundle["coverage"] = (
        f"{year}: nine football leagues and Formula 1. "
        + (
            f"Reviewed event dates: {reviewed_coverage}. See coverage details for inclusions and omissions. "
            if reviewed
            else ""
        )
        + "Community-maintained snapshots, not official or live feeds. Football kickoff times are withheld "
        "because the JSON does not explicitly declare their timezone. F1 times use the source's UTC fields."
    )
    bundle["sources"] = [
        {**source, "revision": revisions[repo]} for source, repo in zip(SOURCES, revisions, strict=True)
    ] + notices
    bundle["input_evidence"] = evidence
    bundle["exclusions"] = exclusions
    bundle["data_licenses"] = {
        "openfootball": "CC0 1.0",
        "f1db": "CC BY 4.0",
        "wikipedia": "CC BY-SA 4.0",
        "wikidata": "CC0 1.0",
    }
    bundle["data_license_notice"] = (
        "Software is MIT. Schedule data retains the per-source licenses listed here. "
        "Wikipedia-derived adaptations are shared under CC BY-SA 4.0, including in this collection. "
        "Source links identify the contributors and pinned revisions; changes are described in sources."
    )
    components = {}
    for kind in ("wikipedia", "wikidata"):
        selected = [event for event in bundle["events"] if event["source"] == kind]
        if not selected:
            continue
        component = {
            "schema_version": "1",
            "season": year,
            "license": bundle["data_licenses"][kind],
            "license_notice": bundle["data_license_notice"],
            "sources": [source for source in notices if source["kind"] == kind],
            "events": selected,
        }
        body = (json.dumps(component, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        name = f"{year}-{kind}-{hashlib.sha256(body).hexdigest()}.json"
        components[name] = body
    bundle["components"] = [
        {"path": name, "sha256": hashlib.sha256(body).hexdigest()} for name, body in components.items()
    ]
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=True, separators=(",", ":")) + "\n")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in components.items():
        component_path = output_dir / name
        component_path.with_suffix(".tmp").write_bytes(body)
        component_path.with_suffix(".tmp").replace(component_path)
    destination = output_dir / bundle_path.name
    destination.with_suffix(".tmp").write_bytes(bundle_path.read_bytes())
    destination.with_suffix(".tmp").replace(destination)
    return destination
