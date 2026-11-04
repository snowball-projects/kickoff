"""Optional structured results with one strict main-process wall-time budget."""

from __future__ import annotations

import hashlib
import json
import logging
import signal
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from kickoff.climbing_results import _event_url, climbing_result, parse_climbing_podiums
from kickoff.f1_results import RAW, load_f1_result
from kickoff.http import read_bounded_response
from kickoff.results import attach_result
from kickoff.reviewed_schedules import CLIMBING_LICENSE, CLIMBING_TERMS, WEIGHTLIFTING_LICENSE

LOGGER = logging.getLogger(__name__)
MAX_BYTES = 20_000_000
USER_AGENT = "kickoff-refresh/0.6 (https://github.com/snowball-projects/kickoff)"
MEDALS = ("total_medalists", "snatch_medalists", "clean_and_jerk_medalists")
PROVENANCE = ("gender", "weight_class", "source_url", "input_url", "checked_date", "revision", "sha256", "hash_scope")


class _BudgetExpired(BaseException):
    """Escape optional parsers' Exception handlers without attaching partial work."""


def _expire(_signum, _frame):
    raise _BudgetExpired()


def _instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return parsed if isinstance(parsed, datetime) and parsed.tzinfo is not None else None


def _eligible(event, now):
    day = date.fromisoformat(event.end_calendar_date or event.calendar_date)
    if day < now.date() - timedelta(days=7):
        return False
    if event.start_time_utc is not None and _instant(event.start_time_utc) > now:
        return False
    zone = ZoneInfo(event.timezone) if event.timezone else timezone.utc
    return day < now.astimezone(zone).date() or (day == now.date() and event.status == "finished")


def _scope_key(row):
    return row["gender"], row["weight_class"].removesuffix(" kg").replace(">", "+").strip()


