"""Public calendar inputs with explicit data licenses; separate from private fetches."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kickoff import feeds as league_feeds
from kickoff.models import CalendarEvent, Participant
from kickoff.normalize import sort_events, stable_event_id
from kickoff.reviewed_schedules import CLIMBING_LICENSE, load_reviewed_schedules
from kickoff.semantics import classification_fields
from kickoff.timeutils import get_zoneinfo, isoformat_z
from kickoff.validation import validate_batch
from kickoff.web import SCHEMA_VERSION, _event_payload

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
FOOTBALL_TIMEZONES = {
    "en.1": "Europe/London",
    "de.1": "Europe/Berlin",
    "it.1": "Europe/Rome",
    "fr.1": "Europe/Paris",
    "pt.1": "Europe/Lisbon",
    "br.1": "America/Sao_Paulo",
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
    "IFSC_WORLD_CUP": "World Climbing stop/session records",
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
    "PGA_TOUR": "selected PGA Tour tournaments (mostly final dates only)",
    "LPGA_TOUR": "selected LPGA Tour final dates",
    "NFL": "selected NFL opener, international and holiday games (not the full schedule)",
}
FEED_LABELS = {
    "NFL": "NFL",
    "NBA": "NBA",
    "MLB": "MLB",
    "NHL": "NHL",
    "UEFA_CHAMPIONS_LEAGUE": "UEFA Champions League",
    "PGA_TOUR": "PGA Tour",
    "UFC": "UFC",
    "NASCAR_CUP": "NASCAR Cup",
    "INDYCAR": "IndyCar",
}


def read_url(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "kickoff (https://github.com/snowball-projects/kickoff)"})
    with urlopen(request, timeout=40) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError(f"Source exceeds size limit: {url}")
    return data


def read_optional(url: str) -> bytes | None:
    """Only an unpublished season's 404 is optional; every other error propagates."""
    try:
        return read_url(url)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def _check_feed(events: list[CalendarEvent], year: int, league: str, kind: str) -> None:
    if not isinstance(events, list):
        raise ValueError("Feed did not return an event list")
    errors = validate_batch(events)
    for event in events:
        if (
            event.league != league
            or event.source != kind
            or not (
                (event.calendar_date or "").startswith(str(year))
                or (event.end_calendar_date or "").startswith(str(year))
            )
        ):
            errors.append(f"Unexpected event in {league} {year}: {event.event_id}")
        if not isinstance(event.tags, list) or any(not isinstance(tag, str) for tag in event.tags):
            errors.append(f"Invalid tags: {event.event_id}")
        for stamp in (event.start_time_utc, event.start_time_local):
            if stamp and datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
                errors.append(f"Timestamp has no offset: {event.event_id}")
        if not event.source_url or not event.source_url.startswith("https://"):
            errors.append(f"Missing source link: {event.event_id}")
    if errors:
        raise ValueError("; ".join(errors))


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
    timezone_name = FOOTBALL_TIMEZONES.get(key)
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
        local = None
        if timezone_name and re.fullmatch(r"\d{2}:\d{2}", row.get("time") or ""):
            # Only a reviewed source clock can become an instant. Repeated or skipped
            # civil clocks stay date-only rather than choosing a DST interpretation.
            naive = datetime.fromisoformat(f"{day}T{row['time']}")
            zone = get_zoneinfo(timezone_name)
            candidate = naive.replace(tzinfo=zone)
            if (
                candidate.utcoffset() == naive.replace(tzinfo=zone, fold=1).utcoffset()
                and candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive
            ):
                local = candidate
        events.append(
            _event(
                event_id=stable_event_id("openfootball", key, season, home, away, row.get("round")),
                source="openfootball",
                sport="soccer",
                league=league,
                season=season,
                title=f"{home} vs {away}",
                day=day,
                utc=isoformat_z(local),
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
        if local:
            events[-1].start_time_local = local.isoformat()
            events[-1].timezone = timezone_name
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


def refresh_open_schedules(
    year: int,
    output_dir: Path,
    reviewed_dir: Path | None = None,
    feeds: dict | None = None,
    available_seasons: list[int] | None = None,
) -> Path:
    """Fetch all configured schedules and export; any feed failure aborts publication."""
    now = datetime.now(timezone.utc)
    retrieved = now.isoformat(timespec="seconds")
    events, evidence, source_notices = [], [], []

    def collect(league, kind, fetch):
        fresh, notices, inputs = fetch()
        _check_feed(fresh, year, league, kind)
        events.extend(fresh)
        evidence.extend(inputs)
        source_notices.extend(notices)

    revisions = {}
    for repo, branch in [("openfootball/football.json", "master"), ("f1db/f1db", "main")]:
        revision = json.loads(read_url(f"https://api.github.com/repos/{repo}/commits/{branch}"))["sha"]
        if not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError("Invalid upstream revision")
        revisions[repo] = revision

    def football(key):
        repo = "openfootball/football.json"
        revision = revisions[repo]
        paths = (
            [f"{year}/br.1.json"]
            if key == "br.1"
            else [f"{start}-{str(start + 1)[-2:]}/{key}.json" for start in (year - 1, year)]
        )
        result, inputs = [], []
        for path in paths:
            url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
            start = int(path[:4])
            # European seasons run July-June; Brazil uses the calendar year.
            current_start = now.year if key == "br.1" else now.year - (now.month < 7)
            body = read_optional(url) if start > current_start else read_url(url)
            if body is None:
                continue
            parsed = football_events(
                json.loads(body), key, path.split("/")[0], f"https://github.com/{repo}/blob/{revision}/{path}"
            )
            result.extend(e for e in parsed if e.calendar_date.startswith(str(year)))
            inputs.append({"url": url, "sha256": hashlib.sha256(body).hexdigest(), "parsed_events": len(parsed)})
        return result, [{**SOURCES[0], "revision": revision}], inputs

    for key, (league, _label, _country) in FOOTBALL.items():
        collect(league, "openfootball", lambda key=key: football(key))

    def formula_one():
        repo = "f1db/f1db"
        revision = revisions[repo]
        directory = f"src/data/seasons/{year}/races"
        url = f"https://api.github.com/repos/{repo}/contents/{directory}?ref={revision}"
        body = read_optional(url) if year > now.year else read_url(url)
        if body is None:
            return [], [], []
        listing = json.loads(body)
        if not isinstance(listing, list) or not listing:
            raise ValueError("No F1 races returned")
        result, inputs = [], []
        for item in listing:
            if item["type"] != "dir":
                continue
            path = item["path"] + "/race.yml"
            url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
            body = read_url(url)
            parsed = f1_events(body.decode(), year, f"https://github.com/{repo}/blob/{revision}/{path}")
            result.extend(e for e in parsed if e.calendar_date.startswith(str(year)))
            inputs.append({"url": url, "sha256": hashlib.sha256(body).hexdigest(), "parsed_events": len(parsed)})
        if not result:
            raise ValueError("No F1 races parsed")
        return result, [{**SOURCES[1], "revision": revision}], inputs

    collect("F1", "f1db", formula_one)
    for league, (kind, fetch) in (feeds or {}).items():

        def league_feed(fetch=fetch, kind=kind):
            return fetch(year), [{**league_feeds.SOURCES[kind], "kind": kind}], []

        collect(league, kind, league_feed)
    fed_leagues = {event.league for event in events if event.source in league_feeds.SOURCES}
    reviewed, notices, exclusions = load_reviewed_schedules(reviewed_dir or output_dir.parent / "reviewed", year)
    # A full league feed supersedes the hand-reviewed selection for the same league.
    reviewed = [event for event in reviewed if event.league not in fed_leagues]
    kept_sources = {event.source_url for event in reviewed}
    notices = [notice for notice in notices if notice["url"] in kept_sources]
    events.extend(reviewed)
    # Each input was validated where it was produced. Check only cross-feed identity here.
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("Duplicate event identity across feeds")
    if not events:
        raise ValueError("No events to publish")
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "season": year,
        "available_seasons": available_seasons or [year],
        "providers": [],
        "events": [_event_payload(e) for e in sort_events(events)],
    }
    bundle["updated_at"] = retrieved
    reviewed_counts = Counter(event.league for event in reviewed)
    reviewed_coverage = ", ".join(
        f"{count} {REVIEWED_LABELS[league]}" for league, count in sorted(reviewed_counts.items())
    )
    fed_coverage = ", ".join(FEED_LABELS[league] for league in feeds or {} if league in fed_leagues)
    football_count = len({event["league"] for event in bundle["events"] if event["source"] == "openfootball"})
    open_coverage = [f"{football_count} football leagues"] if football_count else []
    open_coverage += ["Formula 1"] if any(event["source"] == "f1db" for event in bundle["events"]) else []
    bundle["coverage"] = (
        f"{year}: {' and '.join(open_coverage) or 'no open-data leagues yet'}. "
        + (
            f"Published schedules for {fed_coverage} from official league feeds and ESPN, checked daily. "
            if fed_coverage
            else ""
        )
        + (
            f"Reviewed events: {reviewed_coverage}. See coverage details for inclusions and omissions. "
            if reviewed
            else ""
        )
        + "No live scores. Football kickoff times use confirmed league timezone conventions; "
        "unconfirmed or missing clocks remain date-only. F1 times use the source's UTC fields."
    )
    feed_kinds = sorted({event["source"] for event in bundle["events"]} & set(league_feeds.SOURCES))
    bundle["sources"] = list({json.dumps(s, sort_keys=True): s for s in source_notices + notices}.values())
    bundle["input_evidence"] = evidence
    bundle["exclusions"] = exclusions
    bundle["data_licenses"] = {
        "openfootball": "CC0 1.0",
        "f1db": "CC BY 4.0",
        "wikipedia": "CC BY-SA 4.0",
        "wikidata": "CC0 1.0",
        **({"world_climbing": CLIMBING_LICENSE} if any(s["kind"] == "world_climbing" for s in notices) else {}),
        **{kind: league_feeds.SOURCES[kind]["license"] for kind in feed_kinds},
    }
    bundle["data_license_notice"] = (
        "Software is MIT. Schedule data retains the per-source licenses listed here. "
        "League feed and ESPN schedule facts are attributed to their sources, which grant no data license; "
        "league and team names belong to their owners and kickoff is not affiliated with any league. "
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
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in components.items():
        (output_dir / name).write_bytes(body)
    destination = output_dir / f"{year}.json"
    destination.write_text(json.dumps(bundle, ensure_ascii=True, separators=(",", ":")) + "\n")
    return destination
