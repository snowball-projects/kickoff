"""Weekly ESPN metadata resolution; never imported by daily publication."""

from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit

from kickoff.models import Participant
from kickoff.team_logos import COHORT_FIELDS, TEAM_SPORTS, cohort, cohort_key, competition_season, source_logo
from kickoff.textutils import espn_logo_url

SITE = "https://site.api.espn.com/apis/site/v2/sports"
CORE = "https://sports.core.api.espn.com/v2/sports"
NAME_FIELDS = ("displayName", "name", "shortDisplayName", "location", "abbreviation")
BASE_URL = "https://snowball-projects.github.io/kickoff/data/"


def league_paths() -> dict[str, str]:
    from kickoff import feeds
    from kickoff.start_times import football_teams

    result = {league: row[0] for league, row in feeds.TEAM_LEAGUES.items()}
    result.update({league: f"rugby/{row[0]}" for league, row in feeds.RUGBY_LEAGUES.items()})
    result.update({league: f"soccer/{row['espn_path']}" for league, row in football_teams().items()})
    result.update(
        NFL="football/nfl",
        NBA="basketball/nba",
        MLB="baseball/mlb",
        NHL="hockey/nhl",
        UEFA_CHAMPIONS_LEAGUE="soccer/uefa.champions",
        FIFA_WORLD_CUP="soccer/fifa.world",
        FIFA_WOMENS_WORLD_CUP="soccer/fifa.wwc",
    )
    return result


def fetch_json(url: str) -> dict | None:
    from kickoff.feeds import get_json

    try:
        payload = get_json(url)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed JSON object: {url}")
    return payload


def published_cohorts(base_url: str = BASE_URL) -> dict[str, dict]:
    """Read the complete published corpus, ignoring all previously enriched logos."""
    manifest = fetch_json(base_url + "manifest.json")
    if not manifest or not isinstance(manifest.get("seasons"), dict) or not manifest["seasons"]:
        raise ValueError("Missing published manifest seasons")
    if sorted(map(int, manifest["seasons"])) != sorted(manifest["available_seasons"]):
        raise ValueError("Incomplete published seasons")
    result, seen_files, seen_events = {}, set(), set()
    for year, season in manifest["seasons"].items():
        if not isinstance(season.get("sports"), list) or not season["sports"]:
            raise ValueError("Missing published league catalog")
        count = 0
        for entry in season["sports"]:
            name = entry["file"]
            if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json") or name in seen_files:
                raise ValueError("Invalid or duplicate published bundle")
            seen_files.add(name)
            bundle = fetch_json(base_url + name)
            if not bundle or str(bundle.get("season")) != year or not isinstance(bundle.get("events"), list):
                raise ValueError(f"Missing published bundle: {name}")
            events = bundle["events"]
            if len(events) != entry["count"] or bundle["updated_at"] != season["updated_at"]:
                raise ValueError(f"Incomplete published bundle: {name}")
            count += len(events)
            for event in events:
                if event["event_id"] in seen_events:
                    raise ValueError("Duplicate published event identity")
                seen_events.add(event["event_id"])
                if event["sport"] not in TEAM_SPORTS:
                    continue
                for participant in event["participants"]:
                    if participant["entity_type"] not in {"team", "club", "national_team"}:
                        continue
                    row = cohort(
                        SimpleNamespace(league=event["league"], source=event["source"], season=event["season"]),
                        Participant(
                            name=participant["name"],
                            participant_id=participant["participant_id"],
                            short_name=participant["short_name"],
                        ),
                    )
                    result[cohort_key(row)] = row
        if count != season["all_events"]:
            raise ValueError("Incomplete published event count")
    if not result:
        raise ValueError("No published team cohorts")
    return result


def _name(value: str) -> str:
    return " ".join(value.casefold().split())


def _names(team: dict) -> set[str]:
    return {_name(team[key]) for key in NAME_FIELDS if isinstance(team.get(key), str) and team[key].strip()}


