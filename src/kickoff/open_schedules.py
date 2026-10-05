"""Public calendar inputs with explicit data licenses; separate from private fetches."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kickoff import feeds as league_feeds
from kickoff.dataset import event_from_dict
from kickoff.models import CalendarEvent, Participant
from kickoff.normalize import stable_event_id
from kickoff.reviewed_schedules import load_reviewed_schedules
from kickoff.semantics import classification_fields
from kickoff.settings import Settings
from kickoff.validation import validate_batch
from kickoff.web import export_web_bundle

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
# A feed that suddenly returns far fewer events than last time is treated as broken.
MIN_FEED_RATIO = 0.7


def read_url(url: str) -> bytes:
    request = Request(
        url, headers={"User-Agent": "kickoff-open-schedule/0.2 (https://github.com/snowball-projects/kickoff)"}
    )
    with urlopen(request, timeout=40) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError(f"Source exceeds size limit: {url}")
    return data


def read_optional(url: str) -> bytes | None:
    """Allow a 404 only for an input the caller knows may not be published yet."""
    try:
        return read_url(url)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def _published_input_paths(previous: dict | None, repository: str) -> set[str]:
    """Identify prior inputs across pinned revisions, including older bundles."""
    paths = set()
    prefixes = (
        f"https://raw.githubusercontent.com/{repository}/",
        f"https://github.com/{repository}/blob/",
    )
    for item in (previous or {}).get("input_evidence", []) + (previous or {}).get("events", []):
        url = item.get("url") or item.get("source_url") or ""
        for prefix in prefixes:
            if url.startswith(prefix):
                _revision, separator, path = url[len(prefix) :].partition("/")
                if separator:
                    paths.add(path)
    return paths


def _previous_bundle(path: Path) -> dict | None:
    try:
        bundle = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return bundle if isinstance(bundle, dict) and isinstance(bundle.get("events"), list) else None


def _stable_view(bundle: dict) -> dict:
    """Everything except retrieval times and input hashes, which change on every run."""
    view = {key: value for key, value in bundle.items() if key not in {"updated_at", "input_evidence"}}
    view["sources"] = [{k: v for k, v in source.items() if k != "retrieved_at"} for source in bundle.get("sources", [])]
    return view


def _restore(payload: dict) -> CalendarEvent:
    fields = {k: v for k, v in payload.items() if k not in {"home_participant_name", "away_participant_name"}}
    return event_from_dict(fields)


def collect_feed_events(
    year: int, feeds: dict, previous: dict | None, warnings: list[str]
) -> tuple[list[CalendarEvent], set[str]]:
    """Fetch each league independently; a failing or shrunken feed keeps its last published events."""
    old_by_league: dict[str, list[dict]] = {}
    for event in (previous or {}).get("events", []):
        if event.get("source") in league_feeds.SOURCES:
            old_by_league.setdefault(event["league"], []).append(event)
    events: list[CalendarEvent] = []
    fed_leagues: set[str] = set()
    for league, (_kind, fetch) in feeds.items():
        old = old_by_league.get(league, [])
        try:
            fresh = fetch(year)
        except Exception as error:  # noqa: BLE001 - any feed failure falls back the same way
            warnings.append(f"{league} {year}: fetch failed ({error}); kept {len(old)} previously published events")
            fresh = None
        if fresh is not None and old and len(fresh) < MIN_FEED_RATIO * len(old):
            warnings.append(
                f"{league} {year}: returned {len(fresh)} events, down from {len(old)}; kept the previous events"
            )
            fresh = None
        chosen = fresh if fresh is not None else [_restore(event) for event in old]
        if chosen:
            fed_leagues.add(league)
        events.extend(chosen)
    return events, fed_leagues


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


def refresh_open_schedules(
    year: int,
    working_dir: Path,
    output_dir: Path,
    reviewed_dir: Path | None = None,
    feeds: dict | None = None,
    warnings: list[str] | None = None,
) -> Path:
    """Fetch at fixed upstream commits; export only approved source records.

    `feeds` maps league -> (source kind, fetcher) for the scheduled league feeds.
    Problems that leave the previous data in place are appended to `warnings`.
    """
    warnings = warnings if warnings is not None else []
    previous = _previous_bundle(output_dir / f"{year}.json")
    published_football = _published_input_paths(previous, "openfootball/football.json")
    # Split-year inputs are shared by adjacent calendar snapshots. A first refresh
    # for this year must also preserve publication evidence from those snapshots.
    for adjacent_year in (year - 1, year + 1):
        adjacent = _previous_bundle(output_dir / f"{adjacent_year}.json")
        published_football.update(_published_input_paths(adjacent, "openfootball/football.json"))
    published_f1 = _published_input_paths(previous, "f1db/f1db")
    working_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    retrieved = now.isoformat(timespec="seconds")
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
    optional_f1 = year > now.year and not any(path.startswith(f"{f1dir}/") for path in published_f1)
    listing_url = f"https://api.github.com/repos/f1db/f1db/contents/{f1dir}?ref={f1rev}"
    listing = read_optional(listing_url) if optional_f1 else read_url(listing_url)
    races = json.loads(listing) if listing is not None else []
    for item in races:
        if item["type"] == "dir":
            path = item["path"] + "/race.yml"
            jobs.append(("f1", "", str(year), path, f"https://raw.githubusercontent.com/f1db/f1db/{f1rev}/{path}"))
    if not races and not optional_f1:
        raise ValueError("No F1 races returned")

    def fetch_input(job):
        kind, key, season, path, url = job
        # A split-year season may be unpublished early in its starting year;
        # Brazil's current calendar-year schedule and every listed F1 race are required.
        future_football = int(season[:4]) > now.year if key == "br.1" else int(season[:4]) >= now.year
        if kind == "football" and future_football and path not in published_football:
            return read_optional(url)
        return read_url(url)

    with ThreadPoolExecutor(max_workers=4) as pool:
        bodies = list(pool.map(fetch_input, jobs))
    events, evidence = [], []
    for job, body in zip(jobs, bodies, strict=True):
        kind, key, season, path, url = job
        if body is None:
            # Next season's file appears when upstream publishes it; coverage reflects its absence.
            continue
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
    fed, fed_leagues = collect_feed_events(year, feeds or {}, previous, warnings)
    events.extend(fed)
    reviewed, notices, exclusions = load_reviewed_schedules(reviewed_dir or output_dir.parent / "reviewed", year)
    # A full league feed supersedes the hand-reviewed selection for the same league.
    reviewed = [event for event in reviewed if event.league not in fed_leagues]
    kept_sources = {event.source_url for event in reviewed}
    notices = [notice for notice in notices if notice["url"] in kept_sources]
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
    fed_coverage = ", ".join(FEED_LABELS[league] for league in feeds or {} if league in fed_leagues)
    football_count = len({event["league"] for event in bundle["events"] if event["source"] == "openfootball"})
    open_coverage = [f"{football_count} football leagues"] if football_count else []
    open_coverage += ["Formula 1"] if any(event["source"] == "f1db" for event in bundle["events"]) else []
    bundle["coverage"] = (
        f"{year}: {' and '.join(open_coverage) or 'no open-data leagues yet'}. "
        + (
            f"Published schedules for {fed_coverage} from official league feeds and ESPN, checked weekly. "
            if fed_coverage
            else ""
        )
        + (
            f"Reviewed event dates: {reviewed_coverage}. See coverage details for inclusions and omissions. "
            if reviewed
            else ""
        )
        + "No live scores. Football league kickoff times are withheld "
        "because the JSON does not explicitly declare their timezone. F1 times use the source's UTC fields."
    )
    feed_kinds = sorted({event["source"] for event in bundle["events"]} & set(league_feeds.SOURCES))
    bundle["sources"] = (
        [{**source, "revision": revisions[repo]} for source, repo in zip(SOURCES, revisions, strict=True)]
        + [{**league_feeds.SOURCES[kind], "kind": kind} for kind in feed_kinds]
        + notices
    )
    bundle["input_evidence"] = evidence
    bundle["exclusions"] = exclusions
    bundle["data_licenses"] = {
        "openfootball": "CC0 1.0",
        "f1db": "CC BY 4.0",
        "wikipedia": "CC BY-SA 4.0",
        "wikidata": "CC0 1.0",
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
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=True, separators=(",", ":")) + "\n")
    destination = output_dir / bundle_path.name
    if previous is not None and _stable_view(previous) == _stable_view(bundle):
        # Unchanged schedules leave the published file alone, so quiet weeks make no commit.
        return destination
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in components.items():
        component_path = output_dir / name
        component_path.with_suffix(".tmp").write_bytes(body)
        component_path.with_suffix(".tmp").replace(component_path)
    destination.with_suffix(".tmp").write_bytes(bundle_path.read_bytes())
    destination.with_suffix(".tmp").replace(destination)
    # Superseded components stay recoverable from Git history.
    for stale in output_dir.glob(f"{year}-*.json"):
        if (
            re.fullmatch(rf"{year}-(?:wikipedia|wikidata)-[a-f0-9]{{64}}\.json", stale.name)
            and stale.name not in components
        ):
            stale.unlink()
    return destination
