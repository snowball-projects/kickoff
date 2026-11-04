"""Optional official start-book facts; no roster failure stops schedule publication."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from kickoff.models import CalendarEvent, Participant
from kickoff.pdf import _reader_from_bytes

LOGGER = logging.getLogger(__name__)
START_LIST_LEAGUES = {
    "IWF_WORLDS",
    "IWF_JUNIOR_WORLDS",
    "WEIGHTLIFTING_EUROPE",
    "WEIGHTLIFTING_ASIA",
    "WEIGHTLIFTING_AFRICA",
    "WEIGHTLIFTING_PAN_AMERICA",
    "WEIGHTLIFTING_OCEANIA",
    "WEIGHTLIFTING_COMMONWEALTH_GAMES",
    "WEIGHTLIFTING_ASIAN_GAMES",
}
ENTRY_FIELDS = (
    "entry_total_kg",
    "start_list_category",
    "start_list_nation",
    "start_list_guest",
    "start_list_source_url",
    "start_list_checked_date",
)
Category = tuple[str, str, str]
SessionKey = frozenset[Category]


@dataclass(frozen=True)
class Entry:
    lot: str
    name: str
    nation: str
    weight: str
    total: int
    page: int
    guest: bool = False


@dataclass
class Session:
    categories: SessionKey
    entries: list[Entry]
    expected: int
    issue: str | None = None


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and (href := dict(attrs).get("href")):
            self.hrefs.append(href)


def catalog() -> dict:
    return json.loads(files("kickoff").joinpath("config/weightlifting-startlists.json").read_text())


def _lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _easy_categories(gender: str, text: str) -> SessionKey:
    categories = frozenset((gender, weight, group) for weight, group in re.findall(r"(\+?\d+)\s*([A-Z])", text))
    if not categories:
        raise ValueError("Start list has no explicit class/group identity")
    return categories


def _owl_categories(gender: str, group: str, text: str) -> SessionKey:
    weights = re.findall(r"\+?\d+", text)
    if not weights:
        raise ValueError("Start list has no explicit bodyweight class")
    return frozenset((gender, weight, group) for weight in weights)


def parse_start_book(content: bytes, family: str) -> list[Session]:
    """Parse complete, supported roster pages; timetable counts detect lost rows."""
    pages = [
        (number, _lines(page.extract_text() or "")) for number, page in enumerate(_reader_from_bytes(content).pages, 1)
    ]
    expected: dict[SessionKey, int] = {}
    spanish_counts: dict[tuple[str, str], int] = {}
    sessions = []
    for number, lines in pages:
        if family == "easywl":
            for line in lines:
                match = re.fullmatch(r"\d+ (Women|Men) SE (.+?) (\d+)(?: \([\d/]+\))? \d\d/\d\d .+", line)
                if match:
                    key = _easy_categories(match[1].lower(), match[2])
                    if key in expected:
                        raise ValueError("Duplicate timetable session")
                    expected[key] = int(match[3])
            heading = next(
                (
                    re.fullmatch(r"START LIST (WOMEN|MEN) SE (.+)", line)
                    for line in lines
                    if line.startswith("START LIST ")
                ),
                None,
            )
            if not heading:
                continue
            key = _easy_categories(heading[1].lower(), heading[2])
            pattern = r"(?:\d+ )?(\d+) (.+?) \d\d\.\d\d\.\d{4} ([A-Z]{3}) (\+?\d+) SE (\d+)"
            rows = []
            for line in lines:
                match = re.fullmatch(pattern, line)
                if match:
                    rows.append(Entry(match[1], match[2], match[3], match[4], int(match[5]), number))
        elif family == "owlcms":
            for line in lines:
                match = re.fullmatch(r"\d+ - GROUP ([A-Z]) ([+\d &]+) KG(?: [WM])? .+ ([FM]) (\d+)", line)
                if match:
                    key = _owl_categories("women" if match[3] == "F" else "men", match[1], match[2])
                    if key in expected:
                        raise ValueError("Duplicate timetable session")
                    expected[key] = int(match[4])
            if not any(line.startswith("Session GROUP") for line in lines):
                continue
            heading = next(
                (
                    re.fullmatch(r"GROUP ([A-Z]) (WOMEN|MEN) ([+\d &]+) KG", line)
                    for line in lines
                    if re.match(r"GROUP [A-Z] (?:WOMEN|MEN) ", line)
                ),
                None,
            )
            if heading:
                key = _owl_categories(heading[2].lower(), heading[1], heading[3])
            else:
                trailing = next(
                    (
                        re.fullmatch(r"GROUP ([A-Z]) ([+\d &]+) KG ([WM])", line)
                        for line in lines
                        if re.match(r"GROUP [A-Z] ", line)
                    ),
                    None,
                )
                if not trailing:
                    raise ValueError("Unsupported roster session heading")
                key = _owl_categories("women" if trailing[3] == "W" else "men", trailing[1], trailing[2])
            rows, ordinals = [], []
            pattern = r"(\d+) (\d+) (.+?) ([A-Z]{3}) \d{1,2}/\d{1,2}/\d{4} SR ([FM]) ([>+]?\d+) (\d+)"
            for line in lines:
                match = re.fullmatch(pattern, line)
                if match:
                    if ("women" if match[5] == "F" else "men") not in {category[0] for category in key}:
                        raise ValueError("Athlete gender contradicts session heading")
                    ordinals.append(int(match[1]))
                    name = match[3].replace(" [guest]", "")
                    rows.append(
                        Entry(
                            match[2],
                            name,
                            match[4],
                            match[6].replace(">", "+"),
                            int(match[7]),
                            number,
                            "[guest]" in match[3],
                        )
                    )
            candidates = [line for line in lines if re.match(r"\d+ \d+ ", line)]
            if len(candidates) != len(rows) or ordinals != list(range(1, len(rows) + 1)):
                raise ValueError("Incomplete athlete row sequence")
        elif family == "owlcms-es":
            if any(line == "CRONOGRAMA DE COMPETENCIAS" for line in lines):
                for line in lines:
                    match = re.fullmatch(r"([FM]) ([>+]?\d+) .+ (\d+)", line)
                    if match:
                        identity = ("women" if match[1] == "F" else "men", match[2].replace(">", "+"))
                        if identity in spanish_counts:
                            raise ValueError("Duplicate timetable category")
                        spanish_counts[identity] = int(match[3])
            if "START LIST" not in lines:
                continue
            heading = next(
                (
                    re.fullmatch(r"([FM])\s*([>+]?\d+) KG ([A-Z])", line)
                    for line in lines
                    if re.match(r"[FM]\s*[>+]?\d+ KG ", line)
                ),
                None,
            )
            if not heading:
                raise ValueError("Unsupported Spanish roster heading")
            gender = "women" if heading[1] == "F" else "men"
            weight = heading[2].replace(">", "+")
            key = frozenset({(gender, weight, heading[3])})
            expected[key] = spanish_counts[(gender, weight)]
            candidates, buffer = [], ""
            for line in lines:
                if re.match(r"\d+ \d+ ", line):
                    if buffer:
                        candidates.append(buffer)
                    buffer = line
                elif buffer:
                    buffer += " " + line
            if buffer:
                candidates.append(buffer)
            rows, ordinals = [], []
            pattern = r"(\d+) (\d+) (.+?) ([A-Z]{3}) \d{1,2}/\d{1,2}/\d{4} ([FM]) ([>+]?\d+) (\d+)"
            for line in candidates:
                match = re.fullmatch(pattern, line)
                if not match or ("women" if match[5] == "F" else "men") != gender:
                    raise ValueError("Incomplete Spanish athlete row")
                ordinals.append(int(match[1]))
                rows.append(Entry(match[2], match[3], match[4], match[6].replace(">", "+"), int(match[7]), number))
            if ordinals != list(range(1, len(rows) + 1)):
                raise ValueError("Incomplete Spanish athlete row sequence")
        else:
            raise ValueError("Unsupported start-book format")
        if not rows or any(entry.total <= 0 for entry in rows):
            raise ValueError("Start list has no positive entry totals")
        mismatch = [entry for entry in rows if sum(weight == entry.weight for _, weight, _ in key) != 1]
        issue = (
            f"Source athlete class disagrees with session: lot {mismatch[0].lot}, class {mismatch[0].weight}, page {number}"
            if mismatch
            else None
        )
        sessions.append(Session(key, rows, 0, issue))
    actual = {session.categories for session in sessions}
    if len(actual) != len(sessions) or actual != expected.keys():
        raise ValueError("Roster and timetable session coverage disagree")
    if family == "owlcms-es":
        identities = {(gender, weight) for key in actual for gender, weight, _ in key}
        if identities != spanish_counts.keys() or len(identities) != len(actual):
            raise ValueError("Spanish roster and timetable category coverage disagree")
    lots = []
    for session in sessions:
        session.expected = expected[session.categories]
        # Asia's timetable sometimes includes guests and sometimes excludes them.
        # This range catches missing rows and unexplained extras, but cannot prove
        # that a stale timetable and a syntactically complete roster agree.
        guests = sum(entry.guest for entry in session.entries) if family == "owlcms" else 0
        if not session.expected <= len(session.entries) <= session.expected + guests:
            raise ValueError("Roster count disagrees with official timetable")
        lots.extend(entry.lot for entry in session.entries)
    if not sessions or len(set(lots)) != len(lots):
        raise ValueError("Empty or duplicate athlete cohort")
    return sessions


def reviewed_categories(row: dict) -> SessionKey:
    return frozenset(
        (category["gender"], category["weight_class"], category["group"]) for category in row["categories"]
    )


ROSTER_HASH_SCOPE = "canonical reviewed roster facts (sessions; sorted keys, compact ASCII JSON), not raw PDF bytes"


def roster_hash(sessions: list[dict]) -> str:
    return hashlib.sha256(json.dumps(sessions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reviewed_start_book(book: dict, reviewed_dir: Path) -> tuple[list[Session], dict]:
    """Read audited factual cohorts, keeping their actual review date and revision."""
    snapshot = json.loads((reviewed_dir / book["snapshot_file"]).read_text())
    if (snapshot["league"], snapshot["year"]) != (book["league"], book["year"]):
        raise ValueError("Reviewed roster has the wrong competition")
    if snapshot["hash_scope"] != ROSTER_HASH_SCOPE or snapshot["sha256"] != roster_hash(snapshot["sessions"]):
        raise ValueError("Reviewed roster canonical-fact hash does not match")
    datetime.fromisoformat(snapshot["checked_date"])
    parsed = []
    lots = []
    for row in snapshot["sessions"]:
        key = reviewed_categories(row)
        entries = [Entry(**entry, page=0) for entry in row["entries"]]
        if not entries or len(entries) != row["athlete_count"]:
            raise ValueError("Reviewed roster athlete count does not match")
        if any(entry.total <= 0 or sum(weight == entry.weight for _, weight, _ in key) != 1 for entry in entries):
            raise ValueError("Reviewed athlete class or entry total contradicts session")
        parsed.append(Session(key, entries, len(entries)))
        lots.extend(entry.lot for entry in entries)
    if len(parsed) != snapshot["session_count"] or len(lots) != snapshot["athlete_count"]:
        raise ValueError("Reviewed roster book counts do not match")
    if len(set(lots)) != len(lots) or len({row["event_id"] for row in snapshot["sessions"]}) != len(parsed):
        raise ValueError("Reviewed roster contains duplicate athletes or sessions")
    return parsed, snapshot


class StartListLoader:
    """One run's optional reads. No retries; at most two URLs per configured live book.

    The start budget and short socket timeout limit ordinary outages. They are not
    a hard wall-clock deadline against a server that slowly drips HTTP headers.
    """

    def __init__(self, read=None, *, clock=monotonic, budget=60, timeout=8):
        self.read = read
        self.clock = clock
        self.deadline = None
        self.budget = budget
        self.timeout = timeout
        self.max_requests = 2 * sum(book["format"] != "reviewed-roster" for book in catalog()["books"])
        self.cache: dict[str, bytes | None] = {}
        self.checked: dict[str, str] = {}

    def _read(self, url: str) -> bytes | None:
        if url in self.cache:
            return self.cache[url]
        if self.deadline is None:
            self.deadline = self.clock() + self.budget
        self.cache[url] = None
        try:
            remaining = self.deadline - self.clock()
            if remaining <= 0 or len(self.cache) > self.max_requests:
                raise TimeoutError("Optional start-list budget exhausted")
            if self.read:
                content = self.read(url)
            else:
                request = Request(url, headers={"User-Agent": "kickoff (https://github.com/snowball-projects/kickoff)"})
                with urlopen(request, timeout=min(self.timeout, remaining)) as response:
                    content = response.read(20_000_001)
            if len(content) > 20_000_000:
                raise ValueError("Start-list source exceeds existing source-size limit")
            self.cache[url] = content
            self.checked[url] = datetime.now(timezone.utc).date().isoformat()
        except Exception as error:
            LOGGER.warning("Optional weightlifting start list unavailable: %s (%s)", url, error)
        return self.cache[url]

    def enrich(self, events: list[CalendarEvent], reviewed_dir: Path, year: int) -> tuple[list[dict], list[dict]]:
        specs = catalog()
        sources, evidence = [], []
        relevant = [
            book
            for book in specs["books"]
            if book["year"] == year and any(event.league == book["league"] for event in events)
        ]
        if not relevant:
            return sources, evidence
        rows = json.loads((reviewed_dir / f"{year}-weightlifting.json").read_text())["events"]
        definitions = {row["id"]: row for row in rows}
        for book in relevant:
            cohort = [event for event in events if event.league == book["league"] and event.event_type == "session"]
            try:
                provenance = {}
                if book["format"] == "reviewed-roster":
                    parsed, snapshot = reviewed_start_book(book, reviewed_dir)
                    if {row["event_id"] for row in snapshot["sessions"]} != {event.event_id for event in cohort}:
                        raise ValueError("Reviewed roster does not match every current session identity")
                    url, checked, sha = snapshot["source_url"], snapshot["checked_date"], snapshot["sha256"]
                    provenance = {
                        "hash_scope": snapshot["hash_scope"],
                        "revision": snapshot["revision"],
                        "collection_method": snapshot["collection_method"],
                    }
                else:
                    landing = self._read(book["landing_url"])
                    if landing is None:
                        continue
                    links = Links()
                    links.feed(landing.decode("utf-8"))
                    urls = {
                        urljoin(book["landing_url"], href)
                        for href in links.hrefs
                        if re.search(book["link_pattern"], href, re.IGNORECASE)
                    }
                    if len(urls) != 1:
                        raise ValueError("Latest official start book is absent or ambiguous")
                    url = urls.pop()
                    if urlsplit(url).scheme != "https" or urlsplit(url).netloc != urlsplit(book["landing_url"]).netloc:
                        raise ValueError("Start book is not on its reviewed publisher host")
                    content = self._read(url)
                    if content is None:
                        continue
                    parsed = parse_start_book(content, book["format"])
                    checked = self.checked[url]
                    sha = hashlib.sha256(content).hexdigest()
                by_category = {session.categories: session for session in parsed}
                keys = [reviewed_categories(definitions[event.event_id]) for event in cohort]
                if len(set(keys)) != len(keys) or set(keys) != by_category.keys():
                    raise ValueError("Start book does not match every reviewed session")
                replacements, omitted = [], []
                for event, key in zip(cohort, keys, strict=True):
                    if by_category[key].issue:
                        omitted.append({"event_id": event.event_id, "reason": by_category[key].issue})
                        continue
                    participants = []
                    for entry in by_category[key].entries:
                        gender, weight, group = next(category for category in key if category[1] == entry.weight)
                        label = f"{'Women' if gender == 'women' else 'Men'}'s {weight} kg, Group {group}"
                        metadata = {
                            "entry_total_kg": entry.total,
                            "start_list_category": label,
                            "start_list_nation": entry.nation,
                            "start_list_guest": entry.guest,
                            "start_list_source_url": url,
                            "start_list_checked_date": checked,
                        }
                        country = specs["country_codes"].get(entry.nation.upper())
                        if country:
                            metadata.update(
                                country_code=country["code"],
                                country_source_url=country["source_url"],
                                country_checked_date=country["checked_date"],
                            )
                        participants.append(
                            Participant(
                                name=entry.name,
                                participant_id=f"{book['league']}:{year}:{entry.lot}",
                                entity_type="athlete",
                                metadata=metadata,
                            )
                        )
                    replacements.append((event, participants))
                for event, participants in replacements:
                    event.participants = participants
                sources.append(
                    {
                        "kind": "weightlifting",
                        "name": book["name"],
                        "publisher": book["publisher"],
                        "url": url,
                        "license": "Schedule facts; no data license granted",
                        "license_url": url,
                        "checked_date": checked,
                        "sha256": sha,
                        **provenance,
                        "changes": "Factual athlete names, source nation codes and entry totals from the complete current official start lists; no birth dates or source pages copied.",
                    }
                )
                evidence.append(
                    {
                        "kind": "weightlifting",
                        "url": url,
                        "landing_url": book["landing_url"],
                        "sha256": sha,
                        "checked_date": checked,
                        "sessions": len(replacements),
                        **provenance,
                        "parsed_sessions": len(parsed),
                        "parsed_athletes": sum(len(session.entries) for session in parsed),
                        "omitted_sessions": omitted,
                        "athletes": sum(len(participants) for _, participants in replacements),
                    }
                )
            except Exception as error:
                LOGGER.warning("Optional weightlifting roster omitted for %s: %s", book["league"], error)
        return sources, evidence