def _core_url(path: str, season: int, identity: str | None = None) -> str:
    sport, league = path.split("/", 1)
    base = f"{CORE}/{sport}/leagues/{league}/seasons/{season}/teams"
    return f"{base}/{identity}?lang=en&region=us" if identity is not None else f"{base}?limit=1000"


def _team(payload: dict | None, identity: str, url: str) -> dict | None:
    if payload is None:
        return None
    if str(payload.get("id")) != identity or not _names(payload):
        raise ValueError(f"Malformed or mismatched team: {url}")
    logos = payload.get("logos", [])
    if not isinstance(logos, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("href"), str) or not row["href"] for row in logos
    ):
        raise ValueError(f"Malformed team images: {url}")
    if payload.get("logo") is not None and not isinstance(payload["logo"], str):
        raise ValueError(f"Malformed team image: {url}")
    return payload


class Resolver:
    """One fresh resolution run, with request reuse only inside this run."""

    def __init__(self):
        self.teams = {}
        self.indexes = {}

    def core_team(self, path, season, identity):
        key = (path, season, identity)
        if key not in self.teams:
            url = _core_url(*key)
            self.teams[key] = (_team(fetch_json(url), identity, url), url)
        return self.teams[key]

    def season_index(self, path, season):
        key = (path, season)
        if key in self.indexes:
            return self.indexes[key]
        url = _core_url(path, season)
        first = fetch_json(url)
        if first is None:
            self.indexes[key] = None
            return None
        pages, count = first.get("pageCount"), first.get("count")
        if type(pages) is not int or pages < 1 or type(count) is not int or count < 0:
            raise ValueError(f"Malformed roster pagination: {url}")
        identities = []
        prefix = urlsplit(url).path + "/"
        for page in range(1, pages + 1):
            payload = first if page == 1 else fetch_json(f"{url}&page={page}")
            if (
                payload is None
                or not isinstance(payload.get("items"), list)
                or payload.get("pageCount") != pages
                or payload.get("count") != count
                or payload.get("pageIndex", page) != page
            ):
                raise ValueError(f"Incomplete roster page: {url}, page {page}")
            for item in payload["items"]:
                reference = item.get("$ref") if isinstance(item, dict) else None
                if not isinstance(reference, str):
                    raise ValueError(f"Malformed roster reference: {url}")
                parsed = urlsplit(reference)
                identity = parsed.path.removeprefix(prefix)
                if (
                    parsed.scheme not in {"http", "https"}
                    or parsed.netloc != "sports.core.api.espn.com"
                    or not parsed.path.startswith(prefix)
                    or not identity.isdigit()
                ):
                    raise ValueError(f"Invalid roster reference: {reference}")
                identities.append(identity)
        if len(identities) != count or len(set(identities)) != count:
            raise ValueError(f"Incomplete or duplicate roster: {url}")
        with ThreadPoolExecutor(max_workers=6) as executor:
            teams = list(executor.map(lambda identity: (identity, self.core_team(path, season, identity)), identities))
        index = defaultdict(dict)
        for identity, (team, source_url) in teams:
            if team is None:
                raise ValueError(f"Listed team is missing: {source_url}")
            for name in _names(team):
                index[name][identity] = (team, source_url)
        self.indexes[key] = dict(index)
        return self.indexes[key]

    def resolve(self, row):
        path = league_paths().get(row["league"])
        season = row["competition_season"]
        if path is None:
            return None, None, "unsupported_league"
        if season is None:
            return None, None, "unknown_source_season"
        if row["source"] == "espn":
            identity = row["participant_id"]
            if not identity or not identity.isdigit():
                return None, None, "missing_source_id"
            historical, historical_url = self.core_team(path, season, identity)
            agrees = historical is not None and _name(row["name"]) in _names(historical)
            if agrees and source_logo(historical):
                return source_logo(historical), historical_url, "logo"
            current_url = f"{SITE}/{path}/teams/{identity}"
            payload = fetch_json(current_url)
            if payload is not None and not isinstance(payload.get("team"), dict):
                raise ValueError(f"Malformed Site team: {current_url}")
            current = _team(payload["team"] if payload is not None else None, identity, current_url)
            if current is not None and _name(row["name"]) in _names(current):
                logo = source_logo(current)
                return logo, current_url, "logo" if logo else "missing_image"
            return (
                None,
                historical_url if agrees else current_url,
                ("missing_image" if agrees else "identity_conflict" if historical or current else "missing_metadata"),
            )
        index = self.season_index(path, season)
        source_url = _core_url(path, season)
        if index is None:
            return None, source_url, "missing_metadata"
        candidates = index.get(_name(row["name"]), {})
        if len(candidates) != 1 and row["short_name"]:
            short = index.get(_name(row["short_name"]), {})
            candidates = {key: item for key, item in short.items() if not candidates or key in candidates}
        if len(candidates) != 1:
            return None, source_url, "ambiguous_name" if candidates else "unmatched_name"
        team, source_url = next(iter(candidates.values()))
        logo = source_logo(team)
        return logo, source_url, "logo" if logo else "missing_image"