class ResultsLoader:
    """Main-thread Linux loader; cache/deadline span all years in one publication.

    Source reads, CPU parsing and joins share a remaining wall-time budget.
    Attachments happen after the callback returns and its alarm is restored.
    No build-time IWF/PDF requests or source start-list refreshes are permitted.
    """

    def __init__(self, read_bytes=None, budget=120, timeout=5):
        self.remaining = max(0.0, float(budget))
        self.timeout = max(0.0, float(timeout))
        self._transport = read_bytes
        self._deadline = None
        self._bodies, self.checked = {}, {}
        self._driver_cache, self._podiums = {}, {}
        self._definitions, self._allocations, self._junior = {}, {}, {}
        self._wiki_parsed, self._wiki_requests = {}, {}

    def _run(self, callback):
        if self.remaining <= 0:
            return None
        started = monotonic()
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        duration = min(self.remaining, previous_timer[0]) if previous_timer[0] > 0 else self.remaining
        self._deadline = started + duration
        installed = False
        try:
            signal.signal(signal.SIGALRM, _expire)
            installed = True
            signal.setitimer(signal.ITIMER_REAL, duration)
            return callback()
        except _BudgetExpired:
            self.remaining = 0.0
            LOGGER.warning("Optional result work reached its wall-time deadline")
            return None
        except Exception as error:
            LOGGER.warning("Optional result omitted: %s", error)
            return None
        finally:
            if installed:
                signal.setitimer(signal.ITIMER_REAL, 0)
            elapsed = monotonic() - started
            self.remaining = max(0.0, self.remaining - elapsed)
            self._deadline = None
            if installed:
                signal.signal(signal.SIGALRM, previous_handler)
                if previous_timer[0] > 0:
                    signal.setitimer(signal.ITIMER_REAL, max(0.000001, previous_timer[0] - elapsed), previous_timer[1])

    def _read(self, url):
        if url in self._bodies:
            return self._bodies[url]
        self._bodies[url] = None
        parsed = urlsplit(url)
        if (
            parsed.hostname == "iwf.sport"
            or (parsed.hostname or "").endswith(".iwf.sport")
            or parsed.path.lower().endswith(".pdf")
        ):
            return None
        try:
            if self._transport is None:
                remaining = max(0.000001, self._deadline - monotonic())
                request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
                with urlopen(request, timeout=min(self.timeout, remaining)) as response:
                    body = read_bounded_response(response, max_bytes=MAX_BYTES)
            else:
                body = self._transport(url)
                if body is not None:
                    stream = BytesIO(body)
                    stream.headers = {}
                    body = read_bounded_response(stream, max_bytes=MAX_BYTES)
            if body is not None and body.startswith(b"%PDF"):
                raise ValueError("Expected structured result source, received PDF")
            self._bodies[url] = body
            return body
        except Exception as error:
            LOGGER.warning("Optional result source unavailable for %s: %s", url, error)
            return None
        finally:
            observed = datetime.now(timezone.utc)
            self.checked[url] = observed.date().isoformat()

    def _f1(self, event, context):
        result = load_f1_result(
            event_id=event.event_id,
            event_type=event.event_type,
            race_path=context["race_path"],
            race_body=context["race_body"],
            revision=context["revision"],
            checked_date=datetime.now(timezone.utc).date().isoformat(),
            read_bytes=self._read,
            driver_cache=self._driver_cache,
        )
        if result is not None:
            filename = "race-results.yml" if event.event_type == "race" else "sprint-race-results.yml"
            url = f"{RAW}/{context['revision']}/{context['race_path']}/{filename}"
            result["checked_date"] = self.checked[url]
        return result

    def _climbing(self, event, reviewed_dir):
        url = _event_url(event.source_url or "")
        if url is None:
            return None
        if url not in self._podiums:
            self._podiums[url] = []
            body = self._read(url)
            if body is not None:
                self._podiums[url] = parse_climbing_podiums(body, source_url=url, checked_date=self.checked[url])
        directory = str(reviewed_dir)
        if directory not in self._allocations:
            self._allocations[directory] = {}
            path = Path(reviewed_dir) / "receipts/climbing-result-blocks.json"
            if path.exists():
                self._allocations[directory] = {row["event_id"]: row for row in json.loads(path.read_text())["blocks"]}
        result = climbing_result(event, self._podiums[url], allocation=self._allocations[directory].get(event.event_id))
        return result

    def _sessions(self, reviewed_dir, year):
        key = (str(reviewed_dir), year)
        if key not in self._definitions:
            self._definitions[key] = []
            self._definitions[key] = json.loads((Path(reviewed_dir) / f"{year}-weightlifting.json").read_text())[
                "events"
            ]
        return self._definitions[key]

    def _combine(self, classes, session):
        if not classes:
            return None
        sources = [{key: row[key] for key in PROVENANCE if key in row} for row in classes]
        first = sources[0]
        result = {
            key: first[key]
            for key in ("source_url", "checked_date", "revision", "sha256", "hash_scope")
            if key in first
        }
        result.update(
            kind="weightlifting",
            sources=sources,
            athletes=[athlete for row in classes for athlete in row.get("athletes", [])],
        )
        for field in MEDALS:
            result[field] = [medal for row in classes for medal in row.get(field, [])]
        expected = {_scope_key(row) for row in session["categories"]}
        actual = {_scope_key(row) for row in classes}
        result["_complete"] = (
            expected == actual
            and all(row.get("_complete", False) for row in classes)
            and bool(result["athletes"])
            and all(len(a.get("snatch", [])) == len(a.get("clean_and_jerk", [])) == 3 for a in result["athletes"])
        )
        return result

    def _junior_result(self, event, year, reviewed_dir, session):
        key = (str(reviewed_dir), year)
        if key not in self._junior:
            self._junior[key] = None
            path = Path(reviewed_dir) / "receipts" / f"{year}-junior-results.json"
            snapshot = json.loads(path.read_text())
            sessions = snapshot["sessions"]

            digest = hashlib.sha256(json.dumps(sessions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if (
                snapshot["league"] != "IWF_JUNIOR_WORLDS"
                or snapshot["year"] != year
                or snapshot["sha256"] != digest
                or len(sessions) != snapshot["session_count"]
                or sum(len(s["athletes"]) for s in sessions) != snapshot["athlete_count"]
            ):
                raise ValueError("Reviewed Junior result snapshot does not match")
            self._junior[key] = snapshot
        snapshot = self._junior[key]
        if snapshot is None:
            return None
        source_session = next((row for row in snapshot["sessions"] if row["event_id"] == event.event_id), None)
        if source_session is None or source_session["categories"] != session["categories"]:
            return None
        whole_field = [athlete for row in snapshot["sessions"] for athlete in row["athletes"]]
        classes = []
        for category in session["categories"]:
            scope = {key: category[key] for key in ("gender", "weight_class")}
            if any(all(row[key] == value for key, value in scope.items()) for row in classes):
                continue
            selected = [a for a in source_session["athletes"] if all(a[key] == value for key, value in scope.items())]
            row = {
                **scope,
                **{k: snapshot[k] for k in ("source_url", "checked_date", "sha256", "hash_scope")},
                "revision": snapshot["review_revision"],
                "athletes": selected,
                "_complete": True,
            }
            for field, rank_field, weight_field in [
                ("total_medalists", "total_rank", "total_kg"),
                ("snatch_medalists", "snatch_rank", "snatch_best_kg"),
                ("clean_and_jerk_medalists", "clean_and_jerk_rank", "clean_and_jerk_best_kg"),
            ]:
                row[field] = [
                    {
                        **{k: a[k] for k in ("name", "nation", "gender", "weight_class", "lot")},
                        "rank": a[rank_field],
                        "weight_kg": a[weight_field],
                    }
                    for a in whole_field
                    if all(a[k] == value for k, value in scope.items()) and a.get(rank_field) in {1, 2, 3}
                ]
            classes.append(row)
        result = self._combine(classes, session)
        if result is not None:
            result["membership_source"] = snapshot["identity_source"]
            result["review_revision"] = snapshot["review_revision"]
        return result

    def _wiki_classes(self, url, wiki):
        if url not in self._wiki_parsed:
            self._wiki_parsed[url] = []
            body = self._read(url)
            if body is not None:
                self._wiki_parsed[url] = wiki.parse_classes(body, input_url=url, checked_date=self.checked[url])
        return self._wiki_parsed[url]

    def _weightlifting(self, event, year, reviewed_dir):
        sessions = self._sessions(reviewed_dir, year)
        session = next((row for row in sessions if row["id"] == event.event_id), None)
        if session is None:
            return None
        if event.league == "IWF_JUNIOR_WORLDS":
            return self._junior_result(event, year, reviewed_dir, session)
        from kickoff import weightlifting_wikipedia as wiki

        title = wiki.competition_title(event.league, year)
        if title is None:
            return None
        url = wiki.api_url(title)
        classes = self._wiki_classes(url, wiki)
        if url not in self._wiki_requests:
            body = self._bodies.get(url)
            self._wiki_requests[url] = (
                wiki.class_requests(body, input_url=url, checked_date=self.checked[url]) if body is not None else []
            )
        needed = {_scope_key(row) for row in session["categories"]}
        candidates = {(row["gender"], row["weight_class"]): row for row in classes}
        for request in self._wiki_requests[url]:
            identity = request["gender"], request["weight_class"]
            if identity not in needed or candidates.get(identity, {}).get("_complete"):
                continue
            for parsed in self._wiki_classes(request["input_url"], wiki):
                key = parsed["gender"], parsed["weight_class"]
                if key in needed:
                    prior = candidates.get(key, {})
                    quality = bool(parsed.get("_complete")), bool(parsed.get("athletes"))
                    previous_quality = bool(prior.get("_complete")), bool(prior.get("athletes"))
                    if quality >= previous_quality:
                        candidates[key] = parsed
        selected = wiki.classes_for_session(list(candidates.values()), session, reviewed_sessions=sessions)
        result = self._combine(selected, session)
        return result if result is not None and result["_complete"] else None

    def enrich(
        self,
        events,
        year,
        reviewed_dir,
        *,
        f1_contexts=None,
        now=None,
    ):
        sources, evidence = {}, {}
        contexts = f1_contexts or {}
        moment = now or datetime.now(timezone.utc)
        for event in events:
            if self.remaining <= 0 or event.result is not None:
                continue
            if event.sport == "weightlifting" and ("YOUTH" in event.league or "MASTERS" in event.league):
                continue
            try:
                eligible = _eligible(event, moment)
            except (TypeError, ValueError, LookupError):
                eligible = False
            if not eligible:
                continue
            if event.source == "f1db" and event.event_type in {"race", "sprint"} and event.event_id in contexts:
                result = self._run(lambda event=event: self._f1(event, contexts[event.event_id]))
                kind = "f1db"
            elif event.sport == "climbing" and event.event_type == "session" and event.round_or_stage == "final":
                result = self._run(lambda event=event: self._climbing(event, reviewed_dir))
                kind = "world_climbing"
            elif event.sport == "weightlifting":
                result = self._run(lambda event=event: self._weightlifting(event, year, reviewed_dir))
                kind = "weightlifting" if event.league == "IWF_JUNIOR_WORLDS" else "wikipedia"
            else:
                continue
            if result is None:
                continue
            attach_result(event, result)
            for source in result.get("sources", [result]):
                url, checked, digest = source["source_url"], source["checked_date"], source["sha256"]
                if kind == "f1db":
                    notice = {
                        "kind": kind,
                        "name": "F1DB and contributors",
                        "url": "https://github.com/f1db/f1db",
                        "license": "CC BY 4.0",
                        "license_url": "https://creativecommons.org/licenses/by/4.0/",
                        "revision": result["revision"],
                    }
                elif kind == "world_climbing":
                    notice = {
                        "kind": kind,
                        "name": "World Climbing official results",
                        "url": url,
                        "license": CLIMBING_LICENSE,
                        "license_url": CLIMBING_TERMS,
                    }
                elif kind == "wikipedia":
                    notice = {
                        "kind": kind,
                        "name": "Wikipedia contributors",
                        "url": url,
                        "license": "CC BY-SA 4.0",
                        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    }
                else:
                    notice = {
                        "kind": kind,
                        "name": "Reviewed IWF Junior results",
                        "url": url,
                        "license": WEIGHTLIFTING_LICENSE,
                        "license_url": url,
                    }
                notice.update(
                    {
                        key: source[key]
                        for key in ("checked_date", "revision", "input_url", "sha256", "hash_scope")
                        if key in source
                    }
                )
                sources[json.dumps(notice, sort_keys=True)] = notice
                key = kind, url, checked, digest
                if key not in evidence:
                    evidence[key] = {
                        "kind": kind,
                        "url": url,
                        "checked_date": checked,
                        "sha256": digest,
                        "hash_scope": source.get("hash_scope", "source response bytes"),
                        "results_added": [],
                        **{key: source[key] for key in ("input_url", "revision") if key in source},
                    }
                evidence[key]["results_added"].append({"event_id": event.event_id, "complete": event.result_complete})
        return list(sources.values()), list(evidence.values())
