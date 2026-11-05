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
from kickoff.refresh_metrics import request_family
from kickoff.results import allocate_weightlifting_medals
from kickoff.reviewed_countries import fill_reviewed_countries
from kickoff.reviewed_schedules import BOXING_LICENSE, CLIMBING_LICENSE, WEIGHTLIFTING_LICENSE, load_reviewed_schedules
from kickoff.semantics import classification_fields
from kickoff.start_times import fill_missing_start_times
from kickoff.team_logos import enrich_team_logos
from kickoff.timeutils import get_zoneinfo, isoformat_z
from kickoff.validation import validate_batch
from kickoff.web import SCHEMA_VERSION, _event_payload
from kickoff.weightlifting_startlists import StartListLoader
from kickoff.world_cup import SOURCE as WORLD_CUP_SOURCE
from kickoff.world_cup import world_cup_events

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
    "en.2": "Europe/London",
    "de.1": "Europe/Berlin",
    "nl.1": "Europe/Amsterdam",
    "es.1": "Europe/Madrid",
    "it.1": "Europe/Rome",
    "fr.1": "Europe/Paris",
    "pt.1": "Europe/Lisbon",
    "br.1": "America/Sao_Paulo",
}
SOURCES = [
    {
        "kind": "openfootball",
        "name": "openfootball contributors",
        "url": "https://github.com/openfootball/football.json",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
    },
    {
        "kind": "f1db",
        "name": "F1DB and contributors",
        "url": "https://github.com/f1db/f1db",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
    },
]
REVIEWED_LABELS = {
    "MOTOGP": "MotoGP races",
    "WEC": "World Endurance Championship races and published prologues",
    "TOUR_DE_FRANCE": "Tour de France stages",
    "GIRO_D_ITALIA": "Giro d'Italia stages or published dates",
    "VUELTA_A_ESPANA": "Vuelta a España stages or published dates",
    "UCI_WORLD_TOUR": "UCI World Tour one-day races",
    "DIAMOND_LEAGUE": "Diamond League meetings",
    "WORLD_ATHLETICS_CHAMPIONSHIPS": "World Athletics Championships dates",
    "IPL": "Indian Premier League matches",
    "CRICKET_WORLD_CUP": "Cricket World Cup fixtures",
    "FIFA_WOMENS_WORLD_CUP": "FIFA Women's World Cup fixture slots",
    "IFSC_WORLD_CUP": "World Climbing World Cup records",
    "IFSC_WORLDS": "World Climbing Championships",
    "IFSC_YOUTH_WORLDS": "World Climbing Youth Championships",
    "IFSC_PARA_WORLD_CUP": "Para Climbing World Cup records",
    "IFSC_PARA_WORLDS": "Para Climbing World Championships",
    "CLIMBING_EUROPE": "European climbing championships",
    "CLIMBING_ASIA": "Asian climbing championships",
    "CLIMBING_AFRICA": "African climbing championships",
    "CLIMBING_OCEANIA": "Oceania climbing championships",
    "CLIMBING_PAN_AMERICA": "Pan-American climbing championships",
    "CLIMBING_CONTINENTAL_CUP": "continental climbing series",
    "CLIMBING_YOUTH_CONTINENTAL_CUP": "continental youth climbing series",
    "CLIMBING_CHALLENGER": "World Climbing Challenger records",
    "CLIMBING_NATIONS_GRAND_FINALE": "World Climbing Nations Grand Finale",
    "CLIMBING_OLYMPIC_QUALIFIERS": "continental Olympic climbing qualifiers",
    "CLIMBING_ASIAN_GAMES": "Asian Games climbing records",
    "CLIMBING_ASIAN_BEACH_GAMES": "Asian Beach Games climbing records",
    "CLIMBING_EUROPEAN_GAMES": "European Games climbing dates",
    "CLIMBING_PAN_AM_GAMES": "Pan American Games climbing dates",
    "CLIMBING_SOUTH_AM_GAMES": "South American Games climbing records",
    "NASCAR_CUP": "NASCAR Cup races",
    "INDYCAR": "IndyCar races",
    "IWF_WORLDS": "senior weightlifting Worlds sessions",
    "IWF_JUNIOR_WORLDS": "Junior Worlds sessions",
    "IWF_YOUTH_WORLDS": "Youth Worlds sessions",
    "MASTERS_WORLDS": "Masters Worlds records",
    "WEIGHTLIFTING_EUROPE": "European weightlifting records",
    "WEIGHTLIFTING_ASIA": "Asian weightlifting records",
    "WEIGHTLIFTING_AFRICA": "African weightlifting records",
    "WEIGHTLIFTING_PAN_AMERICA": "Pan-American weightlifting records",
    "WEIGHTLIFTING_OCEANIA": "Oceania weightlifting records",
    "WEIGHTLIFTING_COMMONWEALTH_GAMES": "Commonwealth Games weightlifting sessions",
    "WEIGHTLIFTING_ASIAN_GAMES": "Asian Games weightlifting records",
    "WEIGHTLIFTING_PAN_AM_GAMES": "Pan Am Games weightlifting dates",
    "UFC": "UFC cards",
    "PFL": "PFL global cards",
    "RIZIN": "RIZIN cards",
    "ONE": "ONE Fight Night/Samurai cards",
    "BOXING_MAJOR": "reviewed full world title boxing bouts",
    "ZUFFA_BOXING": "Zuffa Boxing cards",
    "NFL": "selected NFL opener, international and holiday games (not the full schedule)",
}
FEED_LABELS = {
    "NFL": "NFL",
    "NBA": "NBA",
    "MLB": "MLB",
    "NHL": "NHL",
    "UEFA_CHAMPIONS_LEAGUE": "UEFA Champions League",
    "PGA_TOUR": "PGA Tour",
    "LPGA_TOUR": "LPGA Tour",
    "DP_WORLD_TOUR": "DP World Tour",
    "LIV_GOLF": "LIV Golf",
    "ATP": "ATP",
    "WTA": "WTA",
    **{league: label for league, (_, label) in league_feeds.RUGBY_LEAGUES.items()},
    "UFC": "UFC",
    "NASCAR_CUP": "NASCAR Cup",
    "INDYCAR": "IndyCar",
    "UEFA_EUROPA_LEAGUE": "UEFA Europa League",
    "UEFA_CONFERENCE_LEAGUE": "UEFA Conference League",
    "UEFA_NATIONS_LEAGUE": "UEFA Nations League",
    "MLS": "MLS",
    "WNBA": "WNBA",
    "NCAA_MENS_BASKETBALL": "Division I men's basketball",
    "NCAA_WOMENS_BASKETBALL": "Division I women's basketball",
    "COLLEGE_FOOTBALL": "FBS and FCS college football",
    **{league: label for league, (_, _, _, label) in league_feeds.ADDITIONAL_TEAM_LEAGUES.items()},
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
        events[-1].facts_checked_date = datetime.now(timezone.utc).date().isoformat()
        events[-1].facts_source_url = source_url
        if finished:
            events[-1].home_participant.final_score = full_time[0]
            events[-1].away_participant.final_score = full_time[1]
            events[-1].participants = [events[-1].home_participant, events[-1].away_participant]
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
        if key in {
            "id",
            "round",
            "date",
            "time",
            "grandPrixId",
            "circuitId",
            "countryId",
            "alpha2Code",
        } or key.endswith(("Date", "Time")):
            if not re.fullmatch(r"[A-Za-z0-9:_-]+", value):
                raise ValueError(f"Unsupported F1 field: {key}")
            fields[key] = value
    return fields


def f1_events(text: str, year: int, source_url: str, country: str | None = None) -> list[CalendarEvent]:
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
                country=country,
                sport="motorsport",
                league="F1",
                season=str(year),
                title=title if kind == "race" else f"{title} · {label}",
                day=day,
                utc=utc,
                event_type=kind,
                subtitle=f"Round {row['round']}",
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
    enrich_times: bool = False,
    start_list_loader: StartListLoader | None = None,
    window=None,
    result_loader=None,
) -> Path:
    """Fetch all configured schedules and export; primary feed failures abort publication."""
    now = window.now if window is not None else datetime.now(timezone.utc)
    retrieved = now.isoformat(timespec="seconds")
    events, evidence, source_notices = [], [], []

    def collect(league, kind, fetch):
        fresh, notices, inputs = fetch()
        _check_feed(fresh, year, league, kind)
        events.extend(fresh)
        evidence.extend({**item, "kind": kind} for item in inputs)
        source_notices.extend(notices)

    def file_receipt(url, body, count, league, observed):
        return {
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
            "parsed_events": count,
            "league": league,
            "checked_date": observed[:10],
        }

    def read_source(url, optional=False):
        if window is not None and url in window.responses:
            return window.responses[url]
        body = read_optional(url) if optional else read_url(url)
        if window is not None:
            window.responses[url] = body
        return body

    revisions = {}

    def revision_for(repo, branch):
        if repo not in revisions:
            revision = json.loads(read_source(f"https://api.github.com/repos/{repo}/commits/{branch}"))["sha"]
            if not re.fullmatch(r"[a-f0-9]{40}", revision):
                raise ValueError("Invalid upstream revision")
            revisions[repo] = revision
        return revisions[repo]

    def football(key):
        repo = "openfootball/football.json"
        paths = (
            [f"{year}/br.1.json"]
            if key == "br.1"
            else [f"{start}-{str(start + 1)[-2:]}/{key}.json" for start in (year - 1, year)]
        )
        result, inputs, notices = [], [], []
        for path in paths:
            if window is not None:
                end = date(int(path[:4]) + 1, 1 if key == "br.1" else 7, 1)
                if end < window.since(FOOTBALL[key][0], year):
                    continue
            revision = revision_for(repo, "master")
            url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
            start = int(path[:4])
            # European seasons run July-June; Brazil uses the calendar year.
            current_start = now.year if key == "br.1" else now.year - (now.month < 7)
            body = read_source(url, optional=start > current_start)
            observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if body is None:
                continue
            payload = json.loads(body)
            parsed = football_events(
                payload, key, path.split("/")[0], f"https://github.com/{repo}/blob/{revision}/{path}"
            )
            notices.append({**SOURCES[0], "revision": revision})
            result.extend(e for e in parsed if e.calendar_date.startswith(str(year)))
            inputs.append(file_receipt(url, body, len(parsed), FOOTBALL[key][0], observed))
        return result, notices, inputs

    for key, (league, _label, _country) in FOOTBALL.items():
        collect(league, "openfootball", lambda key=key: football(key))

    def world_cup():
        repo = "openfootball/worldcup.json"
        path = f"{year}/worldcup.json"
        if year % 4 != 2 or (window is not None and window.since("FIFA_WORLD_CUP", year) > date(year, 12, 31)):
            return [], [], []
        previous = (
            [e for e in window.events.values() if e["league"] == "FIFA_WORLD_CUP" and e["season"] == str(year)]
            if window is not None
            else []
        )
        if previous and all(window.old(e) for e in previous):
            return [], [], []
        revision = revision_for(repo, "master")
        url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
        # There is no men's World Cup in off years; a known edition's failure
        # must stop publication rather than silently remove the tournament.
        body = read_source(url)
        observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if body is None:
            return [], [], []
        parsed = world_cup_events(json.loads(body), year, f"https://github.com/{repo}/blob/{revision}/{path}")
        return (
            parsed,
            [{**WORLD_CUP_SOURCE, "revision": revision, "checked_date": now.date().isoformat()}],
            [file_receipt(url, body, len(parsed), "FIFA_WORLD_CUP", observed)],
        )

    collect("FIFA_WORLD_CUP", "openfootball", world_cup)

    def formula_one():
        repo = "f1db/f1db"
        directory = f"src/data/seasons/{year}/races"
        if window is not None and window.since("F1", year) > date(year, 12, 31):
            return [], [], []
        revision = revision_for(repo, "main")
        url = f"https://api.github.com/repos/{repo}/contents/{directory}?ref={revision}"
        body = read_source(url, optional=year > now.year)
        observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if body is None:
            return [], [], []
        listing = json.loads(body)
        if not isinstance(listing, list) or not listing:
            raise ValueError("No F1 races returned")
        result, inputs = [], []
        inputs.append(file_receipt(url, body, 0, "F1", observed))
        circuit_countries = {}
        countries = {}

        def metadata(path):
            url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
            body = read_source(url)
            metadata_observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
            inputs.append(file_receipt(url, body, 0, "F1", metadata_observed))
            return f1_fields(body.decode())

        def host_country(race):
            circuit = f1_fields(race).get("circuitId")
            if not circuit:
                return None
            if circuit not in circuit_countries:
                circuit_countries[circuit] = metadata(f"src/data/circuits/{circuit}.yml").get("countryId")
            country = circuit_countries[circuit]
            if not country:
                return None
            if country not in countries:
                code = metadata(f"src/data/countries/{country}.yml").get("alpha2Code")
                if code is not None and not re.fullmatch(r"[A-Z]{2}", code):
                    raise ValueError("Invalid F1 host country code")
                countries[country] = code
            return countries[country]

        for item in listing:
            if item["type"] != "dir":
                continue
            path = item["path"] + "/race.yml"
            if window is not None:
                previous = [
                    e for e in window.events.values() if e["league"] == "F1" and e["source_url"].endswith("/" + path)
                ]
                if previous and all(window.old(e) for e in previous):
                    continue
            url = f"https://raw.githubusercontent.com/{repo}/{revision}/{path}"
            body = read_source(url)
            race_observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
            parsed = f1_events(
                body.decode(), year, f"https://github.com/{repo}/blob/{revision}/{path}", host_country(body.decode())
            )
            if window is not None:
                window.f1_contexts.update(
                    {
                        e.event_id: {"race_path": item["path"], "race_body": body, "revision": revision}
                        for e in parsed
                        if e.event_type in {"race", "sprint"}
                    }
                )
            result.extend(e for e in parsed if e.calendar_date.startswith(str(year)))
            inputs.append(file_receipt(url, body, len(parsed), "F1", race_observed))
        return result, [{**SOURCES[1], "revision": revision}], inputs

    collect("F1", "f1db", formula_one)
    for league, (kind, fetch) in (feeds or {}).items():

        def league_feed(fetch=fetch, kind=kind):
            before = dict(window.receipts) if window is not None else {}
            fresh = fetch(year, window=window) if window is not None else fetch(year)
            inputs = (
                [receipt for key, receipt in window.receipts.items() if before.get(key) != receipt]
                if window is not None
                else []
            )
            return fresh, [{**league_feeds.SOURCES[kind], "kind": kind}], inputs

        collect(league, kind, league_feed)
    fed_leagues = {event.league for event in events if event.source in league_feeds.SOURCES}
    reviewed, notices, exclusions = load_reviewed_schedules(reviewed_dir or output_dir.parent / "reviewed", year)
    # A full league feed supersedes the hand-reviewed selection for the same league.
    reviewed = [event for event in reviewed if event.league not in fed_leagues]
    kept_sources = {event.source_url for event in reviewed}
    notices = [notice for notice in notices if notice["url"] in kept_sources]
    if start_list_loader is not None:
        start_sources, start_evidence = start_list_loader.enrich(
            reviewed,
            reviewed_dir or output_dir.parent / "reviewed",
            year,
        )
        notices.extend(start_sources)
        evidence.extend(start_evidence)
    events.extend(reviewed)
    if window is not None:
        events = [event for event in events if window.active(event, year)]
        window.restore_results(events)
    country_receipts, country_notices = fill_reviewed_countries(events)
    evidence.extend(country_receipts)
    source_notices.extend(country_notices)
    time_receipts = []
    if enrich_times:
        targets = events
        time_receipts = fill_missing_start_times(targets, year) if targets else []
        evidence.extend({**item, "kind": "espn"} for item in time_receipts)
        if any(receipt["clocks_added"] or receipt["team_facts_added"] for receipt in time_receipts):
            source_notices.append({**league_feeds.SOURCES["espn"], "kind": "espn"})
        enrich_team_logos(events)
    if result_loader is not None:
        with request_family("results pages"):
            result_sources, result_evidence = result_loader.enrich(
                events,
                year,
                reviewed_dir or output_dir.parent / "reviewed",
                f1_contexts=window.f1_contexts if window is not None else {},
                now=now,
                window=window,
            )
        notices.extend(result_sources)
        evidence.extend(result_evidence)
    # Each input was validated where it was produced. Check only cross-feed identity here.
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("Duplicate event identity across feeds")
    national_sources = league_feeds.espn_national_sources(events)
    source_notices.extend(national_sources)
    fresh_public = [_event_payload(e) for e in sort_events(events)]
    if any((event.get("result") or {}).get("kind") == "weightlifting" for event in fresh_public):
        definitions = json.loads(
            ((reviewed_dir or output_dir.parent / "reviewed") / f"{year}-weightlifting.json").read_text()
        )["events"]
        fresh_public = allocate_weightlifting_medals(fresh_public, definitions)
    merged_public = window.merge(fresh_public, year) if window is not None else fresh_public
    fed_leagues = {event["league"] for event in merged_public if event["source"] in league_feeds.SOURCES}
    if not merged_public:
        raise ValueError("No events to publish")
    retained_envelopes = []
    if window is not None:
        retained_envelopes = [
            b
            for (season, _league), b in window.bundles.items()
            if season == year and any(window.old(e) for e in b["events"])
        ]
        for previous in retained_envelopes:
            source_notices.extend(previous.get("sources", []))
            evidence.extend(previous.get("input_evidence", []))
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "season": year,
        "available_seasons": available_seasons or [year],
        "providers": [],
        "events": merged_public,
    }
    has_team_logos = any(p.get("logo_url") for event in bundle["events"] for p in event["participants"])
    if has_team_logos:
        source_notices.append({**league_feeds.SOURCES["espn"], "kind": "espn"})
    bundle["updated_at"] = retrieved
    reviewed_counts = Counter(event.league for event in reviewed)
    reviewed_coverage = ", ".join(
        f"{count} {REVIEWED_LABELS[league]}" for league, count in sorted(reviewed_counts.items())
    )
    fed_coverage = ", ".join(FEED_LABELS[league] for league in feeds or {} if league in fed_leagues)
    football_count = len(
        {
            event["league"]
            for event in bundle["events"]
            if event["source"] == "openfootball" and event["league"] != "FIFA_WORLD_CUP"
        }
    )
    open_coverage = [f"{football_count} football leagues"] if football_count else []
    if any(event["league"] == "FIFA_WORLD_CUP" for event in bundle["events"]):
        open_coverage.append("FIFA World Cup")
    open_coverage += ["Formula 1"] if any(event["source"] == "f1db" for event in bundle["events"]) else []
    bundle["coverage"] = (
        f"{year}: {' and '.join(open_coverage) or 'no open-data leagues yet'}. "
        + (
            f"Published schedules for {fed_coverage} from official league feeds and ESPN, refreshed with their sources; events older than seven days retain their published facts and check dates. "
            if fed_coverage
            else ""
        )
        + (
            f"Reviewed events: {reviewed_coverage}. See coverage details for inclusions and omissions. "
            if reviewed
            else ""
        )
        + "ESPN golf leaderboards appear in current/past agenda sections and event popups. Football kickoff times use confirmed league timezone conventions; "
        "ESPN fills independently confirmed missing clocks with its own attribution. "
        "Unconfirmed clocks remain date-only. World Cup clocks use explicit source UTC offsets. "
        "F1 times use the source's UTC fields."
    )
    feed_kinds = sorted(
        (
            {event["source"] for event in bundle["events"]}
            | {event.get("start_time_source") for event in bundle["events"]}
            | ({"espn"} if any(receipt["team_facts_added"] for receipt in time_receipts) else set())
            | ({"espn"} if has_team_logos else set())
        )
        & set(league_feeds.SOURCES)
    )
    bundle["sources"] = list({json.dumps(s, sort_keys=True): s for s in source_notices + notices}.values())
    bundle["input_evidence"] = list({json.dumps(item, sort_keys=True): item for item in evidence}.values())
    bundle["exclusions"] = exclusions
    bundle["data_licenses"] = {
        "openfootball": "CC0 1.0",
        "f1db": "CC BY 4.0",
        "wikipedia": "CC BY-SA 4.0",
        **({"world_climbing": CLIMBING_LICENSE} if any(s["kind"] == "world_climbing" for s in notices) else {}),
        **({"weightlifting": WEIGHTLIFTING_LICENSE} if any(s["kind"] == "weightlifting" for s in notices) else {}),
        **{s["kind"]: BOXING_LICENSE for s in notices if s["kind"].startswith("boxing_")},
        **{kind: league_feeds.SOURCES[kind]["license"] for kind in feed_kinds},
        **{source["kind"]: source["license"] for source in national_sources},
        **{source["kind"]: source["license"] for source in country_notices},
    }
    for previous in retained_envelopes:
        for kind, license_name in previous.get("data_licenses", {}).items():
            bundle["data_licenses"].setdefault(kind, license_name)
    bundle["data_license_notice"] = (
        "Software is MIT. Schedule data retains the per-source licenses listed here. "
        "League feed, reviewed boxing and ESPN schedule facts are attributed to their sources, which grant no data license; "
        "league and team names belong to their owners and kickoff is not affiliated with any league. "
        "Wikipedia-derived adaptations are shared under CC BY-SA 4.0, including in this collection. "
        "Source links identify the contributors and pinned revisions; changes are described in sources. "
        "Separately attributed team facts and start times retain their source's terms, rather than the original schedule's license."
    )
    components = {}
    for kind in ("wikipedia",):
        selected = [event for event in bundle["events"] if event["source"] == kind]
        if not selected:
            continue
        component_kinds = {kind} | {event["start_time_source"] for event in selected if event.get("start_time_source")}
        component = {
            "schema_version": "1",
            "season": year,
            "license": bundle["data_licenses"][kind],
            "data_licenses": {
                source_kind: bundle["data_licenses"][source_kind] for source_kind in sorted(component_kinds)
            },
            "license_notice": bundle["data_license_notice"],
            "sources": [source for source in bundle["sources"] if source.get("kind") in component_kinds],
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