def validate_registry(registry: dict, receipts: dict) -> None:
    if (
        set(registry) != {"schema_version", "logos"}
        or set(receipts) != {"schema_version", "teams"}
        or registry.get("schema_version") != "1"
        or receipts.get("schema_version") != "1"
    ):
        raise ValueError("Invalid team-logo schema")
    logos, teams = registry["logos"], receipts["teams"]
    if not isinstance(logos, dict) or not isinstance(teams, dict) or not teams or not logos.keys() <= teams.keys():
        raise ValueError("Invalid team-logo cohort membership")
    for key, row in teams.items():
        if set(row) != {*COHORT_FIELDS, "competition_season", "status", "source_url", "checked_date"}:
            raise ValueError("Invalid team-logo receipt fields")
        if (
            key != cohort_key(row)
            or any(
                not isinstance(row[field], str) or not row[field] for field in ("league", "source", "season", "name")
            )
            or any(
                row[field] is not None and not isinstance(row[field], str) for field in ("participant_id", "short_name")
            )
        ):
            raise ValueError("Invalid team-logo identity")
        if row["competition_season"] != competition_season(SimpleNamespace(**row)):
            raise ValueError("Invalid source competition season")
        if date.fromisoformat(row["checked_date"]).isoformat() != row["checked_date"]:
            raise ValueError("Invalid team-logo check date")
        source = row["source_url"]
        if source is not None and not source.startswith((SITE + "/", CORE + "/")):
            raise ValueError("Invalid team-logo source")
        if row["status"] == "logo":
            if (
                key not in logos
                or not source
                or not espn_logo_url(logos[key])
                or logos[key] != espn_logo_url(logos[key])
            ):
                raise ValueError("Image missing its source or valid URL")
        elif key in logos or row["status"] not in {
            "unsupported_league",
            "unknown_source_season",
            "missing_source_id",
            "missing_metadata",
            "missing_image",
            "identity_conflict",
            "ambiguous_name",
            "unmatched_name",
        }:
            raise ValueError("Invalid image absence")


def refresh_team_logos(registry_path: Path, receipts_path: Path, base_url: str = BASE_URL) -> tuple[int, int]:
    cohorts = published_cohorts(base_url)
    resolver = Resolver()
    checked = datetime.now(UTC).date().isoformat()
    registry, receipts = {"schema_version": "1", "logos": {}}, {"schema_version": "1", "teams": {}}
    for key, row in sorted(cohorts.items()):
        logo, source_url, status = resolver.resolve(row)
        if logo:
            registry["logos"][key] = logo
        receipts["teams"][key] = {**row, "status": status, "source_url": source_url, "checked_date": checked}
    validate_registry(registry, receipts)
    # Finish every request, validation and serialization before touching either output.
    bodies = [json.dumps(payload, ensure_ascii=True, indent=2) + "\n" for payload in (registry, receipts)]
    registry_path.write_text(bodies[0])
    receipts_path.write_text(bodies[1])
    return len(cohorts), len(registry["logos"])
